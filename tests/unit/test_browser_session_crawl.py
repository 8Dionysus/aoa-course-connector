from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.adapters.browser.crawl import build_crawled_snapshot, discover_lesson_links
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index
from aoa_course_connector.ingest import crawl_browser_fixture
from aoa_course_connector.query import query_keyword_index, render_answer_packet


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_crawler_expands_getcourse_index_links() -> None:
    fixture = json.loads((find_repo_root() / "connector/fixtures/browser/getcourse_starter_snapshot.json").read_text(encoding="utf-8"))
    index_page = fixture["pages"][0]
    links = discover_lesson_links(index_page["html"], index_page["url"], max_lessons=10)
    assert [link["href"] for link in links] == [
        "https://school.example/teach/control/lesson/view/id/101",
        "https://school.example/teach/control/lesson/view/id/102",
    ]
    crawled = build_crawled_snapshot(fixture, platform="getcourse", max_lessons=1)
    assert crawled["crawl"]["discovered_lesson_count"] == 1
    assert len(crawled["pages"]) == 2
    assert crawled["pages"][1]["title"] == "Bootloader recovery lesson"


def test_getcourse_browser_crawl_fixture_to_answer_packet(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    receipt = crawl_browser_fixture(storage, "getcourse", run_id="getcourse-browser-crawl-fixture")
    assert receipt["status"] == "ok"
    assert receipt["crawl"]["discovered_lesson_count"] == 2
    build_keyword_index(storage, run_id="getcourse-browser-crawl-fixture")
    build_graph(storage, run_id="getcourse-browser-crawl-fixture")
    results = query_keyword_index(storage, "GetCourse bootloader rollback evidence", run_id="getcourse-browser-crawl-fixture")
    assert results
    assert results[0]["platform"] == "getcourse"
    packet = render_answer_packet(storage, "GetCourse bootloader rollback evidence", run_id="getcourse-browser-crawl-fixture")
    assert packet["evidence_chain"]


def test_skillspace_browser_crawl_fixture_to_answer_packet(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    receipt = crawl_browser_fixture(storage, "skillspace", run_id="skillspace-browser-crawl-fixture")
    assert receipt["status"] == "ok"
    assert receipt["crawl"]["discovered_lesson_count"] == 2
    build_keyword_index(storage, run_id="skillspace-browser-crawl-fixture")
    build_graph(storage, run_id="skillspace-browser-crawl-fixture")
    results = query_keyword_index(storage, "Skillspace logcat bugreport evidence", run_id="skillspace-browser-crawl-fixture")
    assert results
    assert results[0]["platform"] == "skillspace"
    packet = render_answer_packet(storage, "Skillspace logcat bugreport evidence", run_id="skillspace-browser-crawl-fixture")
    assert packet["evidence_chain"]
