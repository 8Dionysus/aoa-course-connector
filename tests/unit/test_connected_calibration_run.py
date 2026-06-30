from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.calibration.connected_run import run_connected_calibration
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.sources import upsert_source


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_connected_calibration_fixture_run_writes_receipt_packet_and_intake(tmp_path: Path) -> None:
    storage = roots(tmp_path)

    receipt = run_connected_calibration(storage, run_id="connected-fixture-proof", mode="fixture")

    assert receipt["schema"] == "aoa_course_connected_calibration_run_receipt_v1"
    assert receipt["status"] == "ok"
    assert receipt["mode"] == "fixture"
    assert receipt["platforms"] == ["getcourse", "skillspace", "stepik"]
    assert receipt["network_touched"] is False
    assert receipt["quality"]["answer_evidence_count_total"] >= 3
    assert receipt["privacy"]["contains_secret_values"] is False
    assert receipt["privacy"]["contains_raw_payloads"] is False
    assert len(receipt["artifacts"]["smoke_report_paths"]) == 3
    assert Path(str(receipt["artifacts"]["packet_path"])).is_file()
    assert Path(str(receipt["artifacts"]["intake_path"])).is_file()
    assert Path(str(receipt["artifacts"]["runbook_path"])).is_file()
    assert Path(str(receipt["receipt_path"])).is_file()
    rendered = json.dumps(receipt)
    assert "SUPER_SECRET" not in rendered
    assert "gho_" not in rendered


def test_connected_calibration_live_requires_explicit_network_gate(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "stepik", "67", "Stepik Public", access_mode="public_api")

    receipt = run_connected_calibration(storage, run_id="connected-live-blocked", mode="live", platforms=["stepik"])

    assert receipt["status"] == "partial"
    assert receipt["mode"] == "live"
    assert receipt["allow_network"] is False
    assert receipt["network_touched"] is False
    assert receipt["artifacts"]["packet_path"] is None
    assert any(failure["reason"] == "live mode requires --allow-network" for failure in receipt["failures"])
    assert Path(str(receipt["artifacts"]["plan_path"])).is_file()
    assert Path(str(receipt["artifacts"]["runbook_path"])).is_file()
