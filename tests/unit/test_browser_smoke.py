from __future__ import annotations

from pathlib import Path

import pytest

from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.smoke import smoke_browser_fixture, smoke_browser_snapshot


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
    assert report["artifacts"]["enabled"] is True
    assert report["artifacts"]["answer"]["result_count"] >= 1
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
    assert report["artifacts"]["answer"]["evidence_count"] >= 1


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
