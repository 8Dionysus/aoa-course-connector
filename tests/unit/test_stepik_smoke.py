from __future__ import annotations

from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.smoke import smoke_stepik_fixture
from aoa_course_connector.sources import upsert_source


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_stepik_fixture_smoke_builds_sync_artifacts_and_answer(tmp_path: Path) -> None:
    report = smoke_stepik_fixture(
        roots(tmp_path),
        course_id=67,
        run_id="stepik-smoke-fixture",
        title="Stepik smoke fixture",
        query="Stepik public API evidence",
    )

    assert report["schema"] == "aoa_course_stepik_smoke_report_v1"
    assert report["status"] == "ok"
    assert report["network_touched"] is False
    assert report["source"]["source_ref"] == "67"
    assert report["sync"]["status"] == "ok"
    assert report["sync"]["synced_count"] == 1
    assert report["course"]["course_count"] == 1
    assert report["course"]["module_count"] >= 1
    assert report["course"]["lesson_count"] >= 1
    assert report["course"]["step_count"] >= 1
    assert report["artifacts"]["enabled"] is True
    assert report["artifacts"]["answer"]["result_count"] >= 1
    assert report["artifacts"]["answer"]["evidence_count"] >= 1
    assert report["privacy"]["do_not_commit_raw_api_or_auth_state"] is True


def test_stepik_fixture_smoke_targets_registered_source_ref(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "stepik", "1", "Different Stepik Course", access_mode="public_api")

    report = smoke_stepik_fixture(storage, course_id=67, run_id="stepik-smoke-targeted")

    assert report["status"] == "ok"
    assert report["source"]["source_ref"] == "67"
    raw_paths = report["privacy"]["raw_paths"]
    assert len(raw_paths) == 1
    assert "stepik-smoke-targeted-source-stepik-1fa027c617" in raw_paths[0]
