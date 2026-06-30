from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.adapters.browser import parse_html_snapshot
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
    bundle = json.loads((storage.data / "runs/getcourse-browser-fixture/normalized/course_bundle.json").read_text(encoding="utf-8"))
    course = bundle["courses"][0]
    assert course["progress"]["state"] == "in_progress"
    assert course["progress"]["percent"] == "50"
    assert course["progress"]["label"] == "2 of 4 lessons completed"
    bootloader_lesson = course["modules"][0]["lessons"][0]
    assert bootloader_lesson["comment_threads"][0]["comments"][0]["author_label"] == "mentor"
    assert "anti-rollback level" in bootloader_lesson["comment_threads"][0]["comments"][0]["text"]
    build_keyword_index(storage, run_id="getcourse-browser-fixture")
    graph_path = build_graph(storage, run_id="getcourse-browser-fixture")
    results = query_keyword_index(storage, "GetCourse bootloader rollback evidence", run_id="getcourse-browser-fixture")
    assert results
    assert results[0]["platform"] == "getcourse"
    comment_results = query_keyword_index(storage, "mentor anti-rollback vendor boot", run_id="getcourse-browser-fixture")
    assert any(result["kind"] == "comment" and "Mentor note" in result["text"] for result in comment_results)
    progress_results = query_keyword_index(storage, "2 of 4 lessons completed in_progress", run_id="getcourse-browser-fixture")
    assert any(result["kind"] == "progress" for result in progress_results)
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    edge_kinds = {edge["kind"] for edge in graph["edges"]}
    assert "course_has_progress" in edge_kinds
    assert "lesson_has_comment_thread" in edge_kinds
    assert "thread_has_comment" in edge_kinds
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
    comment_results = query_keyword_index(storage, "timestamp window reproduction step", run_id="skillspace-browser-fixture")
    assert any(result["kind"] == "comment" and "timestamp window" in result["text"] for result in comment_results)
    progress_results = query_keyword_index(storage, "75 percent reviewed", run_id="skillspace-browser-fixture")
    assert any(result["kind"] == "progress" for result in progress_results)
    packet = render_answer_packet(storage, "Skillspace logcat bugreport evidence", run_id="skillspace-browser-fixture")
    assert packet["evidence_chain"]


def test_browser_snapshot_preserves_unannotated_asset_links() -> None:
    snapshot = parse_html_snapshot(
        """
        <main>
          <a href="/lesson">ordinary lesson link</a>
          <a href="/files/intro.pdf">Intro PDF</a>
          <a href="/files/archive.zip" download>Archive</a>
        </main>
        """,
        "https://school.example/course/",
    )

    assert [link["href"] for link in snapshot.links] == [
        "https://school.example/lesson",
        "https://school.example/files/intro.pdf",
        "https://school.example/files/archive.zip",
    ]
    assert {asset["url"] for asset in snapshot.assets} == {
        "https://school.example/files/intro.pdf",
        "https://school.example/files/archive.zip",
    }


def test_browser_snapshot_extracts_progress_comments_and_pagination() -> None:
    snapshot = parse_html_snapshot(
        """
        <main>
          <div data-aoa-kind="progress" data-aoa-progress-state="done" data-aoa-progress-percent="100">Complete</div>
          <article data-aoa-kind="comment" data-aoa-thread-id="qna" data-aoa-comment-id="c1" data-aoa-author="mentor" data-aoa-created-at="2026-06-29T00:00:00Z">
            Keep the evidence chain with the course note.
          </article>
          <a rel="next" href="/courses?page=2">Next page</a>
        </main>
        """,
        "https://academy.example/courses",
    )

    assert snapshot.progress == {
        "state": "done",
        "percent": "100",
        "updated_at": "",
        "label": "Complete",
    }
    assert snapshot.comments == [
        {
            "comment_id": "c1",
            "thread_id": "qna",
            "author": "mentor",
            "created_at": "2026-06-29T00:00:00Z",
            "text": "Keep the evidence chain with the course note.",
        }
    ]
    assert snapshot.pagination_links[0]["href"] == "https://academy.example/courses?page=2"


def test_browser_snapshot_uses_unannotated_progress_and_comment_hints() -> None:
    snapshot = parse_html_snapshot(
        """
        <main>
          <div class="course-progress progress-bar" role="progressbar" aria-valuenow="75">75% complete</div>
          <article class="lesson-comment reply" id="comment-42">
            Mentor says keep the radio logs and bugreport together.
          </article>
        </main>
        """,
        "https://academy.example/course/mobile-debugging",
    )

    assert snapshot.progress == {
        "state": "in_progress",
        "percent": "75",
        "updated_at": "",
        "label": "75% complete",
    }
    assert snapshot.comments == [
        {
            "comment_id": "comment-42",
            "thread_id": "visible-thread",
            "author": "",
            "created_at": "",
            "text": "Mentor says keep the radio logs and bugreport together.",
        }
    ]


def test_browser_snapshot_reads_aria_only_progressbar() -> None:
    snapshot = parse_html_snapshot(
        '<main><div class="progressbar" role="progressbar" aria-valuenow="60" aria-valuetext="60 percent reviewed"></div></main>',
        "https://academy.example/course/mobile-debugging",
    )

    assert snapshot.progress == {
        "state": "visible",
        "percent": "60",
        "updated_at": "",
        "label": "60 percent reviewed",
    }
