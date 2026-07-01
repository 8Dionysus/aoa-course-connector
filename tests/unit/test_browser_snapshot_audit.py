from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.adapters.browser import audit_browser_snapshot_file
from aoa_course_connector.config import find_repo_root


def test_browser_snapshot_audit_proves_course_snapshot_without_raw_payloads() -> None:
    repo = find_repo_root()
    report = audit_browser_snapshot_file(
        repo / "connector/fixtures/browser/getcourse_starter_snapshot.json",
        platform="getcourse",
    )

    assert report["schema"] == "aoa_course_browser_snapshot_audit_v1"
    assert report["status"] == "ok"
    assert report["network_touched"] is False
    assert report["privacy"]["raw_html_included"] is False
    assert report["readiness"]["ready_for_materialize"] is True
    assert report["readiness"]["ready_for_crawl"] is True
    assert report["counts"]["lesson_page_count"] == 2
    assert report["counts"]["lesson_link_count"] == 2
    assert report["counts"]["transcript_count"] == 1
    assert report["counts"]["caption_asset_count"] == 1
    assert report["counts"]["caption_resource_count"] == 1
    assert report["counts"]["caption_resource_parse_error_count"] == 0
    assert not report["failures"]
    assert any("materialize browser-snapshot" in command for command in report["next_commands"])
    assert "rollback index" not in json.dumps(report)


def test_browser_snapshot_audit_proves_catalog_discovery_snapshot() -> None:
    repo = find_repo_root()
    report = audit_browser_snapshot_file(
        repo / "connector/fixtures/browser/getcourse_catalog_snapshot.json",
        platform="getcourse",
    )

    assert report["status"] == "ok"
    assert report["readiness"]["ready_for_discovery"] is True
    assert report["readiness"]["ready_for_materialize"] is False
    assert report["counts"]["course_link_count"] == 3
    assert report["counts"]["pagination_link_count"] == 1
    assert report["page_kind_counts"]["account_catalog"] == 2
    assert any("discover browser-snapshot" in command for command in report["next_commands"])
    assert not any("materialize browser-snapshot" in command for command in report["next_commands"])


def test_browser_snapshot_audit_flags_missing_caption_resource(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "missing-caption-resource.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "schema": "aoa_course_browser_snapshot_v1",
                "platform": "skillspace",
                "captured_at": "2026-06-30T00:00:00Z",
                "source": {
                    "source_id": "source:skillspace:demo",
                    "platform": "skillspace",
                    "source_ref": "https://academy.example/course/demo",
                    "access_mode": "browser_session",
                },
                "pages": [
                    {
                        "page_id": "lesson-1",
                        "kind": "lesson",
                        "url": "https://academy.example/course/demo/lesson/1",
                        "title": "Protected captions",
                        "html": """
                        <article>
                          <h1>Protected captions</h1>
                          <p>Lesson text is visible.</p>
                          <video><track kind="subtitles" src="/captions/protected.vtt" srclang="en"></video>
                        </article>
                        """,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = audit_browser_snapshot_file(snapshot_path, platform="skillspace")

    assert report["status"] == "partial"
    assert report["readiness"]["ready_for_materialize"] is True
    assert report["counts"]["caption_asset_count"] == 1
    assert report["counts"]["caption_resource_missing_payload_count"] == 1
    assert any(failure["surface"] == "caption_sidecar" for failure in report["failures"])
    assert any(lane["lane"] == "caption_sidecar" for lane in report["repair_lanes"])
