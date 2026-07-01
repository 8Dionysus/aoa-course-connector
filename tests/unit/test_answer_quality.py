from __future__ import annotations

from typing import Any

from aoa_course_connector.smoke.answer_quality import summarize_answer_packet


def complete_answer_packet(*, refresh_hint: object = None) -> dict[str, Any]:
    result = {
        "source_id": "source:stepik:67",
        "source_url": "https://stepik.org/course/67",
        "fetched_at": "2026-07-01T00:00:00Z",
        "path": "lesson.md",
        "authority_tier": "official",
        "freshness_state": "fresh",
        "rank_features": {"provenance_complete": True},
    }
    if refresh_hint is not None:
        result["refresh_hint"] = refresh_hint
    return {
        "results": [
            result
        ],
        "evidence_chain": [
            {
                "source_id": "source:stepik:67",
                "source_url": "https://stepik.org/course/67",
                "fetched_at": "2026-07-01T00:00:00Z",
                "path": "lesson.md",
            }
        ],
    }


def test_answer_quality_requires_refresh_hints_for_ready_results() -> None:
    summary = summarize_answer_packet(complete_answer_packet())

    assert summary["ready"] is False
    assert summary["refresh_hint_count"] == 0
    assert "result_missing_refresh_hint" in summary["blockers"]


def test_answer_quality_rejects_non_object_refresh_hints() -> None:
    summary = summarize_answer_packet(complete_answer_packet(refresh_hint="serialized-hint"))

    assert summary["ready"] is False
    assert summary["refresh_hint_count"] == 0
    assert "result_missing_refresh_hint" in summary["blockers"]
