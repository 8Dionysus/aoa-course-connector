"""Answer proof-field summaries for smoke and calibration reports."""

from __future__ import annotations

from typing import Any


REQUIRED_RESULT_FIELDS = ["source_id", "source_url", "fetched_at", "path", "authority_tier", "freshness_state"]
REQUIRED_EVIDENCE_FIELDS = ["source_id", "source_url", "fetched_at", "path"]


def summarize_answer_packet(packet: dict[str, object], *, expected_platform: str | None = None) -> dict[str, object]:
    """Return a compact proof-field summary for a source-backed answer packet."""

    results = [item for item in packet.get("results", []) if isinstance(item, dict)]
    evidence_chain = [item for item in packet.get("evidence_chain", []) if isinstance(item, dict)]
    expected = (expected_platform or "").casefold()
    result_counts = _field_counts(results, REQUIRED_RESULT_FIELDS)
    evidence_counts = _field_counts(evidence_chain, REQUIRED_EVIDENCE_FIELDS)
    platform_counts = _value_counts(result.get("platform") for result in results)
    expected_platform_match_count = sum(1 for result in results if str(result.get("platform") or "").casefold() == expected) if expected else 0
    provenance_complete_count = sum(1 for result in results if _rank_provenance_complete(result))
    refresh_hint_count = sum(1 for result in results if isinstance(result.get("refresh_hint"), dict))
    blockers = _quality_blockers(
        results=results,
        evidence_chain=evidence_chain,
        result_counts=result_counts,
        evidence_counts=evidence_counts,
        expected_platform=expected,
        expected_platform_match_count=expected_platform_match_count,
        provenance_complete_count=provenance_complete_count,
    )
    return {
        "schema": "aoa_course_answer_quality_summary_v1",
        "ready": not blockers,
        "blockers": blockers,
        "result_count": len(results),
        "evidence_count": len(evidence_chain),
        "platform_counts": platform_counts,
        "expected_platform": expected,
        "expected_platform_match_count": expected_platform_match_count,
        "provenance_complete_count": provenance_complete_count,
        "refresh_hint_count": refresh_hint_count,
        "result_field_counts": result_counts,
        "evidence_field_counts": evidence_counts,
        "top_result": _top_result_summary(results[0]) if results else {},
    }


def answer_quality_failures(answer: dict[str, object]) -> list[dict[str, object]]:
    """Convert a smoke answer quality summary into smoke-report failures."""

    if not answer.get("enabled"):
        return []
    quality = answer.get("quality") if isinstance(answer.get("quality"), dict) else {}
    if not quality or bool(quality.get("ready")):
        return []
    return [
        {
            "surface": "answer",
            "reason": "answer proof fields incomplete",
            "query": answer.get("query"),
            "blockers": quality.get("blockers", []),
        }
    ]


def _quality_blockers(
    *,
    results: list[dict[str, Any]],
    evidence_chain: list[dict[str, Any]],
    result_counts: dict[str, int],
    evidence_counts: dict[str, int],
    expected_platform: str,
    expected_platform_match_count: int,
    provenance_complete_count: int,
) -> list[str]:
    blockers: list[str] = []
    if not results:
        blockers.append("no_results")
    if not evidence_chain:
        blockers.append("no_evidence_chain")
    for field in REQUIRED_RESULT_FIELDS:
        if results and result_counts.get(field, 0) < len(results):
            blockers.append(f"result_missing_{field}")
    for field in REQUIRED_EVIDENCE_FIELDS:
        if evidence_chain and evidence_counts.get(field, 0) < len(evidence_chain):
            blockers.append(f"evidence_missing_{field}")
    if expected_platform and results and expected_platform_match_count < len(results):
        blockers.append("result_platform_mismatch")
    if results and provenance_complete_count < len(results):
        blockers.append("result_rank_provenance_incomplete")
    return blockers


def _field_counts(items: list[dict[str, Any]], fields: list[str]) -> dict[str, int]:
    return {field: sum(1 for item in items if _present(item.get(field))) for field in fields}


def _value_counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        text = str(value or "unknown")
        counts[text] = counts.get(text, 0) + 1
    return dict(sorted(counts.items()))


def _rank_provenance_complete(result: dict[str, Any]) -> bool:
    features = result.get("rank_features") if isinstance(result.get("rank_features"), dict) else {}
    return bool(features.get("provenance_complete"))


def _present(value: object) -> bool:
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return bool(value)


def _top_result_summary(result: dict[str, Any]) -> dict[str, object]:
    return {
        "doc_id": result.get("doc_id"),
        "source_id": result.get("source_id"),
        "source_url": result.get("source_url"),
        "fetched_at": result.get("fetched_at"),
        "platform": result.get("platform"),
        "path": result.get("path"),
        "authority_tier": result.get("authority_tier"),
        "freshness_state": result.get("freshness_state"),
        "rank_score": result.get("rank_score"),
    }
