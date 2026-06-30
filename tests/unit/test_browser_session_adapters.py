from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.adapters.browser import parse_html_snapshot
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index
from aoa_course_connector.ingest import materialize_browser_fixture
from aoa_course_connector.normalize.browser_session import normalize_browser_snapshot
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
    mentor_comment = bootloader_lesson["comment_threads"][0]["comments"][0]
    learner_comment = bootloader_lesson["comment_threads"][0]["comments"][1]
    assert mentor_comment["author_label"] == "mentor"
    assert mentor_comment["role"] == "mentor"
    assert mentor_comment["authority_tier"] == "mentor_comment"
    assert learner_comment["role"] == "learner"
    assert learner_comment["authority_tier"] == "learner_comment"
    assert bootloader_lesson["steps"][0]["authority_tier"] == "official_lesson"
    assert bootloader_lesson["assets"][0]["authority_tier"] == "asset_metadata"
    assert bootloader_lesson["assignments"][0]["authority_tier"] == "official_assignment"
    assert bootloader_lesson["transcripts"][0]["authority_tier"] == "transcript"
    assert bootloader_lesson["transcripts"][0]["source_authority"] == "browser_visible_transcript"
    assert "vendor boot image" in bootloader_lesson["transcripts"][0]["text"]
    assert "anti-rollback level" in mentor_comment["text"]
    build_keyword_index(storage, run_id="getcourse-browser-fixture")
    graph_path = build_graph(storage, run_id="getcourse-browser-fixture")
    results = query_keyword_index(storage, "GetCourse bootloader rollback evidence", run_id="getcourse-browser-fixture")
    assert results
    assert results[0]["platform"] == "getcourse"
    comment_results = query_keyword_index(storage, "mentor anti-rollback vendor boot", run_id="getcourse-browser-fixture")
    assert any(result["kind"] == "comment" and result["authority_tier"] == "mentor_comment" and "Mentor note" in result["text"] for result in comment_results)
    assert any(result["kind"] == "comment" and result["source_authority"] == "browser_visible_comment" for result in comment_results)
    transcript_results = query_keyword_index(storage, "transcript excerpt vendor boot recovery plan", run_id="getcourse-browser-fixture")
    assert any(result["kind"] == "transcript" and result["authority_tier"] == "transcript" and result["source_authority"] == "browser_visible_transcript" for result in transcript_results)
    progress_results = query_keyword_index(storage, "2 of 4 lessons completed in_progress", run_id="getcourse-browser-fixture")
    assert any(result["kind"] == "progress" for result in progress_results)
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    edge_kinds = {edge["kind"] for edge in graph["edges"]}
    assert "course_has_progress" in edge_kinds
    assert "lesson_has_transcript" in edge_kinds
    assert "lesson_has_comment_thread" in edge_kinds
    assert "thread_has_comment" in edge_kinds
    packet = render_answer_packet(storage, "GetCourse bootloader rollback evidence", run_id="getcourse-browser-fixture")
    assert packet["evidence_chain"]


def test_skillspace_browser_fixture_to_answer_packet(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    receipt = materialize_browser_fixture(storage, "skillspace", run_id="skillspace-browser-fixture")
    assert receipt["status"] == "ok"
    bundle = json.loads((storage.data / "runs/skillspace-browser-fixture/normalized/course_bundle.json").read_text(encoding="utf-8"))
    comment = bundle["courses"][0]["modules"][0]["lessons"][0]["comment_threads"][0]["comments"][0]
    transcript = bundle["courses"][0]["modules"][0]["lessons"][0]["transcripts"][0]
    assert comment["role"] == "mentor"
    assert comment["authority_tier"] == "mentor_comment"
    assert transcript["kind"] == "caption"
    assert transcript["authority_tier"] == "transcript"
    assert "bugreport timeline" in transcript["text"]
    build_keyword_index(storage, run_id="skillspace-browser-fixture")
    build_graph(storage, run_id="skillspace-browser-fixture")
    results = query_keyword_index(storage, "Skillspace logcat bugreport evidence", run_id="skillspace-browser-fixture")
    assert results
    assert results[0]["platform"] == "skillspace"
    comment_results = query_keyword_index(storage, "timestamp window reproduction step", run_id="skillspace-browser-fixture")
    assert any(result["kind"] == "comment" and "timestamp window" in result["text"] for result in comment_results)
    transcript_results = query_keyword_index(storage, "caption bugreport timeline", run_id="skillspace-browser-fixture")
    assert any(result["kind"] == "transcript" and "bugreport timeline" in result["text"] for result in transcript_results)
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
            "role": "",
            "authority_label": "",
            "created_at": "2026-06-29T00:00:00Z",
            "text": "Keep the evidence chain with the course note.",
        }
    ]
    assert snapshot.pagination_links[0]["href"] == "https://academy.example/courses?page=2"


def test_browser_snapshot_extracts_visible_transcripts_and_captions() -> None:
    snapshot = parse_html_snapshot(
        """
        <main>
          <section data-aoa-kind="transcript" data-aoa-transcript-id="t1" lang="en">
            Transcript excerpt: keep rollback index and vendor boot image evidence together.
          </section>
          <p class="lesson-caption" data-aoa-language="ru">
            Caption cue: attach the logcat timestamp window to reproduction steps.
          </p>
        </main>
        """,
        "https://academy.example/course/mobile-debugging",
    )

    assert snapshot.transcripts == [
        {
            "transcript_id": "t1",
            "language": "en",
            "kind": "transcript",
            "source_url": "",
            "text": "Transcript excerpt: keep rollback index and vendor boot image evidence together.",
        },
        {
            "transcript_id": "visible-transcript-2",
            "language": "ru",
            "kind": "transcript",
            "source_url": "",
            "text": "Caption cue: attach the logcat timestamp window to reproduction steps.",
        },
    ]


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
            "role": "",
            "authority_label": "",
            "created_at": "",
            "text": "Mentor says keep the radio logs and bugreport together.",
        }
    ]


def test_browser_snapshot_reads_comment_role_metadata() -> None:
    snapshot = parse_html_snapshot(
        """
        <main>
          <article data-aoa-kind="comment" data-aoa-comment-id="c2" data-aoa-author="Course Coach" data-aoa-author-role="instructor">
            Official staff clarification: use the signed recovery image.
          </article>
        </main>
        """,
        "https://academy.example/course/mobile-debugging",
    )

    assert snapshot.comments == [
        {
            "comment_id": "c2",
            "thread_id": "visible-thread",
            "author": "Course Coach",
            "role": "instructor",
            "authority_label": "",
            "created_at": "",
            "text": "Official staff clarification: use the signed recovery image.",
        }
    ]


def test_browser_comment_authority_label_drives_normalized_tier(tmp_path: Path) -> None:
    raw = {
        "platform": "getcourse",
        "captured_at": "2026-06-30T00:00:00Z",
        "source": {
            "source_id": "source:getcourse:demo",
            "platform": "getcourse",
            "source_ref": "https://school.example/course",
        },
        "pages": [
            {
                "kind": "lesson",
                "page_id": "authority-label",
                "url": "https://school.example/course/lesson",
                "html": """
                <main>
                  <h1>Authority label lesson</h1>
                  <article data-aoa-kind="comment" data-aoa-comment-id="c3" data-aoa-author="Jane Example" data-aoa-authority-label="mentor">
                    Check the rollback evidence before flashing.
                  </article>
                </main>
                """,
            }
        ],
    }

    bundle = normalize_browser_snapshot(raw, "authority-label", raw_ref="raw/browser_snapshot.json")
    comment = bundle["courses"][0]["modules"][0]["lessons"][0]["comment_threads"][0]["comments"][0]

    assert comment["author_label"] == "Jane Example"
    assert comment["role"] == ""
    assert comment["authority_label"] == "mentor"
    assert comment["authority_tier"] == "mentor_comment"


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


def test_browser_snapshot_reads_aria_valuenow_only_progressbar() -> None:
    snapshot = parse_html_snapshot(
        '<main><div class="progressbar" role="progressbar" aria-valuenow="40"></div></main>',
        "https://academy.example/course/mobile-debugging",
    )

    assert snapshot.progress == {
        "state": "visible",
        "percent": "40",
        "updated_at": "",
        "label": "40 percent",
    }


def test_browser_snapshot_keeps_not_started_progress_out_of_in_progress() -> None:
    snapshot = parse_html_snapshot(
        '<main><div class="progressbar" role="progressbar" aria-valuenow="0" aria-label="Not started"></div></main>',
        "https://academy.example/course/mobile-debugging",
    )

    assert snapshot.progress == {
        "state": "not_started",
        "percent": "0",
        "updated_at": "",
        "label": "Not started",
    }
