from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.readiness import connected_source_plan, live_preflight, render_connected_source_runbook
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
    assert "--max-sections 1" in workflows["stepik_source_sync"]["next_command"]
    assert "--full-course" not in workflows["stepik_source_sync"]["next_command"]
    assert not any(command.startswith("export STEPIK_API_TOKEN") for command in report["next_commands"])
    assert not any("--full-course" in command for command in report["next_commands"])


def test_live_preflight_browser_state_readiness_redacts_secret_material(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "getcourse", "https://school.operator.edu/teach/control/stream", "School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )

    report = live_preflight(storage, platforms=["getcourse"], expect_origin_contains="school.operator.edu")

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


def test_live_preflight_blocks_example_browser_sources_from_live_sync(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "getcourse", "https://school.example/teach/control/stream", "Fixture School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.example", "path": "/"}],
            "origins": [{"origin": "https://school.example", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )

    plan = connected_source_plan(storage, platforms=["getcourse"])
    next_commands = plan["next_commands"]

    assert plan["ready"] is False
    assert plan["platform_plans"][0]["operator_source_count"] == 0
    assert plan["platform_plans"][0]["fixture_or_example_source_count"] == 1
    source = plan["source_plans"][0]
    assert source["operator_live_candidate"] is False
    assert source["fixture_or_example_source"] is True
    assert source["sync_command"] is None
    assert "example/reserved host" in " ".join(source["blockers"])
    plan = plan["browser_auth_plans"][0]
    assert plan["operator_source_count"] == 0
    assert plan["fixture_or_example_source_hosts"] == ["school.example"]
    assert "no operator-owned live sources registered" in plan["blockers"]
    assert not any("sync browser-live" in command for command in next_commands)
    assert any("sources add <operator-course-url>" in command for command in next_commands)
    rendered = json.dumps(plan)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_live_preflight_scopes_sync_to_ready_operator_sources_when_fixture_remains(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    fixture, _, _ = upsert_source(storage.data, "getcourse", "https://school.example/teach/control/stream", "Fixture School")
    operator, _, _ = upsert_source(storage.data, "getcourse", "https://school.operator.edu/teach/control/stream", "Operator School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )

    report = live_preflight(storage, platforms=["getcourse"])

    assert report["ready"] is True
    sync_commands = [command for command in report["next_commands"] if command.startswith("aoa-course sync browser-live")]
    assert sync_commands
    assert all(str(operator["source_id"]) in command for command in sync_commands)
    assert not any(str(fixture["source_id"]) in command for command in sync_commands)
    workflow = next(item for item in report["workflows"] if item["name"] == "browser_live_sync")
    assert str(operator["source_id"]) in workflow["next_command"]
    assert str(fixture["source_id"]) not in workflow["next_command"]
    rendered = json.dumps(report)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_live_preflight_blocks_browser_source_when_state_matches_other_host(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "getcourse", "https://a.operator.edu/teach/control/stream", "A")
    upsert_source(storage.data, "getcourse", "https://b.operator.edu/teach/control/stream", "B")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".a.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://a.operator.edu", "localStorage": []}],
        }),
        encoding="utf-8",
    )

    report = live_preflight(storage, platforms=["getcourse"])

    source_checks = {
        check["source_ref"]: check
        for check in report["checks"]
        if check["kind"] == "source"
    }
    assert source_checks["https://a.operator.edu/teach/control/stream"]["ready"] is True
    assert source_checks["https://b.operator.edu/teach/control/stream"]["ready"] is False
    assert "b.operator.edu" in " ".join(source_checks["https://b.operator.edu/teach/control/stream"]["blockers"])
    workflows = {workflow["name"]: workflow for workflow in report["workflows"]}
    assert workflows["browser_live_sync"]["ready"] is False
    assert report["ready"] is False
    assert not any(command.startswith("aoa-course sync browser-live") for command in report["next_commands"])
    assert any(command.startswith("aoa-course auth inspect-browser-state") for command in report["next_commands"])


def test_connected_source_plan_can_scope_browser_work_to_one_ready_source(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    source_a, _, _ = upsert_source(storage.data, "getcourse", "https://a.operator.edu/teach/control/stream", "A")
    source_b, _, _ = upsert_source(storage.data, "getcourse", "https://b.operator.edu/teach/control/stream", "B")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".a.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://a.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )

    unscoped = connected_source_plan(storage, platforms=["getcourse"])
    scoped = connected_source_plan(storage, platforms=["getcourse"], source_ids=[str(source_a["source_id"])])

    assert unscoped["ready"] is False
    assert {source["source_id"] for source in unscoped["source_plans"]} == {source_a["source_id"], source_b["source_id"]}
    assert scoped["ready"] is True
    assert scoped["source_ids"] == [source_a["source_id"]]
    assert scoped["source_registry"]["selected_source_count"] == 1
    assert scoped["source_registry"]["missing_source_ids"] == []
    assert scoped["preflight"]["source_registry"]["selected_source_ids"] == [source_a["source_id"]]
    assert any(str(source_a["source_id"]) in command for command in scoped["preflight"]["next_commands"])
    assert [source["source_id"] for source in scoped["source_plans"]] == [source_a["source_id"]]
    assert scoped["platform_plans"][0]["ready_source_count"] == 1
    assert scoped["platform_plans"][0]["blocked_source_count"] == 0
    assert scoped["connected_run_plan"]["source_ids"] == [source_a["source_id"]]
    assert scoped["connected_run_plan"]["mcp_tool_call"]["arguments"]["source_ids"] == [source_a["source_id"]]
    assert f"--source-id {source_a['source_id']}" in scoped["connected_run_plan"]["command"]
    assert str(source_b["source_id"]) not in scoped["connected_run_plan"]["command"]
    assert str(source_b["source_id"]) not in scoped["connected_run_plan"]["mcp_command"]
    assert any("sync browser-live" in command and str(source_a["source_id"]) in command for command in scoped["next_commands"])
    rendered = json.dumps(scoped)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered

    implicit_platform = connected_source_plan(storage, source_ids=[str(source_a["source_id"])])
    assert implicit_platform["ready"] is True
    assert implicit_platform["platforms"] == ["getcourse"]
    assert implicit_platform["preflight"]["platforms"] == ["getcourse"]
    assert implicit_platform["source_ids"] == [source_a["source_id"]]
    assert all("--platform skillspace" not in command for command in implicit_platform["next_commands"])
    assert all("--platform stepik" not in command for command in implicit_platform["next_commands"])


def test_live_preflight_rejects_source_host_substring_state_match(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "getcourse", "https://my-school.operator.edu/teach/control/stream", "My School")
    upsert_source(storage.data, "getcourse", "https://school.operator.edu/teach/control/stream", "School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [],
            "origins": [{"origin": "https://my-school.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )

    report = live_preflight(storage, platforms=["getcourse"], expect_origin_contains="my-school.operator.edu")

    source_checks = {
        check["source_ref"]: check
        for check in report["checks"]
        if check["kind"] == "source"
    }
    assert source_checks["https://my-school.operator.edu/teach/control/stream"]["ready"] is True
    source_check = source_checks["https://school.operator.edu/teach/control/stream"]
    assert source_check["ready"] is False
    assert "school.operator.edu" in " ".join(source_check["blockers"])
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
    assert not any("import-firefox-state" in command for command in report["next_commands"])
    assert any("capture-browser-state" in command for command in report["next_commands"])


def test_connected_source_plan_defaults_to_all_priority_platforms(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "getcourse", "https://school.example/teach/control/stream", "School")
    upsert_source(storage.data, "skillspace", "https://school.skillspace.example/courses", "School Skillspace")
    upsert_source(storage.data, "stepik", "https://stepik.org/course/67/syllabus", "Stepik Public", access_mode="public_api")
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)

    plan = connected_source_plan(storage, query="course-specific question")

    assert plan["schema"] == "aoa_course_connected_source_plan_v1"
    assert plan["platforms"] == ["getcourse", "skillspace", "stepik"]
    assert plan["status"] == "partial"
    assert plan["ready"] is False
    assert plan["source_registry"]["selected_source_count"] == 3
    platform_plans = {item["platform"]: item for item in plan["platform_plans"]}
    assert platform_plans["getcourse"]["blocked_source_count"] == 1
    assert platform_plans["skillspace"]["blocked_source_count"] == 1
    assert platform_plans["stepik"]["ready_source_count"] == 1
    assert [plan["platform"] for plan in plan["browser_auth_plans"]] == ["getcourse", "skillspace"]
    assert any("capture-browser-state getcourse" in command for command in plan["next_commands"])
    assert any("capture-browser-state skillspace" in command for command in plan["next_commands"])
    assert any("sync stepik-live" in command for command in plan["next_commands"])
    stepik_source = next(source for source in plan["source_plans"] if source["platform"] == "stepik")
    connected_run = plan["connected_run_plan"]
    assert connected_run["ready"] is True
    assert connected_run["scope"] == "ready_subset"
    assert connected_run["covers_all_selected"] is False
    assert connected_run["platforms"] == ["stepik"]
    assert connected_run["selected_platforms"] == ["getcourse", "skillspace", "stepik"]
    assert connected_run["source_ids"] == [stepik_source["source_id"]]
    assert "getcourse workflow is not ready" in connected_run["blocked_by"]
    assert "skillspace workflow is not ready" in connected_run["blocked_by"]
    assert "--platform stepik" in connected_run["command"]
    assert "--platform getcourse" not in connected_run["command"]
    assert "--platform skillspace" not in connected_run["command"]
    assert connected_run["mcp_tool_call"]["arguments"]["platforms"] == ["stepik"]
    assert any(command == connected_run["command"] for command in plan["next_commands"])
    preflight_stage = next(stage for stage in plan["stages"] if stage["name"] == "preflight_reports")
    assert [action["platform"] for action in preflight_stage["actions"]] == ["getcourse", "skillspace", "stepik"]


def test_connected_source_plan_default_keeps_ready_getcourse_subset_actionable(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    source, _path, _state = upsert_source(storage.data, "getcourse", "https://school.operator.edu/teach/control/stream", "School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)

    plan = connected_source_plan(storage, query="course-specific question", max_lessons=7, max_pages=3, max_sources=4)

    assert plan["status"] == "partial"
    assert plan["ready"] is False
    connected_run = plan["connected_run_plan"]
    assert connected_run["ready"] is True
    assert connected_run["scope"] == "ready_subset"
    assert connected_run["covers_all_selected"] is False
    assert connected_run["selected_platforms"] == ["getcourse", "skillspace", "stepik"]
    assert connected_run["platforms"] == ["getcourse"]
    assert connected_run["source_ids"] == [source["source_id"]]
    assert "skillspace workflow is not ready" in connected_run["blocked_by"]
    assert "stepik workflow is not ready" in connected_run["blocked_by"]
    assert "--platform getcourse" in connected_run["command"]
    assert "--platform skillspace" not in connected_run["command"]
    assert "--platform stepik" not in connected_run["command"]
    assert "--max-lessons 7" in connected_run["command"]
    assert "--max-pages 3" in connected_run["command"]
    assert "--max-sources 4" in connected_run["command"]
    assert connected_run["mcp_tool_call"]["arguments"]["platforms"] == ["getcourse"]
    assert connected_run["mcp_tool_call"]["arguments"]["source_ids"] == [source["source_id"]]
    assert any(command == connected_run["command"] for command in plan["next_commands"])
    assert next(stage for stage in plan["stages"] if stage["name"] == "connected_run")["ready"] is True
    rendered = json.dumps(plan)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_connected_source_plan_browser_ready_includes_sync_smoke_and_calibration(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "getcourse", "https://school.operator.edu/teach/control/stream", "School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )

    plan = connected_source_plan(
        storage,
        platforms=["getcourse"],
        query="course-specific question",
        link_pattern="*/lessons/*",
    )

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
    assert any("sync browser-live" in action["command"] and "--source-id" in action["command"] for action in stage_actions["live_sync"])
    assert any("smoke browser-live" in action["command"] for action in stage_actions["live_smoke"])
    assert any("--link-pattern '*/lessons/*'" in action["command"] for action in stage_actions["live_sync"])
    assert any("--link-pattern '*/lessons/*'" in action["command"] for action in stage_actions["live_smoke"])
    assert plan["link_pattern"] == "*/lessons/*"
    connected_run = stage_actions["connected_run"][0]
    assert connected_run["kind"] == "connected_run"
    assert connected_run["ready"] is True
    assert connected_run["network_touched"] is True
    assert connected_run["source_ids"] == [plan["source_plans"][0]["source_id"]]
    assert "calibration connected-run --mode live --allow-network" in connected_run["command"]
    assert "--platform getcourse" in connected_run["command"]
    assert "--source-id" in connected_run["command"]
    assert "--query 'course-specific question'" in connected_run["command"]
    assert "--link-pattern '*/lessons/*'" in connected_run["command"]
    assert connected_run["mcp_tool_call"]["tool"] == "connected_run"
    assert connected_run["mcp_tool_call"]["network_touched"] is True
    mcp_args = connected_run["mcp_tool_call"]["arguments"]
    assert mcp_args["run"] == "connected-live-calibration"
    assert mcp_args["mode"] == "live"
    assert mcp_args["platforms"] == ["getcourse"]
    assert mcp_args["source_ids"] == [plan["source_plans"][0]["source_id"]]
    assert mcp_args["query"] == "course-specific question"
    assert mcp_args["live_scope"] == "bounded"
    assert mcp_args["allow_network"] is True
    assert mcp_args["max_lessons"] == 50
    assert mcp_args["max_pages"] == 5
    assert mcp_args["max_sources"] == 50
    assert mcp_args["link_pattern"] == "*/lessons/*"
    assert connected_run["mcp_command"].startswith("aoa-course mcp call connected_run ")
    assert '"allow_network":true' in connected_run["mcp_command"]
    assert plan["connected_run_plan"] == connected_run
    assert any("calibration build" in action["command"] for action in stage_actions["calibration_packet"])
    assert plan["source_plans"][0]["smoke_report_path"].startswith("${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/")
    assert "--source-id" in plan["source_plans"][0]["sync_command"]
    assert stage_actions["preflight_reports"][0]["artifact_path"] == "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/getcourse-preflight.json"
    assert stage_actions["calibration_packet"][0]["artifact_path"] == "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/connected-live-calibration/calibration/live_calibration_packet.json"
    assert "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/connected-live-calibration" in stage_actions["calibration_packet"][0]["artifact_path"]
    plan = plan["browser_auth_plans"][0]
    assert plan["platform"] == "getcourse"
    assert plan["ready"] is True
    assert plan["source_hosts"] == ["school.operator.edu"]
    assert plan["blocked_source_count"] == 0
    assert plan["host_readiness"][0]["ready_source_count"] == 1
    assert "import-firefox-state getcourse account" in plan["commands"]["import_firefox"]
    assert "--expect-origin-contains school.operator.edu" in plan["commands"]["import_firefox"]
    assert "capture-browser-state getcourse account" in plan["commands"]["capture"]
    assert "--expect-origin-contains school.operator.edu" in plan["commands"]["capture"]
    assert "inspect-browser-state" in plan["commands"]["inspect"]
    assert plan["commands"]["inspect_source_hosts"] == [
        'aoa-course auth inspect-browser-state "${AOA_COURSE_AUTH_ROOT:-.connector-state/auth}/getcourse/account.storage-state.json" --expect-origin-contains school.operator.edu'
    ]
    assert "preflight connected-plan --platform getcourse" in plan["commands"]["recheck"]
    rendered = json.dumps(plan)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_connected_source_plan_blocks_browser_without_auth_state(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "skillspace", "https://school.skillspace.edu/courses", "School")

    plan = connected_source_plan(storage, platforms=["skillspace"])
    next_commands = plan["next_commands"]

    assert plan["status"] == "warning"
    assert plan["ready"] is False
    assert plan["platform_plans"][0]["blocked_source_count"] == 1
    assert plan["platform_plans"][0]["blockers"] == ["browser storage state is missing"]
    assert plan["source_plans"][0]["smoke_command"] is None
    connected_run = next(stage for stage in plan["stages"] if stage["name"] == "connected_run")["actions"][0]
    assert connected_run["ready"] is False
    assert "command" not in connected_run
    assert "skillspace workflow is not ready" in connected_run["blocked_by"]
    plan = plan["browser_auth_plans"][0]
    assert plan["platform"] == "skillspace"
    assert plan["ready"] is False
    assert plan["source_count"] == 1
    assert plan["blocked_source_count"] == 1
    assert plan["source_hosts"] == ["school.skillspace.edu"]
    assert plan["blocked_source_hosts"] == ["school.skillspace.edu"]
    assert plan["host_readiness"] == [
        {
            "host": "school.skillspace.edu",
            "source_count": 1,
            "ready_source_count": 0,
            "blocked_source_count": 1,
            "blockers": ["browser storage state is missing"],
        }
    ]
    assert plan["blockers"] == ["browser storage state is missing"]
    assert "import-firefox-state skillspace account" in plan["commands"]["import_firefox"]
    assert "--expect-origin-contains school.skillspace.edu" in plan["commands"]["import_firefox"]
    assert "capture-browser-state skillspace account" in plan["commands"]["capture"]
    assert "--state-file" in plan["commands"]["capture"]
    assert "--expect-origin school.skillspace.edu" in plan["commands"]["recheck"]
    assert plan["state_file_candidates"][0]["commands"]["import_firefox"].startswith("aoa-course auth import-firefox-state skillspace school.skillspace.edu")
    assert "--expect-origin-contains school.skillspace.edu" in plan["state_file_candidates"][0]["commands"]["import_firefox"]
    assert not any("sync browser-live" in command for command in next_commands)
    assert any("import-firefox-state skillspace account" in command for command in next_commands)
    assert any("capture-browser-state" in command for command in next_commands)


def test_connected_source_runbook_renders_plan_without_secret_values(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "getcourse", "https://school.operator.edu/teach/control/stream", "School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )
    plan = connected_source_plan(storage, platforms=["getcourse"], query="course-specific question")

    runbook = render_connected_source_runbook(plan)

    assert "# Connected Source Runbook" in runbook
    assert "## Browser Auth Plans" in runbook
    assert "school.operator.edu" in runbook
    assert "capture-browser-state getcourse account" in runbook
    assert "smoke browser-live" in runbook
    assert "calibration connected-run --mode live --allow-network" in runbook
    assert "calibration build" in runbook
    assert "SUPER_SECRET_COOKIE" not in runbook
    assert "SUPER_SECRET_TOKEN" not in runbook


def test_connected_source_plan_stepik_public_source_without_token(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "stepik", "https://stepik.org/course/67/syllabus", "Stepik Public", access_mode="public_api")
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)

    plan = connected_source_plan(storage, platforms=["stepik"], query="Stepik public API evidence")

    assert plan["status"] == "ok"
    assert plan["ready"] is True
    assert plan["live_scope"] == "bounded"
    assert plan["include_step_sources"] is False
    assert plan["platform_plans"][0]["ready_source_count"] == 1
    assert any("sync stepik-live" in command and "--source-id" in command for command in plan["next_commands"])
    assert any("smoke stepik-live 67" in command for command in plan["next_commands"])
    assert "--source-id" in plan["source_plans"][0]["sync_command"]
    assert any("--access-mode public_api" in command for command in plan["next_commands"])
    assert not any("--full-course" in command for command in plan["next_commands"])
    assert not any("--include-step-sources" in command for command in plan["next_commands"])
    assert any("--max-sections 1" in command for command in plan["next_commands"])
    assert any("calibration build" in command for command in plan["next_commands"])
    assert any("${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/stepik-live-smoke" in command for command in plan["next_commands"])
    assert any("${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/connected-live-calibration" in action["artifact_path"] for action in next(stage for stage in plan["stages"] if stage["name"] == "calibration_packet")["actions"])
    assert not any(command.startswith("export STEPIK_API_TOKEN") for command in plan["next_commands"])


def test_connected_source_plan_stepik_browser_session_uses_storage_state(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    state_file = storage.auth / "stepik" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        '{"cookies": [{"name": "sessionid", "value": "SUPER_SECRET_COOKIE", "domain": ".stepik.org", "path": "/"}], '
        '"origins": [{"origin": "https://stepik.org", "localStorage": []}]}',
        encoding="utf-8",
    )
    upsert_source(storage.data, "stepik", "67", "Stepik Browser", access_mode="browser_session")
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)

    plan = connected_source_plan(storage, platforms=["stepik"], query="Stepik public API evidence")

    assert plan["status"] == "ok"
    assert plan["ready"] is True
    assert plan["platform_plans"][0]["ready_source_count"] == 1
    assert not any(command.startswith("export STEPIK_API_TOKEN") for command in plan["next_commands"])
    assert any("sync stepik-live" in command and "--state-file" in command for command in plan["next_commands"])
    sync_command = plan["source_plans"][0]["sync_command"]
    smoke_command = plan["source_plans"][0]["smoke_command"]
    assert "--state-file" in sync_command
    assert "--state-file" in smoke_command
    assert "SUPER_SECRET_COOKIE" not in json.dumps(plan)


def test_live_preflight_stepik_browser_state_suggests_account_discovery(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    state_file = storage.auth / "stepik" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        '{"cookies": [{"name": "sessionid", "value": "SUPER_SECRET_COOKIE", "domain": ".stepik.org", "path": "/"}], '
        '"origins": [{"origin": "https://stepik.org", "localStorage": []}]}',
        encoding="utf-8",
    )
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)

    report = live_preflight(storage, platforms=["stepik"])

    assert report["status"] == "warning"
    assert report["workflows"][0]["ready"] is True
    assert any("discover stepik-account --state-file" in command for command in report["next_commands"])
    assert "SUPER_SECRET_COOKIE" not in json.dumps(report)


def test_connected_source_plan_blocks_unparseable_ready_stepik_smoke(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "stepik", "https://stepik.org/learn/broken", "Broken Stepik", access_mode="public_api")
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)

    plan = connected_source_plan(storage, platforms=["stepik"])

    assert plan["status"] == "partial"
    assert plan["ready"] is False
    assert plan["platform_plans"][0]["ready"] is True
    smoke_stage = next(stage for stage in plan["stages"] if stage["name"] == "live_smoke")
    assert smoke_stage["ready"] is False
    assert smoke_stage["actions"][0]["ready"] is False
    assert "cannot parse Stepik course id" in " ".join(smoke_stage["actions"][0]["blocked_by"])
    assert plan["source_plans"][0]["smoke_command"] is None


def test_connected_source_plan_stepik_smoke_preserves_registered_access_mode(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "stepik", "67", "Stepik API", access_mode="api_token")
    monkeypatch.setenv("STEPIK_API_TOKEN", "SUPER_SECRET_STEPIK_TOKEN")

    plan = connected_source_plan(storage, platforms=["stepik"])

    command = plan["source_plans"][0]["smoke_command"]
    assert "--access-mode api_token" in command
    assert "SUPER_SECRET_STEPIK_TOKEN" not in json.dumps(plan)


def test_connected_source_plan_stepik_full_course_scope_is_explicit(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "stepik", "67", "Stepik Public", access_mode="public_api")
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)

    plan = connected_source_plan(
        storage,
        platforms=["stepik"],
        live_scope="full-course",
        include_step_sources=True,
    )

    assert plan["status"] == "ok"
    assert plan["live_scope"] == "full-course"
    assert plan["include_step_sources"] is True
    assert any("--full-course" in command for command in plan["next_commands"])
    assert any("--include-step-sources" in command for command in plan["next_commands"])
    assert not any("--max-sections 1" in command for command in plan["next_commands"])
