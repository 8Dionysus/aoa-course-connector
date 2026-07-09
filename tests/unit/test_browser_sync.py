from __future__ import annotations

import json
from pathlib import Path

import pytest

import aoa_course_connector.refresh as refresh_module
import aoa_course_connector.sync.browser_session as browser_sync_module
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.discover import discover_browser_fixture
from aoa_course_connector.ingest.browser_session import _materialize_browser_raw
from aoa_course_connector.index import build_semantic_index
from aoa_course_connector.query import render_answer_packet
from aoa_course_connector.sources import upsert_source
from aoa_course_connector.sync import load_sync_status, sync_browser_fixture_sources
from aoa_course_connector.sync.checkpoints import checkpoint_store_path, make_checkpoint, upsert_checkpoint


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_browser_fixture_sync_writes_checkpoints_and_artifacts(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    discover_browser_fixture(storage, "getcourse", run_id="getcourse-browser-discovery-fixture", register=True)
    receipt = sync_browser_fixture_sources(
        storage,
        sync_run_id="browser-sync-fixture",
        platforms=["getcourse"],
        source_limit=1,
        build_artifacts=True,
    )
    assert receipt["status"] == "ok"
    assert receipt["synced_count"] == 1
    checkpoint = receipt["synced_sources"][0]
    assert checkpoint["status"] == "ok"
    assert checkpoint["normalized_path"]
    assert checkpoint["index_path"]
    assert checkpoint["semantic_index_path"]
    assert checkpoint["graph_path"]
    stable_identity = checkpoint["stable_identity"]
    assert stable_identity["available"] is True
    assert stable_identity["fingerprint"].startswith("sha256:")
    assert stable_identity["counts"]["course_ids"] == 1
    assert stable_identity["counts"]["lesson_ids"] >= 1
    assert stable_identity["counts"]["step_ids"] >= 1
    assert Path(str(checkpoint["semantic_index_path"])).is_file()
    materialize_receipt = json.loads(Path(str(checkpoint["receipt_path"])).read_text(encoding="utf-8"))
    assert materialize_receipt["content_counts"]["course_count"] == stable_identity["counts"]["course_ids"]
    assert materialize_receipt["content_counts"]["lesson_count"] == stable_identity["counts"]["lesson_ids"]
    assert materialize_receipt["content_counts"]["step_count"] == stable_identity["counts"]["step_ids"]
    assert materialize_receipt["content_counts"]["evidence_count"] == materialize_receipt["evidence_count"]
    status = load_sync_status(storage, sync_run_id="browser-sync-fixture", platform="getcourse")
    assert status["ok_count"] == 1
    packet = render_answer_packet(storage, "GetCourse bootloader rollback evidence", run_id=checkpoint["run_id"])
    assert packet["result_count"] >= 1
    assert packet["evidence_chain"]
    hint = packet["results"][0]["refresh_hint"]
    assert hint["platform"] == "getcourse"
    assert hint["registry_match"] is True
    assert hint["source_refresh"]["registry_match"] is True
    assert "preflight connected-plan --platform getcourse" in hint["source_refresh"]["preflight_command"]
    sync_command = hint["source_refresh"]["sync_command"]
    assert "sync browser-live" in sync_command
    assert f"--source-id {checkpoint['source_id']}" in sync_command
    assert '--state-file "${AOA_COURSE_AUTH_ROOT:-.connector-state/auth}/getcourse/account.storage-state.json"' in sync_command
    assert hint["source_refresh"]["post_sync_rebuild_commands"] == [
        "aoa-course build-index --run <checkpoint-run-id>",
        "aoa-course build-semantic-index --run <checkpoint-run-id>",
        "aoa-course build-graph --run <checkpoint-run-id>",
    ]
    assert "keyword/semantic/graph artifacts" in hint["source_refresh"]["post_sync_guidance"]
    assert "lesson-context" in hint["source_refresh"]["post_sync_guidance"]
    assert any("lesson-context" in command and "--mode keyword" in command for command in hint["local_query_commands"])
    assert any("lesson-context" in command for command in packet["refresh_report"]["local_query_commands"])
    assert packet["refresh_report"]["registry_matched_source_count"] == 1


def test_browser_fixture_sync_preserves_stable_identity_across_refreshes(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    source, _path, _state = upsert_source(storage.data, "getcourse", "https://school.example/course", "GetCourse Stable Identity")

    first = sync_browser_fixture_sources(
        storage,
        sync_run_id="browser-stable-refresh-a",
        platforms=["getcourse"],
        source_ids=[str(source["source_id"])],
        build_artifacts=True,
    )
    second = sync_browser_fixture_sources(
        storage,
        sync_run_id="browser-stable-refresh-b",
        platforms=["getcourse"],
        source_ids=[str(source["source_id"])],
        build_artifacts=True,
    )

    first_checkpoint = first["synced_sources"][0]
    second_checkpoint = second["synced_sources"][0]
    assert first_checkpoint["run_id"] != second_checkpoint["run_id"]
    assert first_checkpoint["stable_identity"]["fingerprint"] == second_checkpoint["stable_identity"]["fingerprint"]
    assert first_checkpoint["stable_identity"]["samples"] == second_checkpoint["stable_identity"]["samples"]
    assert first_checkpoint["stable_identity"]["counts"] == second_checkpoint["stable_identity"]["counts"]

    first_packet = render_answer_packet(storage, "GetCourse bootloader rollback evidence", run_id=str(first_checkpoint["run_id"]), mode="hybrid")
    second_packet = render_answer_packet(storage, "GetCourse bootloader rollback evidence", run_id=str(second_checkpoint["run_id"]), mode="hybrid")
    assert first_packet["results"][0]["source_id"] == second_packet["results"][0]["source_id"] == source["source_id"]
    assert first_packet["results"][0]["lesson_id"] == second_packet["results"][0]["lesson_id"]
    assert first_packet["evidence_chain"][0]["evidence_id"] == second_packet["evidence_chain"][0]["evidence_id"]


def test_browser_fixture_sync_rejects_invalid_sync_run_id_before_checkpoint_write(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    source, _path, _state = upsert_source(storage.data, "getcourse", "https://school.example", "School")

    with pytest.raises(ValueError, match="sync_run_id must be a portable runtime id"):
        sync_browser_fixture_sources(
            storage,
            sync_run_id="../bad-sync",
            platforms=["getcourse"],
            source_ids=[str(source["source_id"])],
        )

    assert not checkpoint_store_path(storage).exists()
    assert not (storage.data / "sync").exists()


def test_refresh_live_cycle_uses_selected_source_readiness_and_default_browser_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = roots(tmp_path)
    selected, _path, _state = upsert_source(storage.data, "getcourse", "https://school.operator.edu/course", "School")
    upsert_source(storage.data, "getcourse", "https://other.operator.edu/course", "Other School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "secret", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "secret"}]}],
        }),
        encoding="utf-8",
    )
    initial = sync_browser_fixture_sources(
        storage,
        sync_run_id="browser-refresh-initial",
        platforms=["getcourse"],
        source_ids=[str(selected["source_id"])],
        build_artifacts=True,
    )
    initial_run = str(initial["synced_sources"][0]["run_id"])
    build_semantic_index(storage, run_id=initial_run)
    captured: dict[str, object] = {}

    def fake_live_sync(*args, **kwargs):
        captured["state_file"] = kwargs.get("state_file")
        captured["source_ids"] = kwargs.get("source_ids")
        fixture_kwargs = dict(kwargs)
        fixture_kwargs.pop("state_file", None)
        return sync_browser_fixture_sources(*args, **fixture_kwargs)

    monkeypatch.setattr(refresh_module, "sync_browser_live_sources", fake_live_sync)

    report = refresh_module.refresh_query_cycle(
        storage,
        "GetCourse bootloader rollback evidence",
        run_id=initial_run,
        mode="hybrid",
        strategy="live",
        execute=True,
        allow_network=True,
        sync_run_id="browser-live-refresh",
    )

    assert report["status"] == "ok"
    assert report["selected_result"]["source_id"] == selected["source_id"]
    assert any("lesson-context" in command and "--mode hybrid" in command for command in report["planned_commands"]["local_query_commands"])
    assert captured["source_ids"] == [selected["source_id"]]
    assert captured["state_file"] == state_file.resolve()
    assert report["rebuilt_artifacts"]["semantic_index_path"]


def test_refresh_live_ready_requires_selected_smoke_ready() -> None:
    plan = {
        "ready": False,
        "source_plans": [
            {
                "source_id": "source:stepik:broken",
                "ready": True,
                "sync_command": "aoa-course sync stepik-live --source-id source:stepik:broken",
                "smoke_command": None,
            }
        ],
        "stages": [
            {
                "name": "live_smoke",
                "actions": [
                    {
                        "source_id": "source:stepik:broken",
                        "ready": False,
                        "blocked_by": ["cannot parse Stepik course id from source_ref"],
                    }
                ],
            }
        ],
    }

    assert refresh_module._selected_source_live_ready(plan, "source:stepik:broken") is False


def test_sync_checkpoints_keep_per_run_source_history(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    source = {
        "source_id": "source:getcourse:test",
        "platform": "getcourse",
        "source_ref": "https://school.example",
        "access_mode": "browser_session",
    }
    first = make_checkpoint(source=source, sync_run_id="sync-a", run_id="sync-a-source", status="ok")
    second = make_checkpoint(source=source, sync_run_id="sync-b", run_id="sync-b-source", status="ok")
    retry = make_checkpoint(
        source=source,
        sync_run_id="sync-a",
        run_id="sync-a-source-retry",
        status="error",
        error="temporary fixture miss",
    )

    upsert_checkpoint(storage, first)
    upsert_checkpoint(storage, second)
    upsert_checkpoint(storage, retry)

    sync_a = load_sync_status(storage, sync_run_id="sync-a")
    sync_b = load_sync_status(storage, sync_run_id="sync-b")
    all_status = load_sync_status(storage)

    assert first["checkpoint_id"] == "checkpoint:sync-a:source:getcourse:test"
    assert second["checkpoint_id"] == "checkpoint:sync-b:source:getcourse:test"
    assert sync_a["checkpoint_count"] == 1
    assert sync_a["error_count"] == 1
    assert sync_a["checkpoints"][0]["run_id"] == "sync-a-source-retry"
    assert sync_b["checkpoint_count"] == 1
    assert sync_b["ok_count"] == 1
    assert sync_b["checkpoints"][0]["run_id"] == "sync-b-source"
    assert all_status["checkpoint_count"] == 2


def test_browser_fixture_sync_can_target_one_source_id(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    first, _path, _state = upsert_source(storage.data, "getcourse", "https://school.example/one", "One")
    second, _path, _state = upsert_source(storage.data, "getcourse", "https://school.example/two", "Two")

    receipt = sync_browser_fixture_sources(
        storage,
        sync_run_id="browser-source-scoped-sync",
        platforms=["getcourse"],
        source_ids=[str(second["source_id"])],
        build_artifacts=True,
    )

    assert receipt["status"] == "ok"
    assert receipt["source_count"] == 1
    assert receipt["synced_count"] == 1
    assert receipt["synced_sources"][0]["source_id"] == second["source_id"]
    assert receipt["synced_sources"][0]["source_id"] != first["source_id"]


def test_browser_live_sync_preserves_registry_source_in_answer_refresh_hints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = roots(tmp_path)
    source, _path, _state = upsert_source(storage.data, "getcourse", "https://school.operator.edu/course", "Operator School")
    captured: dict[str, object] = {}

    def fake_crawl_browser_live(*args, **kwargs):
        roots_arg = args[0]
        run_id = str(kwargs["run_id"])
        crawl_source = kwargs.get("source")
        captured["source"] = crawl_source
        raw = {
            "schema": "aoa_course_browser_snapshot_v1",
            "platform": "getcourse",
            "captured_at": "2026-07-07T00:00:00Z",
            "source": crawl_source,
            "pages": [
                {
                    "page_id": "course-index",
                    "kind": "course_index",
                    "url": source["source_ref"],
                    "title": "Operator School",
                    "html": "<main><a data-aoa-kind='lesson' href='/lesson/one'>Lesson</a></main>",
                },
                {
                    "page_id": "lesson-one",
                    "kind": "lesson",
                    "url": "https://school.operator.edu/lesson/one",
                    "title": "Registry-backed live lesson",
                    "html": "<article><h1>Registry-backed live lesson</h1><p>bootloader rollback registry marker</p></article>",
                },
            ],
        }
        return _materialize_browser_raw(
            roots_arg,
            run_id=run_id,
            source_mode="getcourse_browser_live_crawl",
            raw=raw,
            raw_name="getcourse_browser_live_crawl_snapshot.json",
            network_touched=True,
        )

    monkeypatch.setattr(browser_sync_module, "crawl_browser_live", fake_crawl_browser_live)

    receipt = browser_sync_module.sync_browser_live_sources(
        storage,
        sync_run_id="browser-live-source-preservation",
        platforms=["getcourse"],
        source_ids=[str(source["source_id"])],
        build_artifacts=True,
    )

    checkpoint = receipt["synced_sources"][0]
    packet = render_answer_packet(storage, "bootloader rollback registry marker", run_id=str(checkpoint["run_id"]), mode="hybrid")
    hint = packet["results"][0]["refresh_hint"]

    assert captured["source"]["source_id"] == source["source_id"]
    assert checkpoint["stable_identity"]["samples"]["source_ids"] == [source["source_id"]]
    assert packet["results"][0]["source_id"] == source["source_id"]
    assert packet["evidence_chain"][0]["source_id"] == source["source_id"]
    assert hint["registry_match"] is True
    assert hint["source_refresh"]["registry_match"] is True
    assert f"--source-id {source['source_id']}" in hint["source_refresh"]["sync_command"]
