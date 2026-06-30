from __future__ import annotations

from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index
from aoa_course_connector.ingest import materialize_browser_fixture
from aoa_course_connector.query import query_keyword_index, render_answer_packet


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_getcourse_browser_fixture_to_answer_packet(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    receipt = materialize_browser_fixture(storage, "getcourse", run_id="getcourse-browser-fixture")
    assert receipt["status"] == "ok"
    build_keyword_index(storage, run_id="getcourse-browser-fixture")
    build_graph(storage, run_id="getcourse-browser-fixture")
    results = query_keyword_index(storage, "GetCourse bootloader rollback evidence", run_id="getcourse-browser-fixture")
    assert results
    assert results[0]["platform"] == "getcourse"
    packet = render_answer_packet(storage, "GetCourse bootloader rollback evidence", run_id="getcourse-browser-fixture")
    assert packet["evidence_chain"]


def test_skillspace_browser_fixture_to_answer_packet(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    receipt = materialize_browser_fixture(storage, "skillspace", run_id="skillspace-browser-fixture")
    assert receipt["status"] == "ok"
    build_keyword_index(storage, run_id="skillspace-browser-fixture")
    build_graph(storage, run_id="skillspace-browser-fixture")
    results = query_keyword_index(storage, "Skillspace logcat bugreport evidence", run_id="skillspace-browser-fixture")
    assert results
    assert results[0]["platform"] == "skillspace"
    packet = render_answer_packet(storage, "Skillspace logcat bugreport evidence", run_id="skillspace-browser-fixture")
    assert packet["evidence_chain"]
