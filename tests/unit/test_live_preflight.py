from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.readiness import connected_source_plan, live_preflight
from aoa_course_connector.sources import upsert_source


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_live_preflight_reports_stepik_token_without_value(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "stepik", "67", "Stepik API Fixture", access_mode="api_token")
    monkeypatch.setenv("STEPIK_API_TOKEN", "SUPER_SECRET_STEPIK_TOKEN")

    report = live_preflight(storage, platforms=["stepik"], stepik_token_env="STEPIK_API_TOKEN")

    assert report["schema"] == "aoa_course_live_preflight_v1"
    assert report["status"] == "ok"
    assert report["ready"] is True
    assert report["network_touched"] is False
    token_check = next(check for check in report["checks"] if check["kind"] == "token")
    assert token_check["token_present"] is True
    assert token_check["token_value_logged"] is False
    assert "SUPER_SECRET_STEPIK_TOKEN" not in json.dumps(report)


def test_live_preflight_allows_public_stepik_source_without_account_token(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "stepik", "67", "Stepik API Fixture", access_mode="public_api")
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)

    report = live_preflight(storage, platforms=["stepik"], stepik_token_env="STEPIK_API_TOKEN")

    assert report["status"] == "ok"
    assert report["ready"] is True
    workflows = {workflow["name"]: workflow for workflow in report["workflows"]}
    assert workflows["stepik_account_discovery"]["ready"] is False
    assert workflows["stepik_account_discovery"]["required_for_ready"] is False
    assert workflows["stepik_source_sync"]["ready"] is True
    assert not any(command.startswith("export STEPIK_API_TOKEN") for command in report["next_commands"])


def test_live_preflight_browser_state_readiness_redacts_secret_material(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "getcourse", "https://school.example/teach/control/stream", "School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.example", "path": "/"}],
            "origins": [{"origin": "https://school.example", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )

    report = live_preflight(storage, platforms=["getcourse"], expect_origin_contains="school.example")

    assert report["status"] == "ok"
    assert report["ready"] is True
    state_check = next(check for check in report["checks"] if check["kind"] == "browser_state")
    assert state_check["ready"] is True
    assert state_check["expected_origin_matched"] is True
    assert state_check["cookie_count"] == 1
    assert state_check["local_storage_entry_count"] == 1
    rendered = json.dumps(report)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_live_preflight_blocks_browser_source_when_state_matches_other_host(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "getcourse", "https://a.example/teach/control/stream", "A")
    upsert_source(storage.data, "getcourse", "https://b.example/teach/control/stream", "B")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".a.example", "path": "/"}],
            "origins": [{"origin": "https://a.example", "localStorage": []}],
        }),
        encoding="utf-8",
    )

    report = live_preflight(storage, platforms=["getcourse"])

    source_checks = {
        check["source_ref"]: check
        for check in report["checks"]
        if check["kind"] == "source"
    }
    assert source_checks["https://a.example/teach/control/stream"]["ready"] is True
    assert source_checks["https://b.example/teach/control/stream"]["ready"] is False
    assert "b.example" in " ".join(source_checks["https://b.example/teach/control/stream"]["blockers"])
    workflows = {workflow["name"]: workflow for workflow in report["workflows"]}
    assert workflows["browser_live_sync"]["ready"] is False
    assert report["ready"] is False
    assert not any(command.startswith("aoa-course sync browser-live") for command in report["next_commands"])
    assert any(command.startswith("aoa-course auth inspect-browser-state") for command in report["next_commands"])


def test_live_preflight_rejects_source_host_substring_state_match(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "getcourse", "https://my-school.example/teach/control/stream", "My School")
    upsert_source(storage.data, "getcourse", "https://school.example/teach/control/stream", "School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [],
            "origins": [{"origin": "https://my-school.example", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )

    report = live_preflight(storage, platforms=["getcourse"], expect_origin_contains="my-school.example")

    source_checks = {
        check["source_ref"]: check
        for check in report["checks"]
        if check["kind"] == "source"
    }
    assert source_checks["https://my-school.example/teach/control/stream"]["ready"] is True
    source_check = source_checks["https://school.example/teach/control/stream"]
    assert source_check["ready"] is False
    assert "school.example" in " ".join(source_check["blockers"])
    workflows = {workflow["name"]: workflow for workflow in report["workflows"]}
    assert workflows["browser_live_sync"]["ready"] is False
    assert report["ready"] is False
    assert not any(command.startswith("aoa-course sync browser-live") for command in report["next_commands"])


def test_live_preflight_reports_missing_browser_state_as_warning(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "skillspace", "https://school.skillspace.example/courses", "School")

    report = live_preflight(storage, platforms=["skillspace"])

    assert report["status"] == "warning"
    assert report["ready"] is False
    assert any(check["kind"] == "browser_state" and check["status"] == "missing" for check in report["checks"])
    assert any("capture-browser-state" in command for command in report["next_commands"])


def test_connected_source_plan_browser_ready_includes_sync_smoke_and_calibration(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "getcourse", "https://school.example/teach/control/stream", "School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.example", "path": "/"}],
            "origins": [{"origin": "https://school.example", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )

    plan = connected_source_plan(storage, platforms=["getcourse"], query="course-specific question")

    assert plan["schema"] == "aoa_course_connected_source_plan_v1"
    assert plan["status"] == "ok"
    assert plan["ready"] is True
    assert plan["network_touched"] is False
    assert plan["platform_plans"][0]["ready"] is True
    stage_actions = {
        stage["name"]: stage["actions"]
        for stage in plan["stages"]
    }
    assert any("preflight live --platform getcourse" in action["command"] for action in stage_actions["preflight_reports"])
    assert any("sync browser-live" in action["command"] for action in stage_actions["live_sync"])
    assert any("smoke browser-live" in action["command"] for action in stage_actions["live_smoke"])
    assert any("calibration build" in action["command"] for action in stage_actions["calibration_packet"])
    assert plan["source_plans"][0]["smoke_report_path"].startswith("$AOA_COURSE_ARTIFACT_ROOT/")
    rendered = json.dumps(plan)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_connected_source_plan_blocks_browser_without_auth_state(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "skillspace", "https://school.skillspace.example/courses", "School")

    plan = connected_source_plan(storage, platforms=["skillspace"])

    assert plan["status"] == "warning"
    assert plan["ready"] is False
    assert plan["platform_plans"][0]["blocked_source_count"] == 1
    assert plan["source_plans"][0]["smoke_command"] is None
    assert not any("sync browser-live" in command for command in plan["next_commands"])
    assert any("capture-browser-state" in command for command in plan["next_commands"])


def test_connected_source_plan_stepik_public_source_without_token(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "stepik", "https://stepik.org/course/67/syllabus", "Stepik Public", access_mode="public_api")
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)

    plan = connected_source_plan(storage, platforms=["stepik"], query="Stepik public API evidence")

    assert plan["status"] == "ok"
    assert plan["ready"] is True
    assert plan["platform_plans"][0]["ready_source_count"] == 1
    assert any("sync stepik-live" in command for command in plan["next_commands"])
    assert any("smoke stepik-live 67" in command for command in plan["next_commands"])
    assert any("calibration build" in command for command in plan["next_commands"])
    assert not any(command.startswith("export STEPIK_API_TOKEN") for command in plan["next_commands"])
