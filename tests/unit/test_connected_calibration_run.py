from __future__ import annotations

import json
from pathlib import Path

import aoa_course_connector.calibration.connected_run as connected_run_module
from aoa_course_connector.calibration.connected_run import load_connected_calibration_status, run_connected_calibration
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.smoke.browser_session import smoke_browser_fixture
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
    assert receipt["query_handoff"]["schema"] == "aoa_course_connected_query_handoff_v1"
    assert receipt["query_handoff"]["ready"] is True
    assert receipt["query_handoff"]["entry_count"] >= 3
    smoke_entries = [entry for entry in receipt["query_handoff"]["entries"] if entry["kind"] == "smoke"]
    assert {entry["platform"] for entry in smoke_entries} == {"getcourse", "skillspace", "stepik"}
    assert all(entry["query_ready"] is True for entry in smoke_entries)
    assert all(entry["semantic_query_ready"] is True for entry in smoke_entries)
    assert all(entry["graph_ready"] is True for entry in smoke_entries)
    assert all(entry["answer_ready"] is True for entry in smoke_entries)
    assert all(entry["commands"]["answer"].startswith("aoa-course answer ") for entry in smoke_entries)
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
    assert status["query_handoff"]["entry_count"] == receipt["query_handoff"]["entry_count"]
    assert status["query_handoff"]["entries"][0]["commands"]["query"].startswith("aoa-course query ")
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


def test_connected_calibration_live_browser_uses_default_ready_state_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = roots(tmp_path)
    source, _path, _state = upsert_source(
        storage.data,
        "getcourse",
        "https://school.example/teach/control/stream",
        "School",
        access_mode="browser_session",
    )
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.example", "path": "/"}],
            "origins": [{"origin": "https://school.example", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )
    sync_calls: list[dict[str, object]] = []
    smoke_calls: list[dict[str, object]] = []

    def fake_sync(roots_arg, *, sync_run_id: str, source_ids=None, state_file=None, **_kwargs):
        sync_calls.append({"source_ids": list(source_ids or []), "state_file": state_file})
        receipt_path = roots_arg.data / "sync" / sync_run_id / "sync_receipt.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema": "aoa_course_sync_receipt_v1",
            "status": "ok",
            "sync_run_id": sync_run_id,
            "source_count": len(source_ids or []),
            "synced_sources": [],
            "failed_sources": [],
            "network_touched": True,
            "receipt_path": str(receipt_path),
        }
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
        return receipt

    def fake_smoke(
        roots_arg,
        *,
        platform: str,
        run_id: str,
        course_url: str,
        state_file=None,
        query=None,
        build_artifacts: bool = True,
        **_kwargs,
    ):
        smoke_calls.append({"platform": platform, "course_url": course_url, "state_file": state_file})
        report = smoke_browser_fixture(
            roots_arg,
            platform=platform,
            run_id=run_id,
            query=query,
            build_artifacts=build_artifacts,
        )
        return {**report, "source_mode": "browser_live_smoke", "network_touched": True}

    monkeypatch.setattr(connected_run_module, "sync_browser_live_sources", fake_sync)
    monkeypatch.setattr(connected_run_module, "smoke_browser_live", fake_smoke)

    receipt = run_connected_calibration(
        storage,
        run_id="connected-live-browser-default-state",
        mode="live",
        platforms=["getcourse"],
        allow_network=True,
    )
    status = load_connected_calibration_status(storage, run_id="connected-live-browser-default-state")

    assert receipt["status"] == "ok"
    assert receipt["network_touched"] is True
    assert receipt["source_selection"]["ready_source_ids"] == [source["source_id"]]
    assert receipt["source_selection"]["selected_source_count"] == 1
    assert sync_calls == [{"source_ids": [source["source_id"]], "state_file": state_file.resolve()}]
    assert smoke_calls == [{"platform": "getcourse", "course_url": source["source_ref"], "state_file": state_file.resolve()}]
    live_sync_stage = next(stage for stage in receipt["stages"] if stage["name"] == "live_sync")
    live_smoke_stage = next(stage for stage in receipt["stages"] if stage["name"] == "live_smoke")
    assert live_sync_stage["actions"][0]["source_ids"] == [source["source_id"]]
    assert live_sync_stage["actions"][0]["state_file"] == str(state_file.resolve())
    assert live_smoke_stage["actions"][0]["source_id"] == source["source_id"]
    assert receipt["query_handoff"]["ready"] is True
    assert any(entry["kind"] == "smoke" and entry["platform"] == "getcourse" for entry in receipt["query_handoff"]["entries"])
    assert status["source_selection"]["ready_source_ids"] == [source["source_id"]]
    assert status["query_handoff"]["ready"] is True
    rendered = json.dumps(receipt)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


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
