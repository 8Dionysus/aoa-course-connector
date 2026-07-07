from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.adapters.browser.crawl import build_crawled_snapshot, discover_lesson_links
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index
from aoa_course_connector.ingest import crawl_browser_fixture, materialize_browser_snapshot
from aoa_course_connector.query import query_keyword_index, render_answer_packet
from aoa_course_connector.sources import upsert_source


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


def test_link_pattern_rejects_nonmatching_lesson_hints() -> None:
    html = """
    <main>
      <a href="/course/allowed/lesson-1">Allowed lesson</a>
      <a href="/course/noisy/lesson-2">Noisy lesson</a>
    </main>
    """

    links = discover_lesson_links(html, "https://school.example/", max_lessons=10, link_pattern="*/allowed/*")

    assert [link["href"] for link in links] == ["https://school.example/course/allowed/lesson-1"]


def test_getcourse_crawler_extracts_embedded_lesson_urls_without_stream_noise() -> None:
    html = """
    <main>
      <a href="/teach/control/stream/index">Training list</a>
      <script>
        window.gcLessons = [
          "/teach/control/lesson/view/id/334953645",
          "\\/teach\\/control\\/lesson\\/view\\/id\\/334953653",
          "/teach/control/lesson/view/id/334953645"
        ];
      </script>
      <div data-url="/teach/control/lesson/view/id/334953661">locked lesson</div>
    </main>
    """

    links = discover_lesson_links(html, "https://getcourse.ru/teach/control/stream/view/id/911642804", platform="getcourse", max_lessons=10)

    assert [link["href"] for link in links] == [
        "https://getcourse.ru/teach/control/lesson/view/id/334953645",
        "https://getcourse.ru/teach/control/lesson/view/id/334953653",
        "https://getcourse.ru/teach/control/lesson/view/id/334953661",
    ]


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


def test_crawl_placeholder_links_remain_discovery_evidence_in_query_and_graph(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    source_ref = "https://school.operator.edu/teach/control/stream"
    source, _path, _state = upsert_source(storage.data, "getcourse", source_ref, "Index Only School")
    raw = {
        "schema": "aoa_course_browser_snapshot_v1",
        "platform": "getcourse",
        "captured_at": "2026-07-06T00:00:00Z",
        "source": {
            "source_id": source["source_id"],
            "platform": "getcourse",
            "source_ref": source_ref,
            "access_mode": "browser_session",
            "title": "Index Only School",
        },
        "pages": [
            {
                "page_id": "index-only",
                "kind": "course_index",
                "url": "https://school.operator.edu/teach/control/stream",
                "title": "Index Only School",
                "html": """
                <main>
                  <a data-aoa-kind="lesson" data-aoa-module="Recovery" href="/teach/control/lesson/view/id/777">
                    Unfetched modem rollback lesson
                  </a>
                </main>
                """,
            }
        ],
    }
    crawled = build_crawled_snapshot(raw, platform="getcourse")
    raw_path = tmp_path / "index-only-crawl.json"
    raw_path.write_text(json.dumps(crawled), encoding="utf-8")

    materialize_browser_snapshot(storage, raw_path, platform="getcourse", run_id="index-only-crawl")
    bundle = json.loads((storage.data / "runs/index-only-crawl/normalized/course_bundle.json").read_text(encoding="utf-8"))
    lesson = bundle["courses"][0]["modules"][0]["lessons"][0]
    step = lesson["steps"][0]
    assert lesson["freshness_state"] == "discovered_not_fetched"
    assert step["kind"] == "browser_discovered_link"
    assert step["authority_tier"] == "discovered_link"
    assert step["source_authority"] == "browser_course_index_link"

    build_keyword_index(storage, run_id="index-only-crawl")
    graph_path = build_graph(storage, run_id="index-only-crawl")
    results = query_keyword_index(storage, "unfetched modem rollback", run_id="index-only-crawl")
    assert results
    assert results[0]["freshness_state"] == "discovered_not_fetched"
    assert results[0]["authority_tier"] == "discovered_link"
    assert results[0]["rank_features"]["freshness_boost"] < 0
    assert results[0]["rank_features"]["authority_boost"] < 0
    packet = render_answer_packet(storage, "unfetched modem rollback", run_id="index-only-crawl")
    assert packet["evidence_chain"][0]["freshness_state"] == "discovered_not_fetched"
    assert packet["evidence_chain"][0]["authority_tier"] == "discovered_link"
    assert packet["refresh_report"]["commands_touch_network"] is True

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    lesson_node = next(node for node in graph["nodes"] if node["node_id"] == lesson["lesson_id"])
    step_node = next(node for node in graph["nodes"] if node["node_id"] == step["step_id"])
    assert lesson_node["freshness_state"] == "discovered_not_fetched"
    assert step_node["authority_tier"] == "discovered_link"
    assert step_node["source_authority"] == "browser_course_index_link"
    assert any(edge["kind"] == "module_contains_lesson" and edge["confidence"] == 0.45 for edge in graph["edges"])
