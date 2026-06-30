"""Live calibration packet helpers.

Calibration packets summarize smoke/preflight reports without embedding raw
private source data. They are runtime artifacts: useful for operator handoff and
agent checks, but not central proof verdicts.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.storage import run_artifact_dir


SECRET_MARKERS = [
    "SUPER_SECRET",
    "PRIVATE_COOKIE",
    "PRIVATE_TOKEN",
    "gho_",
    "sk-",
]

RAW_PAYLOAD_KEYS = {
    "apikey",
    "apisecret",
    "accesstoken",
    "authkey",
    "authtoken",
    "apitoken",
    "authorization",
    "bearertoken",
    "clientsecret",
    "credential",
    "credentials",
    "cookie",
    "cookies",
    "html",
    "localstorage",
    "pagehtml",
    "password",
    "rawhtml",
    "refreshtoken",
    "secret",
    "secretkey",
    "sessionkey",
    "storagestate",
    "token",
    "tokenvalue",
}

SECRET_PAYLOAD_KEYS = {
    "apikey",
    "apisecret",
    "accesstoken",
    "authkey",
    "authtoken",
    "apitoken",
    "authorization",
    "bearertoken",
    "clientsecret",
    "credential",
    "credentials",
    "password",
    "refreshtoken",
    "secret",
    "secretkey",
    "sessionkey",
    "token",
    "tokenvalue",
}


def load_json_report(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_live_calibration_packet(
    *,
    run_id: str,
    smoke_reports: list[dict[str, object]],
    preflight_reports: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    preflight_reports = preflight_reports or []
    smoke_summaries = [_smoke_summary(report) for report in smoke_reports]
    preflight_summaries = [_preflight_summary(report) for report in preflight_reports]
    failures: list[dict[str, object]] = []
    if not smoke_summaries:
        failures.append({"surface": "smoke_reports", "reason": "no smoke reports supplied"})
    for summary in smoke_summaries:
        failures.extend(_smoke_failures(summary))
    for summary in preflight_summaries:
        failures.extend(_preflight_failures(summary))
    raw_payload_failures = _raw_payload_failures([*smoke_reports, *preflight_reports])
    secret_failures = _secret_failures([*smoke_reports, *preflight_reports])
    failures.extend(raw_payload_failures)
    failures.extend(secret_failures)
    platforms = sorted({str(summary.get("platform") or "") for summary in smoke_summaries if summary.get("platform")})
    source_modes = sorted({str(summary.get("source_mode") or "") for summary in smoke_summaries if summary.get("source_mode")})
    answer_result_total = sum(int(summary.get("answer_result_count") or 0) for summary in smoke_summaries)
    answer_evidence_total = sum(int(summary.get("answer_evidence_count") or 0) for summary in smoke_summaries)
    transcript_count_total = sum(int(summary.get("transcript_count") or 0) for summary in smoke_summaries)
    caption_sidecar_count_total = sum(int(summary.get("caption_sidecar_count") or 0) for summary in smoke_summaries)
    caption_resource_error_count_total = sum(int(summary.get("caption_resource_error_count") or 0) for summary in smoke_summaries)
    transcript_source_authority_counts = _sum_count_maps(summary.get("transcript_source_authority_counts") for summary in smoke_summaries)
    network_touched = any(bool(summary.get("network_touched")) for summary in smoke_summaries)
    return {
        "schema": "aoa_course_live_calibration_packet_v1",
        "status": "ok" if not failures else "partial",
        "run_id": run_id,
        "generated_at": _now(),
        "network_touched": network_touched,
        "platforms": platforms,
        "source_modes": source_modes,
        "report_count": len(smoke_summaries),
        "preflight_count": len(preflight_summaries),
        "smoke_reports": smoke_summaries,
        "preflight_reports": preflight_summaries,
        "quality": {
            "answer_result_count_total": answer_result_total,
            "answer_evidence_count_total": answer_evidence_total,
            "transcript_count_total": transcript_count_total,
            "caption_sidecar_count_total": caption_sidecar_count_total,
            "caption_resource_error_count_total": caption_resource_error_count_total,
            "transcript_source_authority_counts": transcript_source_authority_counts,
            "browser_report_count": sum(1 for summary in smoke_summaries if _is_browser_smoke(summary)),
            "browser_reports_with_transcripts": sum(1 for summary in smoke_summaries if _is_browser_smoke(summary) and int(summary.get("transcript_count") or 0) > 0),
            "all_answered_reports_have_evidence": all(
                not summary.get("answer_enabled") or int(summary.get("answer_evidence_count") or 0) > 0
                for summary in smoke_summaries
            ),
            "all_answered_reports_have_timestamps": all(
                not summary.get("answer_enabled") or bool(summary.get("has_source_timestamps"))
                for summary in smoke_summaries
            ),
        },
        "privacy": {
            "contains_raw_payloads": bool(raw_payload_failures),
            "contains_secret_values": bool(secret_failures),
            "raw_paths_are_local_runtime_state": all(bool(summary.get("raw_paths_are_local_runtime_state")) for summary in smoke_summaries) if smoke_summaries else False,
            "do_not_commit_live_packets": network_touched,
        },
        "failures": failures,
    }


def write_live_calibration_packet(roots: StorageRoots, packet: dict[str, object], *, run_id: str) -> Path:
    output_dir = run_artifact_dir(roots, run_id) / "calibration"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "live_calibration_packet.json"
    packet_with_path = {**packet, "packet_path": str(path)}
    path.write_text(json.dumps(packet_with_path, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _smoke_summary(report: dict[str, object]) -> dict[str, object]:
    artifacts = report.get("artifacts") if isinstance(report.get("artifacts"), dict) else {}
    answer = artifacts.get("answer") if isinstance(artifacts.get("answer"), dict) else {}
    course = report.get("course") if isinstance(report.get("course"), dict) else {}
    discovery = report.get("discovery") if isinstance(report.get("discovery"), dict) else {}
    sync = report.get("sync") if isinstance(report.get("sync"), dict) else {}
    privacy = report.get("privacy") if isinstance(report.get("privacy"), dict) else {}
    return {
        "schema": report.get("schema"),
        "status": report.get("status"),
        "run_id": report.get("run_id"),
        "platform": report.get("platform"),
        "source_mode": report.get("source_mode"),
        "network_touched": bool(report.get("network_touched")),
        "failure_count": len(report.get("failures", [])) if isinstance(report.get("failures"), list) else 0,
        "course_enabled": bool(course.get("enabled")),
        "bundle_loaded": bool(course.get("bundle_loaded")),
        "lesson_count": int(course.get("lesson_count") or 0),
        "evidence_count": int(course.get("evidence_count") or 0),
        "discovery_course_count": int(discovery.get("course_count") or 0),
        "sync_ok_count": int(sync.get("ok_count") or 0),
        "answer_enabled": bool(answer.get("enabled")),
        "answer_result_count": int(answer.get("result_count") or 0),
        "answer_evidence_count": int(answer.get("evidence_count") or 0),
        "has_source_timestamps": bool(answer.get("has_source_timestamps")),
        "progress_detected_count": int(course.get("progress_detected_count") or 0),
        "comment_count": int(course.get("comment_count") or 0),
        "transcript_count": int(course.get("transcript_count") or 0),
        "visible_transcript_count": int(course.get("visible_transcript_count") or 0),
        "caption_sidecar_count": int(course.get("caption_sidecar_count") or 0),
        "caption_resource_count": int(course.get("caption_resource_count") or 0),
        "caption_resource_error_count": int(course.get("caption_resource_error_count") or 0),
        "caption_resource_error_reasons": [str(reason) for reason in course.get("caption_resource_error_reasons", [])] if isinstance(course.get("caption_resource_error_reasons"), list) else [],
        "transcript_source_authority_counts": {
            str(key): int(value)
            for key, value in course.get("transcript_source_authority_counts", {}).items()
        }
        if isinstance(course.get("transcript_source_authority_counts"), dict)
        else {},
        "raw_path_count": len(privacy.get("raw_paths", [])) if isinstance(privacy.get("raw_paths"), list) else 0,
        "raw_paths_are_local_runtime_state": bool(privacy.get("raw_paths_are_local_runtime_state")),
        "private_data_commit_guard": bool(privacy.get("do_not_commit_raw_html_or_auth_state") or privacy.get("do_not_commit_raw_api_or_auth_state")),
    }


def _preflight_summary(report: dict[str, object]) -> dict[str, object]:
    checks = report.get("checks") if isinstance(report.get("checks"), list) else []
    return {
        "schema": report.get("schema"),
        "status": report.get("status"),
        "ready": bool(report.get("ready")),
        "network_touched": bool(report.get("network_touched")),
        "check_count": len(checks),
        "platforms": [str(platform) for platform in report.get("platforms", [])] if isinstance(report.get("platforms"), list) else [],
        "next_command_count": len(report.get("next_commands", [])) if isinstance(report.get("next_commands"), list) else 0,
    }


def _smoke_failures(summary: dict[str, object]) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    context = {"run_id": summary.get("run_id"), "platform": summary.get("platform"), "source_mode": summary.get("source_mode")}
    if summary.get("status") != "ok":
        failures.append({**context, "surface": "smoke", "reason": "smoke report status is not ok", "status": summary.get("status")})
    if not summary.get("course_enabled") or not summary.get("bundle_loaded"):
        failures.append({**context, "surface": "course", "reason": "course bundle was not loaded"})
    if int(summary.get("lesson_count") or 0) < 1:
        failures.append({**context, "surface": "course", "reason": "no lessons detected"})
    if int(summary.get("evidence_count") or 0) < 1:
        failures.append({**context, "surface": "evidence", "reason": "no evidence records detected"})
    if summary.get("answer_enabled"):
        if int(summary.get("answer_result_count") or 0) < 1:
            failures.append({**context, "surface": "answer", "reason": "answer returned no results"})
        if int(summary.get("answer_evidence_count") or 0) < 1:
            failures.append({**context, "surface": "answer", "reason": "answer has no evidence chain"})
    if int(summary.get("caption_resource_error_count") or 0) > 0:
        failures.append(
            {
                **context,
                "surface": "transcripts",
                "reason": "caption resource errors were recorded",
                "caption_resource_error_count": summary.get("caption_resource_error_count"),
                "caption_resource_error_reasons": summary.get("caption_resource_error_reasons"),
            }
        )
    if not summary.get("raw_paths_are_local_runtime_state") or not summary.get("private_data_commit_guard"):
        failures.append({**context, "surface": "privacy", "reason": "private/raw data guard is missing"})
    return failures


def _preflight_failures(summary: dict[str, object]) -> list[dict[str, object]]:
    if summary.get("status") not in {"ok", "warning"}:
        return [{"surface": "preflight", "reason": "unexpected preflight status", "status": summary.get("status")}]
    if summary.get("network_touched"):
        return [{"surface": "preflight", "reason": "preflight touched network"}]
    return []


def _secret_failures(reports: list[dict[str, object]]) -> list[dict[str, object]]:
    rendered = json.dumps(reports, sort_keys=True)
    markers = [marker for marker in SECRET_MARKERS if marker in rendered]
    keys = sorted(_payload_key_hits(reports, SECRET_PAYLOAD_KEYS))
    if markers or keys:
        return [
            {
                "surface": "privacy",
                "reason": "secret-like marker or key present in source reports",
                "markers": markers,
                "keys": keys,
            }
        ]
    return []


def _raw_payload_failures(reports: list[dict[str, object]]) -> list[dict[str, object]]:
    hits = sorted(_raw_payload_key_hits(reports))
    return [{"surface": "privacy", "reason": "raw/private payload field present in source reports", "keys": hits}] if hits else []


def _raw_payload_key_hits(value: Any) -> set[str]:
    return _payload_key_hits(value, RAW_PAYLOAD_KEYS)


def _payload_key_hits(value: Any, key_set: set[str]) -> set[str]:
    if isinstance(value, dict):
        hits: set[str] = set()
        for key, child in value.items():
            normalized_key = "".join(character for character in str(key).casefold() if character.isalnum())
            if normalized_key in key_set:
                hits.add(str(key))
            hits.update(_payload_key_hits(child, key_set))
        return hits
    if isinstance(value, list):
        hits: set[str] = set()
        for child in value:
            hits.update(_payload_key_hits(child, key_set))
        return hits
    return set()


def _sum_count_maps(items: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    try:
        iterator = iter(items)
    except TypeError:
        iterator = iter(())
    for item in iterator:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            counts[str(key)] = counts.get(str(key), 0) + int(value or 0)
    return dict(sorted(counts.items()))


def _is_browser_smoke(summary: dict[str, object]) -> bool:
    return str(summary.get("source_mode") or "").startswith("browser_")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
