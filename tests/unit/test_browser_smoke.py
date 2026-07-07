from __future__ import annotations

from pathlib import Path

import pytest

import aoa_course_connector.smoke.browser_session as browser_smoke_module
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.ingest.browser_session import _materialize_browser_raw
from aoa_course_connector.smoke import smoke_browser_fixture, smoke_browser_snapshot
from aoa_course_connector.sources import upsert_source


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_browser_fixture_smoke_builds_artifacts_and_answer(tmp_path: Path) -> None:
    report = smoke_browser_fixture(roots(tmp_path), platform="getcourse", run_id="getcourse-smoke-fixture")

    assert report["status"] == "ok"
    assert report["network_touched"] is False
    assert report["discovery"]["course_count"] == 3
    assert report["discovery"]["next_link_count"] == 1
    assert report["course"]["lesson_count"] >= 2
    assert report["course"]["progress_detected_count"] == 1
    assert report["course"]["comment_count"] >= 1
    assert len(report["snapshot_audits"]) == 2
    assert {audit["status"] for audit in report["snapshot_audits"]} == {"ok"}
    assert any(audit["readiness"]["ready_for_discovery"] for audit in report["snapshot_audits"])
    assert any(audit["readiness"]["ready_for_materialize"] for audit in report["snapshot_audits"])
    assert report["snapshot_audits"][0]["privacy"]["raw_html_included"] is False
    assert report["artifacts"]["enabled"] is True
    assert report["artifacts"]["answer"]["result_count"] >= 1
    assert report["artifacts"]["answer"]["quality"]["ready"] is True
    assert report["artifacts"]["answer"]["quality"]["expected_platform"] == "getcourse"
    assert report["artifacts"]["answer"]["quality"]["expected_platform_match_count"] == report["artifacts"]["answer"]["result_count"]
    assert report["artifacts"]["answer"]["quality"]["provenance_complete_count"] == report["artifacts"]["answer"]["result_count"]
    assert report["privacy"]["do_not_commit_raw_html_or_auth_state"] is True


def test_browser_snapshot_smoke_accepts_catalog_and_course_snapshots(tmp_path: Path) -> None:
    repo = find_repo_root()
    report = smoke_browser_snapshot(
        roots(tmp_path),
        platform="skillspace",
        run_id="skillspace-smoke-snapshot",
        catalog_snapshot=repo / "connector/fixtures/browser/skillspace_catalog_snapshot.json",
        course_snapshot=repo / "connector/fixtures/browser/skillspace_starter_snapshot.json",
        query="timestamp window reproduction step",
    )

    assert report["status"] == "ok"
    assert report["source_mode"] == "browser_snapshot_smoke"
    assert report["discovery"]["course_count"] == 3
    assert report["course"]["comment_count"] >= 1
    assert len(report["snapshot_audits"]) == 2
    assert report["snapshot_audits"][0]["source_schema"] == "aoa_course_browser_snapshot_audit_v1"
    assert report["snapshot_audits"][1]["readiness"]["ready_for_materialize"] is True
    assert report["artifacts"]["answer"]["evidence_count"] >= 1
    assert report["artifacts"]["answer"]["quality"]["ready"] is True


def test_browser_snapshot_smoke_flags_catalog_only_query_without_course_materialization(tmp_path: Path) -> None:
    repo = find_repo_root()
    report = smoke_browser_snapshot(
        roots(tmp_path),
        platform="skillspace",
        run_id="skillspace-catalog-only-query",
        catalog_snapshot=repo / "connector/fixtures/browser/skillspace_catalog_snapshot.json",
        query="timestamp window reproduction step",
    )

    assert report["status"] == "partial"
    assert len(report["snapshot_audits"]) == 1
    assert report["snapshot_audits"][0]["readiness"]["ready_for_discovery"] is True
    assert report["snapshot_audits"][0]["readiness"]["ready_for_materialize"] is False
    assert report["course"] == {"enabled": False}
    assert report["artifacts"]["status"] == "not_run_no_course_materialized"
    assert report["artifacts"]["answer"]["status"] == "blocked_no_course_materialized"
    assert report["artifacts"]["answer"]["result_count"] == 0
    assert {
        "surface": "answer",
        "reason": "query requested without course materialization",
        "query": "timestamp window reproduction step",
    } in report["failures"]


def test_browser_snapshot_smoke_requires_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="provide --catalog-snapshot"):
        smoke_browser_snapshot(roots(tmp_path), platform="getcourse", run_id="empty-smoke")


def test_browser_live_smoke_preserves_registry_source_in_report_and_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
                    "html": "<article><h1>Registry-backed live lesson</h1><p>live smoke registry marker</p></article>",
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

    monkeypatch.setattr(browser_smoke_module, "crawl_browser_live", fake_crawl_browser_live)

    report = browser_smoke_module.smoke_browser_live(
        storage,
        platform="getcourse",
        run_id="browser-live-source-smoke",
        course_url=str(source["source_ref"]),
        query="live smoke registry marker",
        source=source,
    )

    assert captured["source"]["source_id"] == source["source_id"]
    assert report["status"] == "ok"
    assert report["source"]["source_id"] == source["source_id"]
    assert report["source"]["registry_backed"] is True
    assert report["artifacts"]["answer"]["quality"]["top_result"]["source_id"] == source["source_id"]
