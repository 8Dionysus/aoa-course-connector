from __future__ import annotations

import json
from pathlib import Path

import aoa_course_connector.calibration.connected_run as connected_run_module
from aoa_course_connector.calibration.connected_run import load_connected_calibration_status, run_connected_calibration
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.smoke.stepik import smoke_stepik_fixture
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
    status = load_connected_calibration_status(storage, run_id="connected-fixture-proof")
    assert status["schema"] == "aoa_course_connected_calibration_run_status_v1"
    assert status["status"] == "ok"
    assert status["exists"] is True
    assert status["receipt_schema"] == "aoa_course_connected_calibration_run_receipt_v1"
    assert status["network_touched"] is False
    assert status["artifacts"]["packet_path"] == receipt["artifacts"]["packet_path"]
    assert status["privacy"]["contains_secret_values"] is False


def test_connected_calibration_status_reports_missing_receipt(tmp_path: Path) -> None:
    storage = roots(tmp_path)

    status = load_connected_calibration_status(storage, run_id="missing-connected-run")

    assert status["schema"] == "aoa_course_connected_calibration_run_status_v1"
    assert status["status"] == "missing"
    assert status["exists"] is False
    assert status["network_touched"] is False


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


def test_connected_calibration_live_source_limit_ignores_unselected_blocked_sources(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = roots(tmp_path)
    ready, _path, _state = upsert_source(storage.data, "stepik", "67", "Stepik Public", access_mode="public_api")
    blocked, _path, _state = upsert_source(storage.data, "stepik", "68", "Stepik Token", access_mode="api_token")
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)
    selected_ids: list[str] = []

    def fake_sync(*_args, source_ids=None, **kwargs):
        selected_ids.extend([str(source_id) for source_id in source_ids or []])
        return {
            "schema": "aoa_course_sync_receipt_v1",
            "status": "ok",
            "sync_run_id": kwargs.get("sync_run_id"),
            "source_count": len(source_ids or []),
            "synced_sources": [],
            "failed_sources": [],
            "network_touched": True,
        }

    def fake_smoke(roots_arg, *, run_id: str, query=None, build_artifacts: bool = True, **_kwargs):
        report = smoke_stepik_fixture(
            roots_arg,
            course_id=67,
            run_id=run_id,
            query=query,
            build_artifacts=build_artifacts,
        )
        return {**report, "source_mode": "stepik_live_smoke", "network_touched": True}

    monkeypatch.setattr(connected_run_module, "sync_stepik_live_sources", fake_sync)
    monkeypatch.setattr(connected_run_module, "smoke_stepik_live", fake_smoke)

    receipt = run_connected_calibration(
        storage,
        run_id="connected-live-limited",
        mode="live",
        platforms=["stepik"],
        allow_network=True,
        source_limit=1,
    )

    assert receipt["status"] == "ok"
    assert selected_ids == [ready["source_id"]]
    assert not any(failure.get("source_id") == blocked["source_id"] for failure in receipt["failures"])


def test_connected_calibration_live_reports_explicit_blocked_source(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    blocked, _path, _state = upsert_source(storage.data, "stepik", "68", "Stepik Token", access_mode="api_token")
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)

    receipt = run_connected_calibration(
        storage,
        run_id="connected-live-explicit-blocked",
        mode="live",
        platforms=["stepik"],
        source_ids=[str(blocked["source_id"])],
        allow_network=True,
    )

    assert receipt["status"] == "partial"
    assert receipt["network_touched"] is False
    assert any(
        failure["reason"] == "source is not ready" and failure["source_id"] == blocked["source_id"]
        for failure in receipt["failures"]
    )
