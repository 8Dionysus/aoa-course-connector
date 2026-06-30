from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.calibration import build_live_calibration_packet, write_live_calibration_packet
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
    assert packet["privacy"]["contains_raw_payloads"] is False
    assert packet["privacy"]["contains_secret_values"] is False
    assert saved["packet_path"] == str(packet_path)


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
