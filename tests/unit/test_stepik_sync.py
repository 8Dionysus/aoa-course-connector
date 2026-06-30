from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.index import build_semantic_index
from aoa_course_connector.mcp.server import call_tool
from aoa_course_connector.query import render_answer_packet
from aoa_course_connector.refresh import refresh_query_cycle
from aoa_course_connector.sources import upsert_source
from aoa_course_connector.sync import load_sync_status, sync_stepik_fixture_sources
from aoa_course_connector.sync.stepik import parse_stepik_course_id


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_parse_stepik_course_id_from_id_and_url() -> None:
    assert parse_stepik_course_id("67") == 67
    assert parse_stepik_course_id("https://stepik.org/course/67/syllabus") == 67
    assert parse_stepik_course_id("stepik.org/course/100") == 100


def test_stepik_fixture_sync_writes_checkpoints_and_artifacts(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    source, _path, state = upsert_source(storage.data, "stepik", "67", "Stepik Sync Fixture", access_mode="public_api")
    assert state == "added"
    receipt = sync_stepik_fixture_sources(
        storage,
        sync_run_id="stepik-sync-fixture",
        source_limit=1,
        build_artifacts=True,
    )
    assert receipt["status"] == "ok"
    assert receipt["synced_count"] == 1
    checkpoint = receipt["synced_sources"][0]
    assert checkpoint["source_id"] == source["source_id"]
    assert checkpoint["platform"] == "stepik"
    assert checkpoint["status"] == "ok"
    assert checkpoint["normalized_path"]
    assert checkpoint["index_path"]
    assert checkpoint["graph_path"]
    raw = json.loads(Path(str(checkpoint["cursor"])).read_text(encoding="utf-8"))
    assert raw["source"]["source_id"] == source["source_id"]
    assert raw["source"]["source_ref"] == "67"
    status = load_sync_status(storage, sync_run_id="stepik-sync-fixture", platform="stepik")
    assert status["ok_count"] == 1
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))
    mcp_status = call_tool("sync_status", {"sync_run": "stepik-sync-fixture", "platform": "stepik"})
    assert mcp_status["sync"]["ok_count"] == 1
    packet = render_answer_packet(storage, "Stepik public API evidence", run_id=checkpoint["run_id"])
    assert packet["result_count"] >= 1
    assert packet["evidence_chain"]
    hint = packet["results"][0]["refresh_hint"]
    assert hint["platform"] == "stepik"
    assert hint["registry_match"] is True
    assert hint["source_refresh"]["access_mode"] == "public_api"
    assert "preflight connected-plan --platform stepik" in hint["source_refresh"]["preflight_command"]
    assert "sync stepik-live" in hint["source_refresh"]["sync_command"]
    assert f"--source-id {source['source_id']}" in hint["source_refresh"]["sync_command"]
    assert packet["refresh_report"]["registry_matched_source_count"] == 1


def test_stepik_fixture_sync_records_bad_source_ref(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "stepik", "not-a-course", "Broken Stepik Source", access_mode="public_api")
    receipt = sync_stepik_fixture_sources(storage, sync_run_id="stepik-bad-source")
    assert receipt["status"] == "error"
    assert receipt["failed_count"] == 1
    checkpoint = receipt["failed_sources"][0]
    assert checkpoint["platform"] == "stepik"
    assert "cannot parse Stepik course id" in checkpoint["error"]


def test_stepik_fixture_sync_can_target_one_source_id(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    first, _path, _state = upsert_source(storage.data, "stepik", "67", "Fixture Stepik Source", access_mode="public_api")
    second, _path, _state = upsert_source(storage.data, "stepik", "not-a-course", "Broken Stepik Source", access_mode="public_api")

    receipt = sync_stepik_fixture_sources(
        storage,
        sync_run_id="stepik-source-scoped-sync",
        source_ids=[str(first["source_id"])],
        build_artifacts=True,
    )

    assert receipt["status"] == "ok"
    assert receipt["source_count"] == 1
    assert receipt["synced_count"] == 1
    assert receipt["failed_count"] == 0
    assert receipt["synced_sources"][0]["source_id"] == first["source_id"]
    assert receipt["synced_sources"][0]["source_id"] != second["source_id"]


def test_stepik_fixture_sync_rejects_parseable_non_fixture_course(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    source, _path, _state = upsert_source(
        storage.data,
        "stepik",
        "https://stepik.org/course/100/syllabus",
        "Different Stepik Source",
        access_mode="public_api",
    )

    receipt = sync_stepik_fixture_sources(storage, sync_run_id="stepik-wrong-fixture")

    assert receipt["status"] == "error"
    assert receipt["synced_count"] == 0
    assert receipt["failed_count"] == 1
    checkpoint = receipt["failed_sources"][0]
    assert checkpoint["source_id"] == source["source_id"]
    assert checkpoint["platform"] == "stepik"
    assert "stepik-fixture sync only supports fixture course 67" in checkpoint["error"]
    assert "stepik-live sync for course 100" in checkpoint["error"]


def test_refresh_fixture_cycle_executes_selected_stepik_source(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    source, _path, _state = upsert_source(storage.data, "stepik", "67", "Stepik Refresh Fixture", access_mode="public_api")
    initial = sync_stepik_fixture_sources(
        storage,
        sync_run_id="stepik-refresh-initial",
        source_ids=[str(source["source_id"])],
        build_artifacts=True,
    )
    initial_run = initial["synced_sources"][0]["run_id"]
    build_semantic_index(storage, run_id=str(initial_run))

    report = refresh_query_cycle(
        storage,
        "Stepik public API evidence",
        run_id=str(initial_run),
        mode="hybrid",
        strategy="fixture",
        execute=True,
        sync_run_id="stepik-refresh-cycle",
    )

    assert report["schema"] == "aoa_course_refresh_cycle_v1"
    assert report["status"] == "ok"
    assert report["network_touched"] is False
    assert report["selected_result"]["source_id"] == source["source_id"]
    assert report["checkpoint"]["source_id"] == source["source_id"]
    assert report["refreshed_run_id"]
    assert report["rebuilt_artifacts"]["semantic_index_path"]
    assert report["refreshed_answer_packet"]["result_count"] >= 1
    assert report["comparison"]["source_id_preserved"] is True
