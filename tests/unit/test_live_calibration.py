from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.calibration import (
    build_live_calibration_intake,
    build_live_calibration_packet,
    write_live_calibration_intake,
    write_live_calibration_packet,
)
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.readiness import live_preflight
from aoa_course_connector.smoke import smoke_browser_fixture, smoke_stepik_fixture


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_live_calibration_packet_summarizes_fixture_smoke_reports(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    getcourse = smoke_browser_fixture(storage, platform="getcourse", run_id="getcourse-calibration", register=True)
    skillspace = smoke_browser_fixture(storage, platform="skillspace", run_id="skillspace-calibration", register=True)
    stepik = smoke_stepik_fixture(storage, course_id=67, run_id="stepik-calibration", query="Stepik public API evidence")
    preflight = live_preflight(storage, platforms=["stepik"])

    packet = build_live_calibration_packet(
        run_id="fixture-calibration",
        smoke_reports=[getcourse, skillspace, stepik],
        preflight_reports=[preflight],
    )
    packet_path = write_live_calibration_packet(storage, packet, run_id="fixture-calibration")
    saved = json.loads(packet_path.read_text(encoding="utf-8"))

    assert packet["status"] == "ok"
    assert packet["network_touched"] is False
    assert packet["platforms"] == ["getcourse", "skillspace", "stepik"]
    assert packet["report_count"] == 3
    assert packet["quality"]["answer_result_count_total"] >= 3
    assert packet["quality"]["all_answered_reports_have_evidence"] is True
    assert packet["quality"]["all_answered_reports_have_proof_fields"] is True
    assert packet["quality"]["answer_quality_ready_report_count"] == 3
    assert packet["quality"]["answer_expected_platform_match_count_total"] >= 3
    assert packet["quality"]["answer_provenance_complete_count_total"] >= 3
    assert packet["quality"]["answer_refresh_hint_count_total"] >= 3
    assert packet["quality"]["transcript_count_total"] >= 4
    assert packet["quality"]["caption_sidecar_count_total"] >= 2
    assert packet["quality"]["caption_resource_error_count_total"] == 0
    assert packet["quality"]["snapshot_audit_count_total"] >= 4
    assert packet["quality"]["snapshot_audit_failure_count_total"] == 0
    assert packet["quality"]["browser_reports_with_snapshot_audit"] == 2
    assert packet["quality"]["all_browser_reports_have_snapshot_audit"] is True
    assert packet["quality"]["all_snapshot_audits_ok"] is True
    assert packet["quality"]["transcript_source_authority_counts"]["browser_visible_transcript"] >= 2
    assert packet["quality"]["transcript_source_authority_counts"]["browser_caption_sidecar"] >= 2
    assert packet["smoke_reports"][0]["transcript_count"] >= 2
    assert packet["smoke_reports"][0]["caption_resource_error_count"] == 0
    assert packet["smoke_reports"][0]["snapshot_audit_count"] == 2
    assert packet["smoke_reports"][0]["snapshot_audit_ready_for_materialize_count"] >= 1
    assert packet["privacy"]["contains_raw_payloads"] is False
    assert packet["privacy"]["contains_secret_values"] is False
    assert saved["packet_path"] == str(packet_path)

    intake = build_live_calibration_intake(packet=saved, run_id="fixture-calibration-intake")
    intake_path = write_live_calibration_intake(storage, intake, run_id="fixture-calibration-intake")
    saved_intake = json.loads(intake_path.read_text(encoding="utf-8"))

    assert intake["status"] == "ok"
    assert intake["action_count"] == 0
    assert intake["authority"]["central_proof_owner"] == "aoa-evals"
    assert intake["privacy"]["shareable_after_review"] is True
    assert saved_intake["intake_path"] == str(intake_path)


def test_live_calibration_packet_rejects_secret_like_report_values(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    report = smoke_browser_fixture(storage, platform="getcourse", run_id="getcourse-secret-check")
    report["leaked_value"] = "SUPER_SECRET_TOKEN"

    packet = build_live_calibration_packet(run_id="secret-check", smoke_reports=[report])

    assert packet["status"] == "partial"
    assert packet["privacy"]["contains_secret_values"] is True
    assert any(failure["surface"] == "privacy" and "SUPER_SECRET" in failure["markers"] for failure in packet["failures"])


def test_live_calibration_packet_rejects_raw_payload_fields(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    report = smoke_browser_fixture(storage, platform="getcourse", run_id="getcourse-raw-check")
    report["raw_html"] = "<html>private course page</html>"

    packet = build_live_calibration_packet(run_id="raw-check", smoke_reports=[report])

    assert packet["status"] == "partial"
    assert packet["privacy"]["contains_raw_payloads"] is True
    assert any(failure["surface"] == "privacy" and "raw_html" in failure["keys"] for failure in packet["failures"])


def test_live_calibration_packet_rejects_generic_token_keys(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    report = smoke_browser_fixture(storage, platform="getcourse", run_id="getcourse-token-check")
    report["auth"] = {
        "token": "opaque-runtime-token",
        "api_key": "opaque-runtime-api-key",
    }

    packet = build_live_calibration_packet(run_id="token-check", smoke_reports=[report])

    assert packet["status"] == "partial"
    assert packet["privacy"]["contains_raw_payloads"] is True
    assert packet["privacy"]["contains_secret_values"] is True
    assert any(
        failure["surface"] == "privacy"
        and {"token", "api_key"} <= set(failure["keys"])
        for failure in packet["failures"]
    )


def test_live_calibration_packet_surfaces_caption_resource_errors(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    report = smoke_browser_fixture(storage, platform="getcourse", run_id="getcourse-caption-error-check")
    report["course"]["caption_resource_error_count"] = 1
    report["course"]["caption_resource_error_reasons"] = ["caption resource request failed"]

    packet = build_live_calibration_packet(run_id="caption-error-check", smoke_reports=[report])

    assert packet["status"] == "partial"
    assert packet["quality"]["caption_resource_error_count_total"] == 1
    assert any(
        failure["surface"] == "transcripts"
        and failure["caption_resource_error_count"] == 1
        for failure in packet["failures"]
    )


def test_live_calibration_packet_surfaces_snapshot_audit_failures(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    report = smoke_browser_fixture(storage, platform="getcourse", run_id="getcourse-audit-failure-check")
    report["snapshot_audits"][0]["status"] = "partial"
    report["snapshot_audits"][0]["failure_count"] = 1
    report["snapshot_audits"][0]["failures"] = [
        {"surface": "caption_sidecar", "reason": "visible caption sidecar has no matching resources[] payload"}
    ]

    packet = build_live_calibration_packet(run_id="audit-failure-check", smoke_reports=[report])
    intake = build_live_calibration_intake(packet=packet, run_id="audit-failure-check")

    assert packet["status"] == "partial"
    assert packet["quality"]["snapshot_audit_count_total"] == 2
    assert packet["quality"]["snapshot_audit_failure_count_total"] == 1
    assert packet["quality"]["all_snapshot_audits_ok"] is False
    assert any(
        failure["surface"] == "snapshot_audit"
        and failure["reason"] == "browser snapshot audit recorded failures"
        for failure in packet["failures"]
    )
    assert any(action["lane"] == "browser_snapshot_diagnostics" for action in intake["actions"])
    assert any("snapshot audit" in step for step in intake["next_steps"])


def test_live_calibration_packet_surfaces_answer_quality_failures(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    report = smoke_browser_fixture(storage, platform="getcourse", run_id="getcourse-answer-quality-check")
    report["artifacts"]["answer"]["quality"]["ready"] = False
    report["artifacts"]["answer"]["quality"]["blockers"] = ["result_missing_source_url"]

    packet = build_live_calibration_packet(run_id="answer-quality-check", smoke_reports=[report])

    assert packet["status"] == "partial"
    assert packet["quality"]["all_answered_reports_have_proof_fields"] is False
    assert any(
        failure["surface"] == "answer"
        and failure["reason"] == "answer proof fields incomplete"
        and "result_missing_source_url" in failure["blockers"]
        for failure in packet["failures"]
    )


def test_live_calibration_intake_classifies_failures_into_repair_lanes(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    report = smoke_browser_fixture(storage, platform="getcourse", run_id="getcourse-intake-check")
    report["course"]["caption_resource_error_count"] = 1
    report["course"]["caption_resource_error_reasons"] = ["caption resource parsed without transcript text"]
    report["artifacts"]["answer"]["result_count"] = 0
    report["auth"] = {"token": "opaque-runtime-token"}
    packet = build_live_calibration_packet(run_id="intake-check", smoke_reports=[report])

    intake = build_live_calibration_intake(packet=packet, run_id="intake-check")

    assert intake["status"] == "actionable"
    assert intake["privacy"]["contains_secret_values"] is True
    lanes = {action["lane"] for action in intake["actions"]}
    assert "caption_or_transcript_collection" in lanes
    assert "retrieval_quality" in lanes
    assert "privacy_guard" in lanes
    assert any(candidate["repo_local_path_hint"].startswith("evals/intake/") for candidate in intake["eval_intake_candidates"])
    assert any("do not share" in step for step in intake["next_steps"])
