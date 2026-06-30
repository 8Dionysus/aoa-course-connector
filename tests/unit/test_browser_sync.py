from __future__ import annotations

from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.discover import discover_browser_fixture
from aoa_course_connector.query import render_answer_packet
from aoa_course_connector.sync import load_sync_status, sync_browser_fixture_sources


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
    assert checkpoint["graph_path"]
    status = load_sync_status(storage, sync_run_id="browser-sync-fixture", platform="getcourse")
    assert status["ok_count"] == 1
    packet = render_answer_packet(storage, "GetCourse bootloader rollback evidence", run_id=checkpoint["run_id"])
    assert packet["result_count"] >= 1
    assert packet["evidence_chain"]
