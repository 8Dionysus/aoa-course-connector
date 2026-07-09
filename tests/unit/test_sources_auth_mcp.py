from __future__ import annotations

import json
import os
import sqlite3
import sys
import types
from argparse import Namespace
from pathlib import Path

import pytest

import aoa_course_connector.cli as cli_module
from aoa_course_connector.adapters import adapter_list
from aoa_course_connector.auth import (
    browser_state_cookie_header,
    browser_state_plan,
    capture_browser_state,
    default_browser_state_path,
    import_firefox_browser_state,
    inspect_browser_state,
)
from aoa_course_connector.calibration.connected_run import run_connected_calibration
from aoa_course_connector.connection_profile import (
    apply_connection_profile,
    build_connection_profile,
    connection_profile_run_plan,
    connection_profile_status,
    inspect_connection_profile,
    load_connection_profile,
    write_connection_profile,
)
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index, build_semantic_index
from aoa_course_connector.ingest import materialize_fixture
from aoa_course_connector.mcp.server import (
    _drop_source_refs,
    _sources_answer_matrix_top_result_refs,
    _sources_answer_next_commands,
    call_tool,
    handle_jsonrpc_message,
    tools_manifest,
)
from aoa_course_connector.readiness import semantic_provider_preflight
from aoa_course_connector.sources import PLATFORMS, load_registry, upsert_source
from aoa_course_connector.status import connected_query_run_catalog
from aoa_course_connector.storage import run_data_dir
from aoa_course_connector.sync.checkpoints import make_checkpoint, upsert_checkpoint


def _write_query_artifact_paths(storage: StorageRoots, run_id: str) -> dict[str, str]:
    index_dir = storage.artifact / "runs" / run_id / "indexes"
    graph_dir = storage.artifact / "runs" / run_id / "graphs"
    index_dir.mkdir(parents=True, exist_ok=True)
    graph_dir.mkdir(parents=True, exist_ok=True)
    index_path = index_dir / "keyword_index.json"
    semantic_path = index_dir / "semantic_index.json"
    graph_path = graph_dir / "course_graph.json"
    for path in [index_path, semantic_path, graph_path]:
        path.write_text("{}", encoding="utf-8")
    return {
        "index_path": str(index_path),
        "semantic_index_path": str(semantic_path),
        "graph_path": str(graph_path),
    }


def test_source_answer_redaction_removes_singular_and_plural_source_refs() -> None:
    redacted = _drop_source_refs(
        {
            "source_ref": "https://school.example/private",
            "source_refs": ["https://school.example/private/lesson"],
            "nested": {
                "source_refs": ["https://academy.example/private/lesson"],
                "kept": "value",
            },
            "items": [{"source_ref": "https://stepik.org/private", "kept": True}],
        }
    )

    rendered = json.dumps(redacted)
    assert "source_ref" not in rendered
    assert "source_refs" not in rendered
    assert "https://school.example" not in rendered
    assert redacted["nested"]["kept"] == "value"
    assert redacted["items"][0]["kept"] is True


def test_sources_answer_next_commands_preserve_kind_filters() -> None:
    commands = _sources_answer_next_commands(
        "Stepik public API evidence",
        ["source:stepik:67"],
        ["stepik"],
        ["smoke"],
        "hybrid",
    )

    assert "--kind smoke" in commands[0]
    assert '"kinds":["smoke"]' in commands[1]


def test_mcp_source_tools_advertise_every_registry_platform() -> None:
    tools = {tool["name"]: tool for tool in tools_manifest()["tools"]}
    expected = sorted(PLATFORMS)

    for name in ["list_sources", "source_answer", "sources_answer"]:
        enum = tools[name]["inputSchema"]["properties"]["platforms"]["items"]["enum"]
        assert enum == expected


def test_source_registry_and_browser_plan(tmp_path: Path) -> None:
    source, path, state = upsert_source(tmp_path / "data", "getcourse", "https://school.example", "School")
    assert state == "added"
    assert source["access_mode"] == "browser_session"
    assert path.exists()
    assert load_registry(tmp_path / "data")["sources"]
    plan = browser_state_plan(tmp_path / "auth", "getcourse", "https://school.example")
    assert plan["state_file"]
    assert plan["state_file"] == str(default_browser_state_path(tmp_path / "auth", "getcourse", "https://school.example"))
    assert plan["expected_origin_contains"] == "school.example"
    assert "capture-browser-state" in plan["capture_command"]
    assert "--state-file" in plan["capture_command"]
    assert "--expect-origin-contains school.example" in plan["capture_command"]
    assert "inspect-browser-state" in plan["inspect_command"]
    assert "--expect-origin-contains school.example" in plan["inspect_command"]
    assert plan["git_safe"] is False


def test_connection_profile_plans_and_applies_operator_sources(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(tmp_path / "auth"))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("AOA_COURSE_TEST_EMBEDDING_TOKEN", "SUPER_SECRET_EMBEDDING_TOKEN")
    monkeypatch.setenv("STEPIK_API_TOKEN", "SUPER_SECRET_STEPIK_TOKEN")
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    profile = build_connection_profile(
        storage,
        name="live-courses",
        getcourse_urls=["https://school.example/teach/control/stream"],
        skillspace_urls=["https://academy.example/course/demo"],
        stepik_course_ids=["67"],
        stepik_token_env="STEPIK_API_TOKEN",
        run_id="connected-live-calibration",
        query="course-specific question",
        live_scope="full-course",
        include_step_sources=True,
        max_step_sources=None,
        step_source_timeout=0.5,
        semantic_provider="http_json_v1",
        embedding_endpoint="https://embed.example/v1",
        embedding_model="course-embedding",
        embedding_token_env="AOA_COURSE_TEST_EMBEDDING_TOKEN",
    )
    profile_path = tmp_path / "artifacts" / "connections" / "live-courses.connection-profile.json"
    write_receipt = write_connection_profile(profile, profile_path)
    loaded = load_connection_profile(profile_path)
    inspection = inspect_connection_profile(storage, loaded, profile_path=profile_path)

    rendered = json.dumps({"profile": loaded, "inspection": inspection})
    assert write_receipt["written"] is True
    assert loaded["schema"] == "aoa_course_connection_profile_v1"
    assert loaded["runtime"]["max_step_sources"] == "all"
    assert loaded["runtime"]["step_source_timeout"] == 0.5
    assert inspection["schema"] == "aoa_course_connection_profile_inspection_v1"
    assert inspection["network_touched"] is False
    assert inspection["live_readiness"]["schema"] == "aoa_course_connection_profile_readiness_v1"
    assert inspection["live_readiness"]["ready_for_connected_run"] is False
    assert inspection["live_readiness"]["blocked_by"]
    assert inspection["source_registry"]["registered_profile_source_count"] == 0
    assert "SUPER_SECRET_EMBEDDING_TOKEN" not in rendered
    assert "SUPER_SECRET_STEPIK_TOKEN" not in rendered
    assert any("sources add" in command for command in inspection["next_commands"])
    assert any("auth import-firefox-state getcourse" in command for command in inspection["next_commands"])
    assert any("auth import-firefox-state skillspace" in command for command in inspection["next_commands"])
    assert any("auth capture-browser-state" in command for command in inspection["next_commands"])
    getcourse_auth = next(plan for plan in inspection["browser_auth"] if plan["platform"] == "getcourse")
    skillspace_auth = next(plan for plan in inspection["browser_auth"] if plan["platform"] == "skillspace")
    assert "auth import-firefox-state getcourse" in getcourse_auth["import_firefox_command"]
    assert "--expect-origin-contains school.example" in getcourse_auth["import_firefox_command"]
    assert "auth import-firefox-state skillspace" in skillspace_auth["import_firefox_command"]
    assert "--expect-origin-contains academy.example" in skillspace_auth["import_firefox_command"]

    apply_receipt = apply_connection_profile(storage, loaded, profile_path=profile_path)
    registry = load_registry(storage.data)
    assert apply_receipt["status"] == "ok"
    assert len(apply_receipt["applied"]) == 3
    assert len(registry["sources"]) == 3
    assert apply_receipt["inspection"]["source_registry"]["registered_profile_source_count"] == 3
    status = connection_profile_status(apply_receipt["inspection"])
    assert status["schema"] == "aoa_course_connection_profile_status_v1"
    assert status["live_readiness"]["ready_for_connected_run"] is False
    stepik_plan = next(plan for plan in apply_receipt["inspection"]["connected_plans"] if plan["platform"] == "stepik")
    assert "--stepik-token-env STEPIK_API_TOKEN" in stepik_plan["command"]
    assert "--max-step-sources all" in stepik_plan["command"]
    assert "--step-source-timeout 0.5" in stepik_plan["command"]
    assert "--stepik-token-env STEPIK_API_TOKEN" in stepik_plan["plan"]["connected_run_plan"].get("command", "")
    assert "--max-step-sources all" in stepik_plan["plan"]["connected_run_plan"].get("command", "")
    assert stepik_plan["plan"]["connected_run_plan"]["mcp_tool_call"]["arguments"]["max_step_sources"] == "all"

    mcp = call_tool("connection_profile_inspect", {"profile_path": str(profile_path)})
    assert mcp["tool"] == "connection_profile_inspect"
    assert mcp["inspection"]["schema"] == "aoa_course_connection_profile_inspection_v1"
    assert mcp["inspection"]["network_touched"] is False
    mcp_status = call_tool("connection_profile_status", {"profile_path": str(profile_path)})
    assert mcp_status["tool"] == "connection_profile_status"
    assert mcp_status["status"]["schema"] == "aoa_course_connection_profile_status_v1"
    assert mcp_status["status"]["network_touched"] is False


def test_connection_profile_live_readiness_reports_ready_connected_run(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))
    source_url = "https://school.operator.edu/teach/control/stream"
    profile = build_connection_profile(
        storage,
        name="ready-live",
        getcourse_urls=[source_url],
        run_id="connected-live-calibration",
        query="course-specific question",
    )
    state_file = default_browser_state_path(storage.auth, "getcourse", source_url)
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )
    profile_path = tmp_path / "artifacts" / "connections" / "ready-live.connection-profile.json"
    write_connection_profile(profile, profile_path)
    receipt = apply_connection_profile(storage, load_connection_profile(profile_path), profile_path=profile_path)
    readiness = receipt["inspection"]["live_readiness"]
    run_plan = connection_profile_run_plan(profile, receipt["inspection"], platform="getcourse")
    mcp_plan = call_tool("connection_profile_run_plan", {"profile_path": str(profile_path), "platform": "getcourse"})

    assert readiness["ready_for_connected_run"] is True
    assert run_plan["schema"] == "aoa_course_connection_profile_run_plan_v1"
    assert run_plan["ready"] is True
    assert run_plan["platform"] == "getcourse"
    assert run_plan["source_ids"] == [receipt["applied"][0]["source"]["source_id"]]
    assert run_plan["browser_state_file"] == str(state_file)
    assert run_plan["expect_origin_contains"] == "school.operator.edu"
    assert "calibration connected-run --mode live --allow-network" in run_plan["command"]
    assert readiness["registered_source_count"] == 1
    assert readiness["browser_auth_ready_count"] == 1
    assert readiness["ready_connected_plan_count"] == 1
    assert readiness["blocked_by"] == []
    source_id = str(receipt["applied"][0]["source"]["source_id"])
    browser_auth = receipt["inspection"]["browser_auth"][0]
    assert browser_auth["source_id"] == source_id
    assert f"--source-id {source_id}" in browser_auth["preflight_command"]
    assert receipt["inspection"]["connected_plans"][0]["source_ids"] == [source_id]
    assert any("calibration connected-run --mode live --allow-network" in command for command in readiness["connected_run_commands"])
    assert mcp_plan["tool"] == "connection_profile_run_plan"
    assert mcp_plan["run_plan"]["schema"] == "aoa_course_connection_profile_run_plan_v1"
    assert mcp_plan["run_plan"]["ready"] is True
    assert mcp_plan["run_plan"]["network_touched"] is False
    assert mcp_plan["run_plan"]["platform"] == "getcourse"
    assert mcp_plan["run_plan"]["source_ids"] == [source_id]
    assert "calibration connected-run --mode live --allow-network" in mcp_plan["run_plan"]["command"]
    rendered = json.dumps(receipt)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered
    assert "SUPER_SECRET_COOKIE" not in json.dumps(mcp_plan)
    assert "SUPER_SECRET_TOKEN" not in json.dumps(mcp_plan)


def test_connect_run_executes_ready_profile_with_network_gate(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(tmp_path / "auth"))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    source_url = "https://school.operator.edu/teach/control/stream"
    profile = build_connection_profile(
        storage,
        name="ready-run",
        getcourse_urls=[source_url],
        run_id="connected-profile-run",
        query="course-specific question",
        link_pattern="*/lessons/*",
        max_lessons=7,
        max_pages=3,
        max_sources=2,
    )
    state_file = default_browser_state_path(storage.auth, "getcourse", source_url)
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )
    profile_path = tmp_path / "artifacts" / "connections" / "ready-run.connection-profile.json"
    write_connection_profile(profile, profile_path)
    apply_connection_profile(storage, load_connection_profile(profile_path), profile_path=profile_path)
    captured: dict[str, object] = {}

    def fake_run_connected_calibration(roots_arg, **kwargs):
        captured["roots"] = roots_arg
        captured["kwargs"] = kwargs
        return {
            "schema": "aoa_course_connected_calibration_run_receipt_v1",
            "status": "ok",
            "network_touched": True,
            "run_id": kwargs["run_id"],
        }

    monkeypatch.setattr(cli_module, "run_connected_calibration", fake_run_connected_calibration)

    result = cli_module.cmd_connect_run(
        types.SimpleNamespace(
            profile=profile_path,
            platform="getcourse",
            source_id=None,
            allow_network=True,
            require_ready=False,
        )
    )

    output = json.loads(capsys.readouterr().out)
    kwargs = captured["kwargs"]
    assert result == 0
    assert output["schema"] == "aoa_course_connection_profile_run_receipt_v1"
    assert output["status"] == "ok"
    assert output["executed"] is True
    assert output["network_touched"] is True
    assert output["run_plan"]["ready"] is True
    assert output["connected_run"]["run_id"] == "connected-profile-run"
    assert kwargs["run_id"] == "connected-profile-run"
    assert kwargs["platforms"] == ["getcourse"]
    assert kwargs["allow_network"] is True
    assert kwargs["browser_state_file"] == state_file
    assert kwargs["expect_origin_contains"] == "school.operator.edu"
    assert kwargs["link_pattern"] == "*/lessons/*"
    assert kwargs["max_lessons"] == 7
    assert kwargs["max_pages"] == 3
    assert kwargs["max_sources"] == 2
    rendered = json.dumps(output)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_capture_browser_state_receipt_verifies_expected_origin(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "auth" / "getcourse" / "account.storage-state.json"

    class FakePage:
        url = "https://school.example/cms/system/login"

        def goto(self, *_args, **_kwargs) -> None:
            return None

        def title(self) -> str:
            return "Login"

    class FakeContext:
        def new_page(self) -> FakePage:
            return FakePage()

        def storage_state(self, *, path: str) -> None:
            Path(path).write_text(
                json.dumps({
                    "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.example", "path": "/"}],
                    "origins": [{"origin": "https://school.example", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
                }),
                encoding="utf-8",
            )

    class FakeBrowser:
        def new_context(self) -> FakeContext:
            return FakeContext()

        def close(self) -> None:
            return None

    class FakeChromium:
        def launch(self, *, headless: bool = False) -> FakeBrowser:
            assert headless is True
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeSyncPlaywright:
        def __enter__(self) -> FakePlaywright:
            return FakePlaywright()

        def __exit__(self, *_args) -> None:
            return None

    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: FakeSyncPlaywright()
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    receipt = capture_browser_state(
        tmp_path / "auth",
        "getcourse",
        "https://school.example",
        "https://school.example/cms/system/login",
        state_file=state_file,
        headless=True,
        pause=lambda _page_info: None,
    )
    alias = capture_browser_state(
        tmp_path / "auth",
        "getcourse",
        "account",
        "https://school.example/cms/system/login",
        state_file=state_file,
        headless=True,
        pause=lambda _page_info: None,
    )
    mismatch = capture_browser_state(
        tmp_path / "auth",
        "getcourse",
        "account",
        "https://school.example/cms/system/login",
        state_file=state_file,
        headless=True,
        expect_origin_contains="other.example",
        pause=lambda _page_info: None,
    )

    assert receipt["status"] == "ok"
    assert receipt["expected_origin_contains"] == "school.example"
    assert receipt["expected_origin_matched"] is True
    assert receipt["state"]["expected_origin_matched"] is True
    assert alias["status"] == "ok"
    assert alias["expected_origin_contains"] == "school.example"
    assert alias["expected_origin_matched"] is True
    assert mismatch["status"] == "warning"
    assert mismatch["expected_origin_contains"] == "other.example"
    assert mismatch["expected_origin_matched"] is False
    rendered = json.dumps(receipt) + json.dumps(alias) + json.dumps(mismatch)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_import_firefox_state_writes_redacted_browser_state(tmp_path: Path) -> None:
    profile = tmp_path / "firefox/example.default-release"
    profile.mkdir(parents=True)
    db_path = profile / "cookies.sqlite"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE moz_cookies (
              id INTEGER PRIMARY KEY,
              name TEXT,
              value TEXT,
              host TEXT,
              path TEXT,
              expiry INTEGER,
              isSecure INTEGER,
              isHttpOnly INTEGER
            )
            """
        )
        connection.execute(
            "INSERT INTO moz_cookies (name, value, host, path, expiry, isSecure, isHttpOnly) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sessionid", "SUPER_SECRET_STEPIK_COOKIE", ".stepik.org", "/", 1999999999, 1, 1),
        )
        connection.execute(
            "INSERT INTO moz_cookies (name, value, host, path, expiry, isSecure, isHttpOnly) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("other", "OTHER_SECRET_COOKIE", ".example.org", "/", 1999999999, 1, 1),
        )
        connection.commit()
    finally:
        connection.close()
    state_file = tmp_path / "auth/stepik/account.storage-state.json"

    receipt = import_firefox_browser_state(
        tmp_path / "auth",
        "stepik",
        "account",
        state_file=state_file,
        profile_dir=profile,
        expect_origin_contains="stepik.org",
    )

    assert receipt["schema"] == "aoa_course_firefox_state_import_receipt_v1"
    assert receipt["status"] == "ok"
    assert receipt["network_touched"] is False
    assert receipt["firefox_profile"]["matched_cookie_count"] == 1
    assert receipt["privacy"]["cookie_values_logged"] is False
    assert state_file.exists()
    status = inspect_browser_state(state_file, expect_origin_contains="stepik.org")
    assert status["status"] == "ok"
    assert browser_state_cookie_header(state_file, "stepik.org") == "sessionid=SUPER_SECRET_STEPIK_COOKIE"
    rendered = json.dumps(receipt) + json.dumps(status)
    assert "SUPER_SECRET_STEPIK_COOKIE" not in rendered
    assert "OTHER_SECRET_COOKIE" not in state_file.read_text(encoding="utf-8")


def test_import_firefox_state_normalizes_session_cookie_expiry_for_playwright(tmp_path: Path) -> None:
    profile = tmp_path / "firefox/example.default-release"
    profile.mkdir(parents=True)
    db_path = profile / "cookies.sqlite"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE moz_cookies (
              id INTEGER PRIMARY KEY,
              name TEXT,
              value TEXT,
              host TEXT,
              path TEXT,
              expiry INTEGER,
              isSecure INTEGER,
              isHttpOnly INTEGER
            )
            """
        )
        connection.execute(
            "INSERT INTO moz_cookies (name, value, host, path, expiry, isSecure, isHttpOnly) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sessionid", "SUPER_SECRET_STEPIK_COOKIE", ".stepik.org", "/", 0, 1, 1),
        )
        connection.execute(
            "INSERT INTO moz_cookies (name, value, host, path, expiry, isSecure, isHttpOnly) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("persistent", "SUPER_SECRET_PERSISTENT_COOKIE", ".stepik.org", "/", 1_999_999_999_000, 1, 1),
        )
        connection.execute(
            "INSERT INTO moz_cookies (name, value, host, path, expiry, isSecure, isHttpOnly) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("far_future", "SUPER_SECRET_FAR_FUTURE_COOKIE", ".stepik.org", "/", 253_402_300_799, 1, 1),
        )
        connection.commit()
    finally:
        connection.close()
    state_file = tmp_path / "auth/stepik/account.storage-state.json"

    receipt = import_firefox_browser_state(
        tmp_path / "auth",
        "stepik",
        "account",
        state_file=state_file,
        profile_dir=profile,
        expect_origin_contains="stepik.org",
    )

    state = json.loads(state_file.read_text(encoding="utf-8"))
    expires_by_name = {cookie["name"]: cookie["expires"] for cookie in state["cookies"]}
    assert receipt["status"] == "ok"
    assert expires_by_name["sessionid"] == -1
    assert expires_by_name["persistent"] == 1_999_999_999
    assert expires_by_name["far_future"] == 253_402_300_799


def test_import_firefox_state_uses_stepik_host_for_numeric_source_ref(tmp_path: Path) -> None:
    profile = tmp_path / "firefox/example.default-release"
    profile.mkdir(parents=True)
    db_path = profile / "cookies.sqlite"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE moz_cookies (
              id INTEGER PRIMARY KEY,
              name TEXT,
              value TEXT,
              host TEXT,
              path TEXT,
              expiry INTEGER,
              isSecure INTEGER,
              isHttpOnly INTEGER
            )
            """
        )
        connection.execute(
            "INSERT INTO moz_cookies (name, value, host, path, expiry, isSecure, isHttpOnly) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sessionid", "SUPER_SECRET_STEPIK_COOKIE", ".stepik.org", "/", 0, 1, 1),
        )
        connection.commit()
    finally:
        connection.close()
    state_file = tmp_path / "auth/stepik/67.storage-state.json"

    receipt = import_firefox_browser_state(
        tmp_path / "auth",
        "stepik",
        "67",
        state_file=state_file,
        profile_dir=profile,
    )

    assert receipt["status"] == "ok"
    assert receipt["expected_origin_contains"] == "stepik.org"
    assert browser_state_cookie_header(state_file, "stepik.org") == "sessionid=SUPER_SECRET_STEPIK_COOKIE"


def test_connected_query_run_catalog_counts_invalid_cached_answer_ready(tmp_path: Path) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    receipt_dir = storage.artifact / "runs" / "invalid-answer-ready" / "connected"
    receipt_dir.mkdir(parents=True)
    receipt_path = receipt_dir / "connected_calibration_receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "run_id": "invalid-answer-ready",
                "status": "ok",
                "completed_at": "2026-07-08T12:00:00Z",
                "query_plan": {
                    "entries": [
                        {
                            "source_id": "source:stepik:67",
                            "platform": "stepik",
                            "kind": "smoke",
                            "query": "course-specific evidence",
                            "query_mode": "keyword",
                            "query_ready": True,
                            "answer_ready": True,
                            "answer_result_count": 0,
                            "answer_evidence_count": 0,
                            "paths": _write_query_artifact_paths(storage, "invalid-answer-ready"),
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    catalog = connected_query_run_catalog(storage, receipt_limit=3)
    entry = catalog["by_source_id"]["source:stepik:67"][0]

    assert entry["answer_ready"] is True
    assert entry["answer_result_count"] == 0
    assert entry["answer_evidence_count"] == 0
    assert catalog["answer_ready_entry_count"] == 0
    assert catalog["invalid_answer_ready_entry_count"] == 1


def test_connected_query_run_catalog_prefers_smoke_entries_before_slicing(tmp_path: Path) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    receipt_dir = storage.artifact / "runs" / "same-time-connected" / "connected"
    receipt_dir.mkdir(parents=True)
    receipt_path = receipt_dir / "connected_calibration_receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "run_id": "same-time-connected",
                "status": "ok",
                "started_at": "2026-07-08T12:00:00Z",
                "completed_at": "2026-07-08T12:00:00Z",
                "query_plan": {
                    "entries": [
                        {
                            "source_id": "source:stepik:67",
                            "platform": "stepik",
                            "kind": "sync",
                            "run_id": "stepik-sync-67",
                            "query": "course-specific question",
                            "query_mode": "keyword",
                            "query_ready": True,
                            "paths": _write_query_artifact_paths(storage, "stepik-sync-67"),
                        },
                        {
                            "source_id": "source:stepik:67",
                            "platform": "stepik",
                            "kind": "smoke",
                            "run_id": "stepik-smoke-67",
                            "query": "Stepik public API evidence",
                            "query_mode": "keyword",
                            "query_ready": True,
                            "paths": _write_query_artifact_paths(storage, "stepik-smoke-67"),
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    catalog = connected_query_run_catalog(storage, receipt_limit=3, per_source_limit=1)
    [entry] = catalog["by_source_id"]["source:stepik:67"]

    assert entry["kind"] == "smoke"
    assert entry["query"] == "Stepik public API evidence"


def test_connected_query_run_catalog_preserves_entry_status_and_coverage_counts(tmp_path: Path) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    receipt_dir = storage.artifact / "runs" / "partial-run-ok-entry" / "connected"
    receipt_dir.mkdir(parents=True)
    receipt_path = receipt_dir / "connected_calibration_receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "run_id": "partial-run-ok-entry",
                "status": "partial",
                "completed_at": "2026-07-08T12:00:00Z",
                "query_plan": {
                    "entries": [
                        {
                            "source_id": "source:stepik:67",
                            "platform": "stepik",
                            "kind": "sync",
                            "run_id": "stepik-sync-67",
                            "status": "ok",
                            "query": "course-specific evidence",
                            "query_mode": "hybrid",
                            "query_ready": True,
                            "semantic_query_ready": True,
                            "graph_ready": True,
                            "answer_ready": False,
                            "paths": _write_query_artifact_paths(storage, "stepik-sync-67"),
                            "stable_identity": {
                                "schema": "aoa_course_stable_identity_summary_v1",
                                "available": True,
                                "fingerprint": "sha256:123",
                                "counts": {
                                    "course_ids": 1,
                                    "module_ids": 3,
                                    "lesson_ids": 28,
                                    "step_ids": 174,
                                    "asset_ids": 74,
                                    "assignment_ids": 145,
                                    "evidence_ids": 203,
                                },
                            },
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    catalog = connected_query_run_catalog(storage, receipt_limit=3)
    entry = catalog["by_source_id"]["source:stepik:67"][0]

    assert entry["connected_run_status"] == "partial"
    assert entry["status"] == "ok"
    assert entry["updated_at"] == "2026-07-08T12:00:00Z"
    assert entry["content_counts"] == {
        "asset_count": 74,
        "assignment_count": 145,
        "course_count": 1,
        "evidence_count": 203,
        "lesson_count": 28,
        "module_count": 3,
        "step_count": 174,
    }
    assert entry["stable_identity"]["fingerprint"] == "sha256:123"
    assert "samples" not in entry["stable_identity"]


def test_sources_answer_matrix_portfolio_refs_are_grounded_and_rank_sorted() -> None:
    refs = _sources_answer_matrix_top_result_refs(
        {
            "responses": [
                {
                    "source_id": "source:stepik:python",
                    "platform": "stepik",
                    "connected_run_id": "run",
                    "answer_packet": {
                        "quality": {
                            "ready": True,
                            "top_result": {
                                "doc_id": "step:python",
                                "score": 0.51,
                                "rank_score": 0.59,
                                "path": ["Python"],
                                "fetched_at": "2026-07-08T00:00:00Z",
                                "freshness_state": "current",
                            }
                        }
                    },
                    "evidence_count": 1,
                },
                {
                    "source_id": "source:stepik:empty",
                    "platform": "stepik",
                    "connected_run_id": "run",
                    "answer_packet": {"quality": {"top_result": {}}},
                },
                {
                    "source_id": "source:stepik:csharp",
                    "platform": "stepik",
                    "connected_run_id": "run",
                    "answer_packet": {
                        "quality": {
                            "ready": True,
                            "top_result": {
                                "doc_id": "step:csharp",
                                "score": 0.45,
                                "rank_score": 0.63,
                                "path": ["PRO C#"],
                                "fetched_at": "2026-07-08T00:00:00Z",
                                "freshness_state": "current",
                            }
                        }
                    },
                    "evidence_count": 1,
                },
                {
                    "source_id": "source:stepik:ungrounded",
                    "platform": "stepik",
                    "connected_run_id": "run",
                    "answer_packet": {
                        "quality": {
                            "ready": False,
                            "top_result": {
                                "doc_id": "step:ungrounded",
                                "score": 0.99,
                                "rank_score": 0.99,
                            },
                        }
                    },
                    "evidence_count": 0,
                },
            ]
        },
        grounded_only=True,
    )

    assert [ref["doc_id"] for ref in refs] == ["step:csharp", "step:python"]
    assert all(ref.get("doc_id") for ref in refs)
    assert refs[0]["rank_score"] > refs[1]["rank_score"]


def test_connected_query_run_catalog_reports_unreadable_sync_checkpoint_store(tmp_path: Path) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    receipt_dir = storage.artifact / "runs" / "receipt-ready" / "connected"
    receipt_dir.mkdir(parents=True)
    (receipt_dir / "connected_calibration_receipt.json").write_text(
        json.dumps(
            {
                "run_id": "receipt-ready",
                "status": "ok",
                "completed_at": "2026-07-08T12:00:00Z",
                "query_plan": {
                    "entries": [
                        {
                            "source_id": "source:stepik:67",
                            "platform": "stepik",
                            "kind": "smoke",
                            "query": "course-specific evidence",
                            "query_mode": "keyword",
                            "query_ready": True,
                            "answer_ready": False,
                            "paths": _write_query_artifact_paths(storage, "receipt-ready"),
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    checkpoint_path = storage.data / "sync" / "sync_checkpoints.json"
    checkpoint_path.parent.mkdir(parents=True)
    checkpoint_path.write_text("{not-json", encoding="utf-8")

    catalog = connected_query_run_catalog(storage, receipt_limit=3)

    assert catalog["query_ready_entry_count"] == 1
    assert catalog["sync_checkpoint_count"] == 0
    assert catalog["error_count"] == 1
    assert catalog["errors"][0]["entry_source"] == "sync_checkpoint"
    assert catalog["errors"][0]["path"] == str(checkpoint_path)


def test_import_firefox_state_selects_profile_with_matching_cookies(tmp_path: Path) -> None:
    firefox_root = tmp_path / "firefox"
    empty_profile = firefox_root / "empty.default"
    stepik_profile = firefox_root / "stepik.default"
    empty_profile.mkdir(parents=True)
    stepik_profile.mkdir()
    (firefox_root / "profiles.ini").write_text(
        "\n".join(
            [
                "[Profile0]",
                "Name=empty",
                "IsRelative=1",
                "Path=empty.default",
                "Default=1",
                "",
                "[Profile1]",
                "Name=stepik",
                "IsRelative=1",
                "Path=stepik.default",
            ]
        ),
        encoding="utf-8",
    )
    connection = sqlite3.connect(stepik_profile / "cookies.sqlite")
    try:
        connection.execute(
            """
            CREATE TABLE moz_cookies (
              id INTEGER PRIMARY KEY,
              name TEXT,
              value TEXT,
              host TEXT,
              path TEXT,
              expiry INTEGER,
              isSecure INTEGER,
              isHttpOnly INTEGER
            )
            """
        )
        connection.execute(
            "INSERT INTO moz_cookies (name, value, host, path, expiry, isSecure, isHttpOnly) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sessionid", "SUPER_SECRET_AUTO_PROFILE_COOKIE", ".stepik.org", "/", 1999999999, 1, 1),
        )
        connection.commit()
    finally:
        connection.close()

    receipt = import_firefox_browser_state(
        tmp_path / "auth",
        "stepik",
        "account",
        profiles_ini=firefox_root / "profiles.ini",
        expect_origin_contains="stepik.org",
    )

    assert receipt["status"] == "ok"
    assert receipt["candidate_count"] == 2
    assert receipt["firefox_profile"]["name"] == "stepik"
    assert receipt["firefox_profile"]["matched_cookie_count"] == 1
    assert "SUPER_SECRET_AUTO_PROFILE_COOKIE" not in json.dumps(receipt)


def test_adapter_registry_covers_connector_platform_topology(tmp_path: Path) -> None:
    adapters = {str(adapter["platform"]): adapter for adapter in adapter_list()}
    expected = {
        "getcourse",
        "skillspace",
        "stepik",
        "moodle",
        "canvas",
        "coursera",
        "teachable",
        "thinkific",
        "kajabi",
    }

    assert expected <= set(adapters)
    assert adapters["getcourse"]["status"].startswith("working_")
    assert adapters["skillspace"]["status"].startswith("working_")
    assert adapters["stepik"]["status"] == "working_clean_api_adapter"
    for platform in ["moodle", "canvas", "coursera", "teachable", "thinkific", "kajabi"]:
        assert str(adapters[platform]["status"]).startswith("future_")

    for platform in ["coursera", "teachable", "thinkific", "kajabi"]:
        source, path, state = upsert_source(tmp_path / "data", platform, f"https://{platform}.example/course/demo", platform.title())
        assert state == "added"
        assert source["platform"] == platform
        assert source["access_mode"] == "browser_session"
        assert path.exists()


def test_browser_state_inspect_redacts_secret_material(tmp_path: Path) -> None:
    state_file = tmp_path / "auth" / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        """
{
  "cookies": [
    {
      "name": "session",
      "value": "SUPER_SECRET_COOKIE",
      "domain": ".school.example",
      "path": "/",
      "expires": -1,
      "httpOnly": true,
      "secure": true,
      "sameSite": "Lax"
    }
  ],
  "origins": [
    {
      "origin": "https://school.example",
      "localStorage": [
        {"name": "token", "value": "SUPER_SECRET_TOKEN"}
      ]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    status = inspect_browser_state(state_file, expect_origin_contains="school.example")

    assert status["status"] == "ok"
    assert status["usable"] is True
    assert status["cookie_count"] == 1
    assert status["origin_count"] == 1
    assert status["local_storage_entry_count"] == 1
    assert status["expected_origin_matched"] is True
    rendered = str(status)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_browser_state_inspect_reports_missing_and_origin_mismatch(tmp_path: Path) -> None:
    missing = inspect_browser_state(tmp_path / "missing.storage-state.json")
    assert missing["status"] == "missing"
    assert missing["usable"] is False

    state_file = tmp_path / "account.storage-state.json"
    state_file.write_text('{"cookies": [{"name": "session", "value": "secret"}], "origins": []}', encoding="utf-8")
    mismatch = inspect_browser_state(state_file, expect_origin_contains="school.example")
    assert mismatch["status"] == "mismatch"
    assert mismatch["usable"] is False


def test_browser_state_inspect_rejects_origin_substring_match(tmp_path: Path) -> None:
    state_file = tmp_path / "account.storage-state.json"
    state_file.write_text(
        json.dumps({
            "cookies": [],
            "origins": [{"origin": "https://my-school.example", "localStorage": [{"name": "token", "value": "secret"}]}],
        }),
        encoding="utf-8",
    )

    status = inspect_browser_state(state_file, expect_origin_contains="school.example")

    assert status["status"] == "mismatch"
    assert status["usable"] is False
    assert status["expected_origin_matched"] is False


def test_browser_state_inspect_matches_expected_origin_from_cookie_domain(tmp_path: Path) -> None:
    state_file = tmp_path / "account.storage-state.json"
    state_file.write_text(
        '{"cookies": [{"name": "session", "value": "secret", "domain": ".school.example", "path": "/"}], "origins": []}',
        encoding="utf-8",
    )

    status = inspect_browser_state(state_file, expect_origin_contains="https://school.example/dashboard")

    assert status["status"] == "ok"
    assert status["usable"] is True
    assert status["cookie_count"] == 1
    assert status["origin_count"] == 0
    assert status["expected_origin_matched"] is True


def test_browser_state_inspect_rejects_tracking_only_skillspace_state(tmp_path: Path) -> None:
    state_file = tmp_path / "account.storage-state.json"
    state_file.write_text(
        json.dumps({
            "cookies": [
                {"name": "carrotquest_auth_token", "value": "TRACKING_SECRET", "domain": ".school.skillspace.edu", "path": "/"},
                {"name": "carrotquest_session", "value": "TRACKING_SESSION", "domain": ".school.skillspace.edu", "path": "/"},
            ],
            "origins": [{"origin": "https://school.skillspace.edu", "localStorage": []}],
        }),
        encoding="utf-8",
    )

    status = inspect_browser_state(state_file, expect_origin_contains="school.skillspace.edu", platform="skillspace")

    assert status["status"] == "no_auth_signal"
    assert status["usable"] is False
    assert status["expected_origin_matched"] is True
    assert status["cookie_count"] == 2
    assert status["tracking_cookie_count"] == 2
    assert status["auth_cookie_count"] == 0
    assert status["auth_storage_entry_count"] == 0
    assert status["auth_signal_present"] is False
    rendered = str(status)
    assert "TRACKING_SECRET" not in rendered
    assert "TRACKING_SESSION" not in rendered


def test_browser_state_inspect_rejects_subdomain_cookie_for_parent_origin(tmp_path: Path) -> None:
    state_file = tmp_path / "account.storage-state.json"
    state_file.write_text(
        '{"cookies": [{"name": "session", "value": "secret", "domain": ".login.school.example", "path": "/"}], "origins": []}',
        encoding="utf-8",
    )

    status = inspect_browser_state(state_file, expect_origin_contains="https://school.example")

    assert status["status"] == "mismatch"
    assert status["usable"] is False
    assert status["expected_origin_matched"] is False


def test_stepik_source_defaults_to_public_api(tmp_path: Path) -> None:
    source, _path, state = upsert_source(tmp_path / "data", "stepik", "67", "Stepik Course")
    assert state == "added"
    assert source["access_mode"] == "public_api"


def test_stepik_live_preflight_requires_cookie_header_for_browser_sources(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    source, _path, _state = upsert_source(storage.data, "stepik", "67", "Stepik Browser", access_mode="browser_session")
    state_file = storage.auth / "stepik" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps(
            {
                "cookies": [],
                "origins": [
                    {
                        "origin": "https://stepik.org",
                        "localStorage": [{"name": "session_token", "value": "SUPER_SECRET_TOKEN"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)

    preflight = cli_module.live_preflight(storage, platforms=["stepik"], browser_state_file=state_file)

    browser_state = next(check for check in preflight["checks"] if check["kind"] == "browser_state")
    source_check = next(check for check in preflight["checks"] if check["kind"] == "source" and check["source_id"] == source["source_id"])
    assert browser_state["usable"] is True
    assert browser_state["ready"] is False
    assert browser_state["status"] == "missing_cookie_header"
    assert browser_state["cookie_header_ready"] is False
    assert "does not contain cookies for stepik.org" in browser_state["cookie_header_error"]
    assert source_check["ready"] is False
    assert "browser storage state is missing_cookie_header" in source_check["blockers"]


def test_mcp_connected_source_plan_exposes_ready_subset_without_secret_values(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
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
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))
    monkeypatch.delenv("STEPIK_API_TOKEN", raising=False)

    result = call_tool("connected_source_plan", {"query": "course-specific question", "max_lessons": 7, "max_pages": 3})

    plan = result["plan"]
    connected_run = plan["connected_run_plan"]
    assert result["tool"] == "connected_source_plan"
    assert plan["status"] == "partial"
    assert plan["ready"] is False
    assert connected_run["ready"] is True
    assert connected_run["scope"] == "ready_subset"
    assert connected_run["covers_all_selected"] is False
    assert connected_run["platforms"] == ["getcourse"]
    assert connected_run["selected_platforms"] == ["getcourse", "skillspace", "stepik"]
    assert connected_run["source_ids"] == [source["source_id"]]
    assert connected_run["mcp_tool_call"]["arguments"]["platforms"] == ["getcourse"]
    assert connected_run["mcp_tool_call"]["arguments"]["source_ids"] == [source["source_id"]]
    assert "skillspace workflow is not ready" in connected_run["blocked_by"]
    assert "stepik workflow is not ready" in connected_run["blocked_by"]
    rendered = json.dumps(result)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_mcp_tools_and_search(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_graph(storage, run_id="starter-fixture")
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))
    assert any(tool["name"] == "connector_readiness" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "search" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "sync_status" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "list_sources" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "live_preflight" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "connected_source_plan" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "semantic_provider_preflight" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "browser_snapshot_audit" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "connection_profile_run_plan" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "connected_run" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "connected_run_status" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "connected_run_query" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "refresh_plan" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "graph_neighbors" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "freshness_report" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "answer" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "evidence_report" for tool in tools_manifest()["tools"])
    ingest = call_tool("ingest_status", {"run": "starter-fixture"})
    assert ingest["schema"] == "aoa_course_ingest_status_v1"
    assert ingest["status"] == "ready"
    assert ingest["network_touched"] is False
    assert ingest["readiness"]["agent_query_ready"] is True
    assert ingest["normalized"]["counts"]["courses"] == 1
    assert ingest["normalized"]["counts"]["lessons"] >= 1
    assert ingest["normalized"]["fetched_at"]["latest"] == "2026-06-29T12:00:00Z"
    assert ingest["indexes"]["keyword"]["doc_count"] >= 1
    assert ingest["indexes"]["semantic"]["exists"] is False
    assert ingest["graph"]["node_count"] >= 1
    assert ingest["receipts"][0]["schema"] == "aoa_course_materialize_receipt_v1"
    assert any(command == "aoa-course build-semantic-index --run starter-fixture" for command in ingest["next_commands"])
    missing_ingest = call_tool("ingest_status", {"run": "missing-run"})
    assert missing_ingest["status"] == "missing"
    assert missing_ingest["readiness"]["agent_query_ready"] is False
    assert missing_ingest["next_commands"]
    result = call_tool("search", {"query": "rollback", "run": "starter-fixture"})
    assert result["results"]
    answer = call_tool("answer", {"query": "bootloader rollback", "run": "starter-fixture", "mode": "keyword"})
    assert answer["tool"] == "answer"
    assert answer["answer_packet"]["schema"] == "aoa_course_answer_packet_v1"
    assert answer["answer_packet"]["quality"]["ready"] is True
    assert answer["answer_packet"]["evidence_chain"]
    assert answer["answer_packet"]["refresh_report"]["network_touched"] is False
    graph = call_tool("graph_neighbors", {"node_id": "lesson:starter:unlock-risk", "run": "starter-fixture"})
    assert graph["graph"]["node"]["node_id"] == "lesson:starter:unlock-risk"
    assert graph["graph"]["neighbors"]
    context = call_tool("lesson_context", {"query": "bootloader rollback", "run": "starter-fixture", "graph_limit": 6})
    assert context["lesson_context"]["schema"] == "aoa_course_lesson_context_packet_v1"
    assert context["answer_packet"]["evidence_chain"]
    assert context["answer_packet"]["quality"]["ready"] is True
    assert context["answer_packet"]["quality"]["evidence_count"] == len(context["answer_packet"]["evidence_chain"])
    assert context["lesson_context"]["answer_packet"] == context["answer_packet"]
    assert context["lesson_context"]["graph_context"] == context["graph_context"]
    assert context["graph_context"]["schema"] == "aoa_course_lesson_graph_context_v1"
    assert context["graph_context"]["status"] == "ready"
    assert context["graph_context"]["contexts"][0]["evidence_id"] == context["answer_packet"]["evidence_chain"][0]["evidence_id"]
    assert context["graph_context"]["contexts"][0]["node_id"] == context["answer_packet"]["evidence_chain"][0]["lesson_id"]
    assert context["graph_context"]["contexts"][0]["graph"]["node"]["kind"] == "lesson"
    assert context["graph_context"]["contexts"][0]["graph"]["neighbors"]
    freshness = call_tool("freshness_report", {"run": "starter-fixture"})
    assert freshness["freshness"]["states"]
    evidence = call_tool("evidence_report", {"query": "rollback", "run": "starter-fixture"})
    assert evidence["evidence_chain"]
    assert evidence["quality"]["schema"] == "aoa_course_answer_quality_summary_v1"
    assert evidence["quality"]["ready"] is True
    assert evidence["quality"]["result_count"] == evidence["result_count"]
    assert evidence["quality"]["evidence_count"] == len(evidence["evidence_chain"])
    assert evidence["quality"]["top_result"]["doc_id"] == evidence["result_refs"][0]["doc_id"]
    assert evidence["freshness_report"]["has_source_timestamps"] is True
    assert evidence["refresh_report"]["local_rebuild_commands"]
    assert evidence["result_refs"][0]["evidence_id"]
    assert evidence["evidence_chain"][0]["freshness_state"]
    assert evidence["evidence_chain"][0]["authority_tier"]
    assert evidence["evidence_chain"][0]["rank_score"] == evidence["result_refs"][0]["rank_score"]
    assert evidence["evidence_chain"][0]["snippet"] == evidence["result_refs"][0]["snippet"]
    assert evidence["result_refs"][0]["rank_features"]["provenance_complete"] is True

    assert evidence["result_refs"][0]["refresh_hint"]["schema"] == "aoa_course_refresh_hint_v1"
    snapshot_audit = call_tool(
        "browser_snapshot_audit",
        {
            "snapshot_path": str(find_repo_root() / "connector/fixtures/browser/getcourse_starter_snapshot.json"),
            "platform": "getcourse",
        },
    )
    rendered_audit = json.dumps(snapshot_audit)
    assert snapshot_audit["tool"] == "browser_snapshot_audit"
    assert snapshot_audit["audit"]["schema"] == "aoa_course_browser_snapshot_audit_v1"
    assert snapshot_audit["audit"]["network_touched"] is False
    assert snapshot_audit["audit"]["readiness"]["ready_for_materialize"] is True
    assert snapshot_audit["audit"]["privacy"]["raw_html_included"] is False
    assert "rollback index" not in rendered_audit
    checkpoint = make_checkpoint(
        source={"source_id": "source:getcourse:test", "platform": "getcourse", "source_ref": "https://school.example", "access_mode": "browser_session"},
        sync_run_id="browser-sync-fixture",
        run_id="browser-sync-fixture-source",
        status="ok",
    )
    upsert_checkpoint(storage, checkpoint)
    sync_status = call_tool("sync_status", {"sync_run": "browser-sync-fixture"})
    assert sync_status["sync"]["ok_count"] == 1
    upsert_source(storage.data, "getcourse", "https://school.example", "School")
    plan = call_tool("connected_source_plan", {"platforms": ["getcourse"], "query": "rollback"})
    assert plan["tool"] == "connected_source_plan"
    assert plan["plan"]["network_touched"] is False
    assert plan["plan"]["live_scope"] == "bounded"
    assert plan["plan"]["source_plans"]
    mcp_connected_run = call_tool(
        "connected_run",
        {"run": "mcp-connected-run-tool", "mode": "fixture", "platforms": ["stepik"], "query": "Stepik public API evidence"},
    )
    assert mcp_connected_run["tool"] == "connected_run"
    assert mcp_connected_run["connected_run"]["schema"] == "aoa_course_connected_calibration_run_receipt_v1"
    assert mcp_connected_run["connected_run"]["status"] == "ok"
    assert mcp_connected_run["connected_run"]["network_touched"] is False
    assert Path(str(mcp_connected_run["connected_run"]["receipt_path"])).is_file()
    mcp_connected_query = call_tool("connected_run_query", {"run": "mcp-connected-run-tool", "kinds": ["smoke"]})
    assert mcp_connected_query["tool"] == "connected_run_query"
    assert mcp_connected_query["query_packet"]["schema"] == "aoa_course_connected_run_query_packet_v1"
    assert mcp_connected_query["query_packet"]["status"] == "ok"
    assert mcp_connected_query["query_packet"]["network_touched"] is False
    assert mcp_connected_query["query_packet"]["response_count"] == 1
    assert mcp_connected_query["query_packet"]["quality"]["ready"] is True
    assert mcp_connected_query["query_packet"]["responses"][0]["answer_packet"]["schema"] == "aoa_course_answer_packet_v1"
    assert mcp_connected_query["query_packet"]["responses"][0]["lesson_context"]["schema"] == "aoa_course_lesson_context_packet_v1"
    assert mcp_connected_query["query_packet"]["responses"][0]["evidence_report"]["result_refs"]
    mcp_connected_matrix = call_tool(
        "connected_run_query_matrix",
        {
            "run": "mcp-connected-run-tool",
            "kinds": ["smoke"],
            "queries": ["Stepik public API evidence", "canonical course objects"],
        },
    )
    assert mcp_connected_matrix["tool"] == "connected_run_query_matrix"
    assert mcp_connected_matrix["query_matrix"]["schema"] == "aoa_course_connected_run_query_matrix_v1"
    assert mcp_connected_matrix["query_matrix"]["status"] == "ok"
    assert mcp_connected_matrix["query_matrix"]["network_touched"] is False
    assert mcp_connected_matrix["query_matrix"]["query_count"] == 2
    assert mcp_connected_matrix["query_matrix"]["quality"]["ready"] is True
    assert mcp_connected_matrix["query_matrix"]["quality"]["all_queries_have_evidence"] is True
    missing_connected_run = call_tool("connected_run_status", {"run": "missing-connected-run"})
    assert missing_connected_run["tool"] == "connected_run_status"
    assert missing_connected_run["connected_run"]["status"] == "missing"
    run_connected_calibration(storage, mode="fixture", platforms=["stepik"])
    default_connected_run = call_tool("connected_run_status", {})
    assert default_connected_run["tool"] == "connected_run_status"
    assert default_connected_run["connected_run"]["status"] == "ok"
    assert default_connected_run["connected_run"]["run_id"] == "connected-calibration"
    assert default_connected_run["connected_run"]["network_touched"] is False
    run_connected_calibration(storage, run_id="mcp-connected-fixture", mode="fixture", platforms=["stepik"])
    connected_run = call_tool("connected_run_status", {"run": "mcp-connected-fixture"})
    assert connected_run["connected_run"]["schema"] == "aoa_course_connected_calibration_run_status_v1"
    assert connected_run["connected_run"]["status"] == "ok"
    assert connected_run["connected_run"]["network_touched"] is False
    readiness = call_tool("connector_readiness", {"runs": ["starter-fixture"], "connected_run": "mcp-connected-fixture"})
    assert readiness["schema"] == "aoa_course_connector_readiness_v1"
    assert readiness["network_touched"] is False
    assert readiness["operational_ready"] is True
    assert readiness["connected_live_ready"] is False
    assert readiness["connected_live_ready"] == readiness["lanes"]["connected_live_ready"]
    assert readiness["lanes"]["agent_query_ready"] is True
    assert readiness["lanes"]["mcp_tools_ready"] is True
    assert readiness["connected_run"]["status"] == "ok"
    assert readiness["mcp"]["missing_tools"] == []
    assert readiness["runs"][0]["readiness"]["agent_query_ready"] is True
    refresh = call_tool("refresh_plan", {"query": "rollback", "run": "starter-fixture", "mode": "keyword"})
    assert refresh["tool"] == "refresh_plan"
    assert refresh["refresh"]["schema"] == "aoa_course_refresh_cycle_v1"
    assert refresh["refresh"]["status"] == "planned"
    assert refresh["refresh"]["network_touched"] is False
    assert any("lesson-context" in command for command in refresh["refresh"]["planned_commands"]["local_query_commands"])


def test_mcp_list_sources_returns_filtered_read_only_catalog(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    getcourse, _, _ = upsert_source(storage.data, "getcourse", "https://school.example/teach/control/stream", "School")
    disabled, _, _ = upsert_source(storage.data, "skillspace", "https://academy.example/course/demo", "Disabled", enabled=False)
    stepik, _, _ = upsert_source(storage.data, "stepik", "67", "Stepik Public", access_mode="public_api")
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))
    monkeypatch.setenv("STEPIK_API_TOKEN", "SUPER_SECRET_STEPIK_TOKEN")

    result = call_tool("list_sources", {"platforms": ["getcourse"], "include_source_refs": False})

    catalog = result["catalog"]
    rendered = json.dumps(result)
    assert result["tool"] == "list_sources"
    assert catalog["schema"] == "aoa_course_source_registry_list_v1"
    assert catalog["network_touched"] is False
    assert catalog["read_only"] is True
    assert catalog["contains_secret_values"] is False
    assert catalog["source_refs_included"] is False
    assert catalog["selected_platforms"] == ["getcourse"]
    assert catalog["source_count"] == 3
    assert catalog["enabled_source_count"] == 2
    assert catalog["selected_source_count"] == 1
    assert catalog["sources"][0]["source_id"] == getcourse["source_id"]
    assert "source_ref" not in catalog["sources"][0]
    assert "source_ref" not in result["registry"]["sources"][0]
    assert "SUPER_SECRET_STEPIK_TOKEN" not in rendered

    selected = call_tool("list_sources", {"source_ids": [stepik["source_id"]]})
    assert selected["catalog"]["selected_source_ids"] == [stepik["source_id"]]
    assert selected["catalog"]["selected_source_count"] == 1
    assert selected["catalog"]["sources"][0]["source_ref"] == "67"

    with_disabled = call_tool("list_sources", {"source_ids": [disabled["source_id"]], "include_disabled": True})
    assert with_disabled["catalog"]["selected_source_count"] == 1
    assert with_disabled["catalog"]["sources"][0]["enabled"] is False

    missing = call_tool("list_sources", {"source_ids": ["source:stepik:missing"]})
    assert missing["catalog"]["missing_source_ids"] == ["source:stepik:missing"]
    assert missing["catalog"]["selected_source_count"] == 0

    connected_receipt = run_connected_calibration(
        storage,
        run_id="source-catalog-connected",
        mode="fixture",
        platforms=["stepik"],
        query="Stepik public API evidence",
    )
    receipt_path = Path(str(connected_receipt["receipt_path"]))
    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    for entry in receipt_payload["query_plan"]["entries"]:
        entry.get("commands", {}).pop("sources_answer", None)
        entry.get("mcp_commands", {}).pop("source_answer", None)
    receipt_path.write_text(json.dumps(receipt_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    assert "source_answer" not in receipt_path.read_text(encoding="utf-8")
    assert "sources answer" not in receipt_path.read_text(encoding="utf-8")

    with_runs = call_tool(
        "list_sources",
        {
            "source_ids": [stepik["source_id"]],
            "include_source_refs": False,
            "connected_run_limit": 2,
            "connected_receipt_limit": 10,
        },
    )
    run_catalog = with_runs["catalog"]["connected_runs"]
    source = with_runs["catalog"]["sources"][0]
    latest_runs = source["latest_connected_runs"]
    rendered_runs = json.dumps(with_runs)
    assert run_catalog["schema"] == "aoa_course_connected_query_run_catalog_v1"
    assert run_catalog["included"] is True
    assert run_catalog["network_touched"] is False
    assert run_catalog["query_ready_entry_count"] >= 1
    assert run_catalog["answer_ready_entry_count"] >= 1
    assert run_catalog["invalid_answer_ready_entry_count"] == 0
    assert run_catalog["source_ids_with_query_runs"] == [stepik["source_id"]]
    assert source["query_ready_connected_run_count"] >= 1
    assert latest_runs[0]["connected_run_id"] == "source-catalog-connected"
    assert latest_runs[0]["source_id"] == stepik["source_id"]
    assert latest_runs[0]["query_ready"] is True
    assert latest_runs[0]["answer_ready"] is True
    assert latest_runs[0]["answer_result_count"] >= 1
    assert latest_runs[0]["answer_evidence_count"] >= 1
    assert latest_runs[0]["commands"]["sources_answer"].startswith("aoa-course sources answer ")
    assert f"--source-id {stepik['source_id']}" in latest_runs[0]["commands"]["sources_answer"]
    assert "--kind smoke" in latest_runs[0]["commands"]["sources_answer"]
    assert latest_runs[0]["mcp_commands"]["answer"].startswith("aoa-course mcp call answer ")
    assert latest_runs[0]["mcp_commands"]["source_answer"].startswith("aoa-course mcp call source_answer ")
    assert f'"source_id":"{stepik["source_id"]}"' in latest_runs[0]["mcp_commands"]["source_answer"]
    if "stable_identity" in latest_runs[0]:
        assert "fingerprint" in latest_runs[0]["stable_identity"]
        assert "samples" not in latest_runs[0]["stable_identity"]
    assert "source_ref" not in latest_runs[0]
    assert "SUPER_SECRET_STEPIK_TOKEN" not in rendered_runs

    source_answer = call_tool(
        "source_answer",
        {
            "source_id": stepik["source_id"],
            "query": "Stepik public API evidence",
        },
    )
    source_answer_packet = source_answer["source_answer"]
    rendered_source_answer = json.dumps(source_answer)
    assert source_answer["tool"] == "source_answer"
    assert source_answer_packet["schema"] == "aoa_course_source_answer_packet_v1"
    assert source_answer_packet["status"] == "ok"
    assert source_answer_packet["network_touched"] is False
    assert source_answer_packet["read_only"] is True
    assert source_answer_packet["source_refs_included"] is False
    assert source_answer_packet["selected_source"]["source_id"] == stepik["source_id"]
    assert source_answer_packet["selected_entry"]["connected_run_id"] == "source-catalog-connected"
    assert source_answer_packet["query_packet"]["response_count"] == 1
    assert source_answer_packet["answer_packet"]["schema"] == "aoa_course_answer_packet_v1"
    assert source_answer_packet["answer_packet"]["quality"]["ready"] is True
    assert source_answer_packet["lesson_context"]["schema"] == "aoa_course_lesson_context_packet_v1"
    assert source_answer_packet["evidence_report"]["result_refs"]
    assert source_answer_packet["next_commands"][0].startswith("aoa-course sources answer ")
    assert f"--source-id {stepik['source_id']}" in source_answer_packet["next_commands"][0]
    assert any("source_answer" in command for command in source_answer_packet["next_commands"])
    assert '"source_ref"' not in rendered_source_answer
    assert "SUPER_SECRET_STEPIK_TOKEN" not in rendered_source_answer

    sources_answer = call_tool(
        "sources_answer",
        {
            "source_ids": [stepik["source_id"]],
            "query": "Stepik public API evidence",
        },
    )
    sources_answer_packet = sources_answer["sources_answer"]
    rendered_sources_answer = json.dumps(sources_answer)
    assert sources_answer["tool"] == "sources_answer"
    assert sources_answer_packet["schema"] == "aoa_course_sources_answer_packet_v1"
    assert sources_answer_packet["status"] == "ok"
    assert sources_answer_packet["network_touched"] is False
    assert sources_answer_packet["source_refs_included"] is False
    assert sources_answer_packet["response_count"] == 1
    assert sources_answer_packet["quality"]["ready"] is True
    assert sources_answer_packet["responses"][0]["answer_packet"]["quality"]["ready"] is True
    assert sources_answer_packet["responses"][0]["evidence_report"]["result_refs"]
    assert sources_answer_packet["next_commands"][0].startswith("aoa-course sources answer ")
    assert f"--source-id {stepik['source_id']}" in sources_answer_packet["next_commands"][0]
    assert '"source_ref"' not in rendered_sources_answer
    assert "SUPER_SECRET_STEPIK_TOKEN" not in rendered_sources_answer

    sources_answer_matrix = call_tool(
        "sources_answer_matrix",
        {
            "source_ids": [stepik["source_id"]],
            "queries": ["Stepik public API evidence", "canonical course objects"],
            "mode": "hybrid",
        },
    )
    matrix_packet = sources_answer_matrix["sources_answer_matrix"]
    rendered_matrix = json.dumps(sources_answer_matrix)
    assert sources_answer_matrix["tool"] == "sources_answer_matrix"
    assert matrix_packet["schema"] == "aoa_course_sources_answer_matrix_v1"
    assert matrix_packet["status"] == "ok"
    assert matrix_packet["coverage_mode"] == "all-sources"
    assert matrix_packet["network_touched"] is False
    assert matrix_packet["read_only"] is True
    assert matrix_packet["source_refs_included"] is False
    assert matrix_packet["query_count"] == 2
    assert matrix_packet["quality"]["ready"] is True
    assert matrix_packet["quality"]["coverage_mode"] == "all-sources"
    assert matrix_packet["quality"]["source_scoped_ready"] is True
    assert matrix_packet["quality"]["portfolio_ready"] is True
    assert matrix_packet["quality"]["ready_query_count"] == 2
    assert matrix_packet["quality"]["source_scoped_ready_query_count"] == 2
    assert matrix_packet["quality"]["portfolio_ready_query_count"] == 2
    assert matrix_packet["quality"]["evidence_ready_query_count"] == 2
    assert matrix_packet["quality"]["all_queries_have_evidence"] is True
    assert matrix_packet["query_packets"][0]["schema"] == "aoa_course_sources_answer_packet_v1"
    assert matrix_packet["query_summaries"][0]["top_result_refs"]
    assert matrix_packet["next_commands"][0].startswith("aoa-course sources answer-matrix ")
    assert any("sources_answer_matrix" in command for command in matrix_packet["next_commands"])
    assert '"source_ref"' not in rendered_matrix
    assert "SUPER_SECRET_STEPIK_TOKEN" not in rendered_matrix

    partial_sources_answer = call_tool("sources_answer", {"query": "Stepik public API evidence"})
    assert partial_sources_answer["sources_answer"]["status"] == "partial"
    assert partial_sources_answer["sources_answer"]["response_count"] == 1
    assert partial_sources_answer["sources_answer"]["blocked_source_count"] == 1
    assert partial_sources_answer["sources_answer"]["blocked_sources"][0]["reason"] == "no_query_ready_connected_run"

    ambiguous = call_tool("source_answer", {"query": "Stepik public API evidence"})
    assert ambiguous["source_answer"]["status"] == "blocked"
    assert ambiguous["source_answer"]["reason"] == "ambiguous_source"
    assert ambiguous["source_answer"]["candidate_source_count"] == 2
    assert '"source_ref"' not in json.dumps(ambiguous)


def test_browser_registry_source_rejects_source_id_source_ref_mismatch(tmp_path: Path) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    source, _, _ = upsert_source(storage.data, "getcourse", "https://school.example/teach/control/stream", "School")

    with pytest.raises(ValueError, match="source_ref_mismatch"):
        cli_module._browser_registry_source(
            storage,
            platform="getcourse",
            source_ref="https://other.example/teach/control/stream",
            source_id=str(source["source_id"]),
        )


def test_sources_answer_matrix_portfolio_mode_allows_relevant_source_coverage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(tmp_path / "auth"))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    run_connected_calibration(
        storage,
        run_id="portfolio-coverage-stepik",
        mode="fixture",
        platforms=["stepik"],
        query="Stepik public API evidence",
    )
    empty_source, _, _ = upsert_source(storage.data, "stepik", "empty-query-ready-source", "Empty Query Ready", access_mode="public_api")
    empty_run_id = "portfolio-empty-query-ready"
    normalized_dir = run_data_dir(storage, empty_run_id) / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = normalized_dir / "course_bundle.json"
    normalized_path.write_text(
        json.dumps(
            {
                "schema": "aoa_course_bundle_v1",
                "source": empty_source,
                "courses": [],
                "evidence": [],
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    index_path = build_keyword_index(storage, empty_run_id)
    semantic_index_path = build_semantic_index(storage, empty_run_id)
    graph_path = build_graph(storage, empty_run_id)
    upsert_checkpoint(
        storage,
        make_checkpoint(
            source=empty_source,
            sync_run_id="portfolio-empty-sync",
            run_id=empty_run_id,
            status="ok",
            normalized_path=str(normalized_path),
            index_path=str(index_path),
            semantic_index_path=str(semantic_index_path),
            graph_path=str(graph_path),
        ),
    )
    stepik_source = next(source for source in load_registry(storage.data)["sources"] if source["platform"] == "stepik" and source["source_ref"] == "67")
    args = {
        "source_ids": [stepik_source["source_id"], empty_source["source_id"]],
        "queries": ["Stepik public API evidence", "canonical course objects"],
        "mode": "hybrid",
    }

    strict_packet = call_tool("sources_answer_matrix", args)["sources_answer_matrix"]
    portfolio_packet = call_tool("sources_answer_matrix", {**args, "coverage_mode": "portfolio"})["sources_answer_matrix"]

    assert strict_packet["coverage_mode"] == "all-sources"
    assert strict_packet["status"] == "partial"
    assert strict_packet["quality"]["ready"] is False
    assert strict_packet["quality"]["source_scoped_ready"] is False
    assert strict_packet["quality"]["portfolio_ready"] is True
    assert strict_packet["quality"]["all_queries_have_evidence"] is True
    assert strict_packet["quality"]["all_queries_have_grounded_response"] is True
    assert strict_packet["quality"]["grounded_response_count_total"] >= 2
    assert strict_packet["quality"]["all_grounded_responses_have_path"] is True
    assert strict_packet["quality"]["all_grounded_responses_have_fetched_at"] is True
    assert strict_packet["quality"]["all_grounded_responses_have_freshness"] is True
    assert portfolio_packet["coverage_mode"] == "portfolio"
    assert portfolio_packet["status"] == "ok"
    assert portfolio_packet["quality"]["ready"] is True
    assert portfolio_packet["quality"]["coverage_mode"] == "portfolio"
    assert portfolio_packet["quality"]["source_scoped_ready"] is False
    assert portfolio_packet["quality"]["portfolio_ready"] is True
    assert portfolio_packet["quality"]["ready_query_count"] == 2
    assert portfolio_packet["quality"]["blocked_query_count"] == 0
    assert portfolio_packet["quality"]["source_scoped_ready_query_count"] == 0
    assert portfolio_packet["quality"]["source_scoped_gap_query_count"] == 2
    assert portfolio_packet["quality"]["portfolio_ready_query_count"] == 2
    assert portfolio_packet["quality"]["evidence_ready_query_count"] == 2
    assert portfolio_packet["quality"]["grounded_ready_query_count"] == 2
    assert portfolio_packet["query_summaries"][0]["grounded_response_count"] >= 1
    assert portfolio_packet["query_summaries"][0]["status"] == "ok"
    assert portfolio_packet["query_summaries"][0]["ready"] is True
    assert portfolio_packet["query_summaries"][0]["source_scoped_ready"] is False
    assert portfolio_packet["query_summaries"][0]["portfolio_ready"] is True
    assert portfolio_packet["query_summaries"][0]["top_result_refs"][0]["path"]
    assert portfolio_packet["query_summaries"][0]["top_result_refs"][0]["freshness_state"]
    assert all(ref.get("doc_id") for summary in portfolio_packet["query_summaries"] for ref in summary["top_result_refs"])
    assert any(not ref.get("doc_id") for summary in strict_packet["query_summaries"] for ref in summary["top_result_refs"])
    assert "--coverage-mode portfolio" in portfolio_packet["next_commands"][0]
    assert '"coverage_mode":"portfolio"' in portfolio_packet["next_commands"][1]


def test_source_registry_query_eval_blocks_external_semantic_provider(tmp_path: Path) -> None:
    semantic_index = tmp_path / "semantic_index.json"
    semantic_index.write_text(
        json.dumps(
            {
                "schema": "aoa_course_semantic_index_v1",
                "provider": "http_json_v1",
                "provider_config": {"provider": "http_json_v1", "endpoint_configured": True},
                "docs": [],
            }
        ),
        encoding="utf-8",
    )
    catalog = {
        "connected_runs": {
            "by_source_id": {
                "source:stepik:67": [
                    {
                        "run_id": "connected-stepik",
                        "query_ready": True,
                        "paths": {"semantic_index": str(semantic_index)},
                    }
                ]
            }
        }
    }

    failures = cli_module._source_registry_external_semantic_provider_failures(catalog, "hybrid")

    assert failures == [
        {
            "surface": "connected_runs",
            "source_id": "source:stepik:67",
            "run_id": "connected-stepik",
            "field": "semantic_index.provider",
            "expected": "local_hashing_v1",
            "actual": "http_json_v1",
            "path": str(semantic_index),
            "reason": "external_semantic_provider_requires_network",
            "next_command": "aoa-course build-semantic-index --run connected-stepik --provider local_hashing_v1",
        }
    ]
    assert cli_module._source_registry_external_semantic_provider_failures(catalog, "keyword") == []


def test_source_registry_query_eval_blocks_external_semantic_provider_path_alias(tmp_path: Path) -> None:
    semantic_index = tmp_path / "semantic_index.json"
    semantic_index.write_text(
        json.dumps(
            {
                "schema": "aoa_course_semantic_index_v1",
                "provider": "http_json_v1",
                "provider_config": {"provider": "http_json_v1", "endpoint_configured": True},
                "docs": [],
            }
        ),
        encoding="utf-8",
    )
    catalog = {
        "connected_runs": {
            "by_source_id": {
                "source:stepik:67": [
                    {
                        "run_id": "connected-stepik",
                        "query_ready": True,
                        "paths": {"semantic_index_path": str(semantic_index)},
                    }
                ]
            }
        }
    }

    [failure] = cli_module._source_registry_external_semantic_provider_failures(catalog, "semantic")

    assert failure["path"] == str(semantic_index)
    assert failure["reason"] == "external_semantic_provider_requires_network"


def test_source_registry_query_eval_reads_semantic_alias_from_source_entries(tmp_path: Path) -> None:
    semantic_index = tmp_path / "semantic_index.json"
    semantic_index.write_text(
        json.dumps(
            {
                "schema": "aoa_course_semantic_index_v1",
                "provider": "http_json_v1",
                "provider_config": {"provider": "http_json_v1", "endpoint_configured": True},
                "docs": [],
            }
        ),
        encoding="utf-8",
    )
    catalog = {
        "connected_runs": {
            "schema": "aoa_course_connected_query_run_catalog_v1",
            "query_ready_entry_count": 1,
        },
        "sources": [
            {
                "source_id": "source:stepik:67",
                "latest_connected_runs": [
                    {
                        "connected_run_id": "connected-stepik",
                        "run_id": "stepik-smoke-67",
                        "query_ready": True,
                        "paths": {"semantic_index_path": str(semantic_index)},
                    }
                ],
            }
        ],
    }

    [failure] = cli_module._source_registry_external_semantic_provider_failures(catalog, "hybrid")

    assert failure["surface"] == "sources.latest_connected_runs"
    assert failure["source_id"] == "source:stepik:67"
    assert failure["run_id"] == "stepik-smoke-67"
    assert failure["path"] == str(semantic_index)
    assert failure["reason"] == "external_semantic_provider_requires_network"


def test_sources_answer_blocks_external_semantic_provider_before_query(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    stepik, _, _ = upsert_source(storage.data, "stepik", "67", "Stepik Public", access_mode="public_api")
    receipt = run_connected_calibration(
        storage,
        run_id="external-semantic-provider",
        mode="fixture",
        platforms=["stepik"],
        query="Stepik public API evidence",
    )
    assert receipt["receipt_path"]
    for semantic_path in storage.artifact.glob("runs/**/indexes/semantic_index.json"):
        semantic_path.write_text(
            json.dumps(
                {
                    "schema": "aoa_course_semantic_index_v1",
                    "provider": "http_json_v1",
                    "provider_config": {"provider": "http_json_v1", "endpoint_configured": True},
                    "docs": [],
                }
            ),
            encoding="utf-8",
        )
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    packet = call_tool(
        "sources_answer",
        {"source_ids": [stepik["source_id"]], "query": "Stepik public API evidence", "mode": "hybrid"},
    )["sources_answer"]

    assert packet["status"] == "blocked"
    assert packet["network_touched"] is False
    assert packet["blocked_source_count"] == 1
    assert packet["blocked_sources"][0]["reason"] == "external_semantic_provider_requires_network"
    assert packet["blocked_sources"][0]["query_packet_failures"][0]["actual"] == "http_json_v1"


def test_connector_readiness_accepts_source_registry_query_ready_route(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    stepik, _, _ = upsert_source(storage.data, "stepik", "67", "Stepik Public", access_mode="public_api")
    run_connected_calibration(
        storage,
        run_id="source-registry-query-ready",
        mode="fixture",
        platforms=["stepik"],
        query="Stepik public API evidence",
    )
    run_connected_calibration(
        storage,
        run_id="source-registry-query-ready-second",
        mode="fixture",
        platforms=["stepik"],
        query="canonical course objects",
    )
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    readiness = call_tool(
        "connector_readiness",
        {
            "runs": ["missing-starter-run"],
            "platforms": ["stepik"],
            "connected_run": "missing-connected-run",
        },
    )

    rendered = json.dumps(readiness)
    assert readiness["schema"] == "aoa_course_connector_readiness_v1"
    assert readiness["status"] == "ready"
    assert readiness["operational_ready"] is True
    assert readiness["runs"][0]["status"] == "missing"
    assert readiness["lanes"]["run_agent_query_ready"] is False
    assert readiness["lanes"]["source_registry_query_ready"] is True
    assert readiness["lanes"]["source_registry_query_ready_entry_count"] >= 1
    assert readiness["lanes"]["source_registry_query_ready_source_count"] == 1
    assert readiness["lanes"]["source_registry_answer_ready_entry_count"] >= 1
    assert readiness["lanes"]["source_registry_invalid_answer_ready_entry_count"] == 0
    assert readiness["lanes"]["agent_query_ready"] is True
    assert readiness["sources"]["connected_runs"]["included"] is True
    assert readiness["sources"]["connected_runs"]["query_ready_entry_count"] >= 1
    assert readiness["sources"]["connected_runs"]["invalid_answer_ready_entry_count"] == 0
    assert readiness["sources"]["sources"][0]["source_id"] == stepik["source_id"]
    assert readiness["sources"]["sources"][0]["query_ready_connected_run_count"] >= 1
    assert readiness["sources"]["source_refs_included"] is False
    assert any(command.startswith("aoa-course sources list --no-source-refs") for command in readiness["next_commands"])
    assert any("sources answer " in command and f"--source-id {stepik['source_id']}" in command for command in readiness["next_commands"])
    assert any("sources answer-matrix " in command and f"--source-id {stepik['source_id']}" in command for command in readiness["next_commands"])
    assert not any(command.startswith("aoa-course bootstrap fixture") for command in readiness["next_commands"])
    assert '"source_ref"' not in rendered


def test_connector_readiness_rejects_stale_source_registry_query_artifacts(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    stepik, _, _ = upsert_source(storage.data, "stepik", "67", "Stepik Public", access_mode="public_api")
    receipt = run_connected_calibration(
        storage,
        run_id="source-registry-stale-artifacts",
        mode="fixture",
        platforms=["stepik"],
        query="Stepik public API evidence",
    )
    assert receipt["receipt_path"]
    for index_path in storage.artifact.glob("runs/**/indexes/keyword_index.json"):
        index_path.unlink()
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    readiness = call_tool(
        "connector_readiness",
        {
            "runs": ["missing-starter-run"],
            "platforms": ["stepik"],
            "connected_run": "missing-connected-run",
        },
    )

    assert readiness["lanes"]["source_registry_query_ready"] is False
    assert readiness["lanes"]["source_registry_query_ready_entry_count"] == 0
    assert readiness["lanes"]["agent_query_ready"] is False
    assert readiness["sources"]["connected_runs"]["query_ready_entry_count"] == 0
    assert readiness["sources"]["connected_runs"]["errors"][0]["missing"] == "index_path"
    assert readiness["sources"]["sources"][0]["source_id"] == stepik["source_id"]


def test_cli_sources_answer_omits_mode_when_not_requested(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_call_tool(name: str, args: dict[str, object]) -> dict[str, object]:
        captured["name"] = name
        captured["args"] = args
        return {"sources_answer": {"status": "ok"}}

    monkeypatch.setattr(cli_module, "call_tool", fake_call_tool)

    result = cli_module.cmd_sources_answer(
        Namespace(
            query="course evidence",
            platform=None,
            source_id=None,
            kind=None,
            limit=5,
            mode=None,
            graph_limit=12,
            source_limit=10,
            connected_run_limit=5,
            connected_receipt_limit=50,
            include_disabled=False,
            include_source_refs=False,
        )
    )

    assert result == 0
    assert captured["name"] == "sources_answer"
    assert captured["args"]["mode"] is None
    capsys.readouterr()


def test_mcp_connected_run_live_requires_allow_network(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    upsert_source(storage.data, "stepik", "https://stepik.org/course/67/syllabus", "Stepik Public", access_mode="public_api")
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    result = call_tool(
        "connected_run",
        {"run": "mcp-live-blocked", "mode": "live", "platforms": ["stepik"], "source_limit": 1},
    )

    receipt = result["connected_run"]
    assert result["tool"] == "connected_run"
    assert receipt["schema"] == "aoa_course_connected_calibration_run_receipt_v1"
    assert receipt["status"] == "partial"
    assert receipt["mode"] == "live"
    assert receipt["allow_network"] is False
    assert receipt["network_touched"] is False
    assert any(failure["reason"] == "live mode requires --allow-network" for failure in receipt["failures"])
    assert any(lane["lane"] == "network_gate" for lane in receipt["repair_lanes"])

    status = call_tool("connected_run_status", {"run": "mcp-live-blocked"})
    assert status["connected_run"]["status"] == "partial"
    assert status["connected_run"]["network_touched"] is False


def test_semantic_provider_preflight_redacts_token_values(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    materialize_fixture(storage, run_id="starter-fixture")

    missing = semantic_provider_preflight(
        storage,
        run_id="starter-fixture",
        provider="http_json_v1",
        embedding_endpoint="https://embed.example/v1",
        embedding_model="course-embedding",
        embedding_token_env="AOA_COURSE_TEST_EMBEDDING_TOKEN",
    )
    assert missing["schema"] == "aoa_course_semantic_provider_preflight_v1"
    assert missing["ready"] is False
    assert missing["network_touched"] is False
    assert missing["provider_config"]["token_env_present"] is False
    assert "export AOA_COURSE_TEST_EMBEDDING_TOKEN=<redacted-token>" in missing["next_commands"]

    monkeypatch.setenv("AOA_COURSE_TEST_EMBEDDING_TOKEN", "SUPER_SECRET_EMBEDDING_TOKEN")
    ready = semantic_provider_preflight(
        storage,
        run_id="starter-fixture",
        provider="http_json_v1",
        embedding_endpoint="https://embed.example/v1",
        embedding_model="course-embedding",
        embedding_token_env="AOA_COURSE_TEST_EMBEDDING_TOKEN",
    )
    serialized = json.dumps(ready, sort_keys=True)
    assert ready["ready"] is True
    assert ready["provider_config"]["token_env_present"] is True
    assert ready["provider_config"]["secret_values_logged"] is False
    assert "SUPER_SECRET_EMBEDDING_TOKEN" not in serialized
    assert "build-semantic-index --run starter-fixture --provider http_json_v1" in ready["commands"]["build"]

    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))
    readiness = call_tool(
        "connector_readiness",
        {
            "runs": ["starter-fixture"],
            "semantic_provider": "http_json_v1",
            "embedding_endpoint": "https://embed.example/v1",
            "embedding_model": "course-embedding",
            "embedding_token_env": "AOA_COURSE_TEST_EMBEDDING_TOKEN",
        },
    )
    assert any(
        "build-semantic-index --run starter-fixture --provider http_json_v1" in command
        for command in readiness["next_commands"]
    )
    semantic_build_commands = [
        command
        for command in readiness["next_commands"]
        if command.startswith("aoa-course build-semantic-index --run starter-fixture")
    ]
    assert semantic_build_commands
    assert all("--provider http_json_v1" in command for command in semantic_build_commands)
    assert not any("build-semantic-index --run starter-fixture --provider local_hashing" in command for command in readiness["next_commands"])


def test_ingest_status_treats_corrupt_artifacts_as_not_ready(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_graph(storage, run_id="starter-fixture")
    keyword_path = storage.artifact / "runs" / "starter-fixture" / "indexes" / "keyword_index.json"
    keyword_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    ingest = call_tool("ingest_status", {"run": "starter-fixture"})

    assert ingest["status"] == "partial"
    assert ingest["indexes"]["keyword"]["status"] == "error"
    assert ingest["readiness"]["query_ready"] is False
    assert ingest["readiness"]["agent_query_ready"] is False
    assert any(command == "aoa-course build-index --run starter-fixture" for command in ingest["next_commands"])


def test_connector_readiness_uses_selected_connected_run_in_remediation(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_graph(storage, run_id="starter-fixture")
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    readiness = call_tool("connector_readiness", {"runs": ["starter-fixture"], "connected_run": "custom-connected-run"})

    assert readiness["connected_run"]["status"] == "missing"
    assert readiness["connected_run"]["run_id"] == "custom-connected-run"
    assert any(
        command == "aoa-course bootstrap fixture --connected-run custom-connected-run"
        for command in readiness["next_commands"]
    )
    assert not any("--connected-run connected-calibration" in command for command in readiness["next_commands"])


def test_connector_readiness_surfaces_partial_connected_run_repair_lanes(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_semantic_index(storage, run_id="starter-fixture")
    build_graph(storage, run_id="starter-fixture")
    upsert_source(storage.data, "stepik", "https://stepik.org/course/67/syllabus", "Stepik Public", access_mode="public_api")
    run_connected_calibration(storage, run_id="partial-connected-run", mode="live", platforms=["stepik"])
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    readiness = call_tool(
        "connector_readiness",
        {"runs": ["starter-fixture"], "platforms": ["stepik"], "connected_run": "partial-connected-run"},
    )

    assert readiness["connected_run"]["status"] == "partial"
    assert readiness["connected_run"]["repair_lanes"][0]["lane"] == "network_gate"
    assert readiness["lanes"]["connected_run_receipt_ready"] is False
    assert any(command.startswith("aoa-course preflight connected-plan --platform stepik") for command in readiness["next_commands"])
    assert any("aoa-course calibration connected-run --mode live --allow-network --run partial-connected-run" in command for command in readiness["next_commands"])
    assert not any(
        "aoa-course calibration connected-run --mode live --allow-network --run connected-live-calibration" in command
        for command in readiness["next_commands"]
    )
    assert not any(command == "aoa-course bootstrap fixture --connected-run partial-connected-run" for command in readiness["next_commands"])


def test_mcp_live_preflight_reports_readiness_without_secret_values(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
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
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    result = call_tool(
        "live_preflight",
        {"platforms": ["getcourse"], "state_file": str(state_file), "expect_origin": "school.operator.edu"},
    )

    assert result["tool"] == "live_preflight"
    assert result["preflight"]["ready"] is True
    assert result["preflight"]["network_touched"] is False
    rendered = json.dumps(result)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered

    plan = call_tool(
        "connected_source_plan",
        {
            "platforms": ["getcourse"],
            "state_file": str(state_file),
            "expect_origin": "school.operator.edu",
            "link_pattern": "*/lessons/*",
            "max_lessons": 7,
            "max_pages": 3,
            "max_sources": 4,
        },
    )

    assert plan["tool"] == "connected_source_plan"
    assert plan["plan"]["ready"] is True
    assert plan["plan"]["link_pattern"] == "*/lessons/*"
    assert plan["plan"]["live_scope"] == "bounded"
    assert plan["plan"]["include_step_sources"] is False
    assert plan["plan"]["max_lessons"] == 7
    assert plan["plan"]["max_pages"] == 3
    assert plan["plan"]["max_sources"] == 4
    assert any("smoke browser-live" in command for command in plan["plan"]["next_commands"])
    assert any("--link-pattern '*/lessons/*'" in command for command in plan["plan"]["next_commands"])
    assert any("--max-lessons 7" in command for command in plan["plan"]["next_commands"])
    assert any("--max-pages 3" in command for command in plan["plan"]["next_commands"])
    assert any("--max-sources 4" in command for command in plan["plan"]["next_commands"])
    assert "calibration connected-run --mode live --allow-network" in plan["plan"]["connected_run_plan"]["command"]
    assert "--link-pattern '*/lessons/*'" in plan["plan"]["connected_run_plan"]["command"]
    assert "--max-lessons 7" in plan["plan"]["connected_run_plan"]["command"]
    assert "--max-pages 3" in plan["plan"]["connected_run_plan"]["command"]
    assert "--max-sources 4" in plan["plan"]["connected_run_plan"]["command"]
    plan_mcp_call = plan["plan"]["connected_run_plan"]["mcp_tool_call"]
    assert plan_mcp_call["tool"] == "connected_run"
    assert plan_mcp_call["arguments"]["allow_network"] is True
    assert plan_mcp_call["arguments"]["link_pattern"] == "*/lessons/*"
    assert plan_mcp_call["arguments"]["max_lessons"] == 7
    assert "aoa-course mcp call connected_run" in plan["plan"]["connected_run_plan"]["mcp_command"]
    plan = plan["plan"]["browser_auth_plans"][0]
    assert plan["ready"] is True
    assert plan["source_hosts"] == ["school.operator.edu"]
    assert "capture-browser-state getcourse account" in plan["commands"]["capture"]
    assert plan["state_file_candidates"][0]["host"] == "school.operator.edu"
    assert plan["state_file_candidates"][0]["state_file"].endswith("/getcourse/school-operator-edu.storage-state.json")
    assert plan["state_file_candidates"][0]["selected_by_default"] is False
    assert "--expect-origin-contains school.operator.edu" in plan["commands"]["import_firefox"]
    assert "auth import-firefox-state getcourse school.operator.edu" in plan["state_file_candidates"][0]["commands"]["import_firefox"]
    assert "--expect-origin-contains school.operator.edu" in plan["state_file_candidates"][0]["commands"]["capture"]
    rendered_plan = json.dumps(plan)
    assert "SUPER_SECRET_COOKIE" not in rendered_plan
    assert "SUPER_SECRET_TOKEN" not in rendered_plan

    readiness = call_tool(
        "connector_readiness",
        {
            "platforms": ["getcourse"],
            "state_file": str(state_file),
            "expect_origin": "school.operator.edu",
            "query": "course-specific question",
            "link_pattern": "*/lessons/*",
            "max_lessons": 7,
            "max_pages": 3,
            "max_sources": 4,
            "live_scope": "bounded",
        },
    )
    assert readiness["connected_live_ready"] is True
    assert readiness["connected_live_ready"] == readiness["lanes"]["connected_live_ready"]
    compact_plan = readiness["connected_source_plan"]
    assert compact_plan["link_pattern"] == "*/lessons/*"
    assert compact_plan["live_scope"] == "bounded"
    assert compact_plan["include_step_sources"] is False
    assert compact_plan["max_lessons"] == 7
    assert compact_plan["max_pages"] == 3
    assert compact_plan["max_sources"] == 4
    assert compact_plan["connected_run_plan"]["ready"] is True
    assert "--link-pattern '*/lessons/*'" in compact_plan["connected_run_plan"]["command"]
    assert "--max-lessons 7" in compact_plan["connected_run_plan"]["command"]
    assert "--max-pages 3" in compact_plan["connected_run_plan"]["command"]
    assert "--max-sources 4" in compact_plan["connected_run_plan"]["command"]
    assert any("calibration connected-run --mode live --allow-network" in command for command in readiness["next_commands"])
    assert any("--link-pattern '*/lessons/*'" in command for command in readiness["next_commands"] if "calibration connected-run" in command)
    assert any("--max-lessons 7" in command for command in readiness["next_commands"] if "calibration connected-run" in command)
    assert any("--max-pages 3" in command for command in readiness["next_commands"] if "calibration connected-run" in command)
    assert any("--max-sources 4" in command for command in readiness["next_commands"] if "calibration connected-run" in command)


def test_mcp_jsonrpc_initialize_list_and_call(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_graph(storage, run_id="starter-fixture")
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    initialize = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
    })
    unsupported_initialize = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "initialize",
        "params": {"protocolVersion": "1900-01-01", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
    })
    assert initialize["result"]["protocolVersion"] == "2025-11-25"
    assert unsupported_initialize["result"]["protocolVersion"] == "2025-11-25"
    assert initialize["result"]["serverInfo"]["name"] == "aoa-course-connector-mcp"
    assert initialize["result"]["capabilities"]["tools"]["listChanged"] is False
    assert handle_jsonrpc_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None

    listed = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    readiness_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "connector_readiness")
    search_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "search")
    preflight_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "live_preflight")
    connected_plan_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "connected_source_plan")
    profile_run_plan_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "connection_profile_run_plan")
    semantic_provider_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "semantic_provider_preflight")
    browser_snapshot_audit_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "browser_snapshot_audit")
    connected_run_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "connected_run")
    connected_run_status_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "connected_run_status")
    connected_run_query_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "connected_run_query")
    connected_run_query_matrix_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "connected_run_query_matrix")
    source_answer_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "source_answer")
    sources_answer_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "sources_answer")
    answer_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "answer")
    evidence_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "evidence_report")
    lesson_context_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "lesson_context")
    refresh_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "refresh_plan")
    assert "runs" in readiness_tool["inputSchema"]["properties"]
    assert "link_pattern" in readiness_tool["inputSchema"]["properties"]
    assert readiness_tool["inputSchema"]["properties"]["live_scope"]["enum"] == ["bounded", "full-course"]
    assert "include_step_sources" in readiness_tool["inputSchema"]["properties"]
    assert "max_step_sources" in readiness_tool["inputSchema"]["properties"]
    assert "step_source_timeout" in readiness_tool["inputSchema"]["properties"]
    assert "max_lessons" in readiness_tool["inputSchema"]["properties"]
    assert "max_pages" in readiness_tool["inputSchema"]["properties"]
    assert "max_sources" in readiness_tool["inputSchema"]["properties"]
    assert search_tool["inputSchema"]["required"] == ["query"]
    assert answer_tool["inputSchema"]["required"] == ["query"]
    assert answer_tool["inputSchema"]["properties"]["mode"]["enum"] == ["keyword", "semantic", "hybrid"]
    assert "platforms" in preflight_tool["inputSchema"]["properties"]
    assert "calibration_run" in connected_plan_tool["inputSchema"]["properties"]
    assert connected_plan_tool["inputSchema"]["properties"]["live_scope"]["enum"] == ["bounded", "full-course"]
    assert "include_step_sources" in connected_plan_tool["inputSchema"]["properties"]
    assert "max_step_sources" in connected_plan_tool["inputSchema"]["properties"]
    assert "step_source_timeout" in connected_plan_tool["inputSchema"]["properties"]
    assert "link_pattern" in connected_plan_tool["inputSchema"]["properties"]
    assert profile_run_plan_tool["inputSchema"]["required"] == ["profile_path"]
    assert profile_run_plan_tool["inputSchema"]["properties"]["platform"]["enum"] == ["getcourse", "skillspace", "stepik"]
    assert "embedding_endpoint" in semantic_provider_tool["inputSchema"]["properties"]
    assert "embedding_token_env" in semantic_provider_tool["inputSchema"]["properties"]
    assert browser_snapshot_audit_tool["inputSchema"]["required"] == ["snapshot_path"]
    assert browser_snapshot_audit_tool["inputSchema"]["properties"]["platform"]["enum"] == ["getcourse", "skillspace"]
    assert connected_run_tool["inputSchema"]["required"] == []
    assert connected_run_tool["inputSchema"]["properties"]["mode"]["enum"] == ["fixture", "live"]
    assert "allow_network" in connected_run_tool["inputSchema"]["properties"]
    assert "max_step_sources" in connected_run_tool["inputSchema"]["properties"]
    assert "step_source_timeout" in connected_run_tool["inputSchema"]["properties"]
    assert connected_run_status_tool["inputSchema"]["required"] == []
    assert connected_run_query_tool["inputSchema"]["required"] == []
    assert connected_run_query_tool["inputSchema"]["properties"]["mode"]["enum"] == ["keyword", "semantic", "hybrid"]
    assert connected_run_query_tool["inputSchema"]["properties"]["kinds"]["items"]["enum"] == ["smoke", "sync"]
    assert connected_run_query_matrix_tool["inputSchema"]["required"] == ["queries"]
    assert connected_run_query_matrix_tool["inputSchema"]["properties"]["mode"]["enum"] == ["keyword", "semantic", "hybrid"]
    assert connected_run_query_matrix_tool["inputSchema"]["properties"]["kinds"]["items"]["enum"] == ["smoke", "sync"]
    assert source_answer_tool["inputSchema"]["required"] == ["query"]
    assert source_answer_tool["inputSchema"]["properties"]["mode"]["enum"] == ["keyword", "semantic", "hybrid"]
    assert source_answer_tool["inputSchema"]["properties"]["kinds"]["items"]["enum"] == ["smoke", "sync"]
    assert "include_source_refs" in source_answer_tool["inputSchema"]["properties"]
    assert sources_answer_tool["inputSchema"]["required"] == ["query"]
    assert sources_answer_tool["inputSchema"]["properties"]["mode"]["enum"] == ["keyword", "semantic", "hybrid"]
    assert sources_answer_tool["inputSchema"]["properties"]["kinds"]["items"]["enum"] == ["smoke", "sync"]
    assert "source_ids" in sources_answer_tool["inputSchema"]["properties"]
    assert "source_limit" in sources_answer_tool["inputSchema"]["properties"]
    assert lesson_context_tool["inputSchema"]["required"] == ["query"]
    assert "graph_limit" in lesson_context_tool["inputSchema"]["properties"]
    assert evidence_tool["inputSchema"]["required"] == ["query"]
    assert refresh_tool["inputSchema"]["required"] == ["query"]

    called = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "search", "arguments": {"query": "rollback", "run": "starter-fixture"}},
    })
    result = called["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["tool"] == "search"
    assert result["structuredContent"]["results"]

    answer = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 30,
        "method": "tools/call",
        "params": {"name": "answer", "arguments": {"query": "rollback", "run": "starter-fixture", "mode": "keyword"}},
    })
    assert answer["result"]["structuredContent"]["tool"] == "answer"
    assert answer["result"]["structuredContent"]["answer_packet"]["schema"] == "aoa_course_answer_packet_v1"
    assert answer["result"]["structuredContent"]["answer_packet"]["quality"]["ready"] is True

    evidence = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 31,
        "method": "tools/call",
        "params": {"name": "evidence_report", "arguments": {"query": "rollback", "run": "starter-fixture"}},
    })
    assert evidence["result"]["structuredContent"]["tool"] == "evidence_report"
    assert evidence["result"]["structuredContent"]["evidence_chain"]
    assert evidence["result"]["structuredContent"]["quality"]["ready"] is True

    refresh = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 32,
        "method": "tools/call",
        "params": {"name": "refresh_plan", "arguments": {"query": "rollback", "run": "starter-fixture", "mode": "keyword"}},
    })
    assert refresh["result"]["structuredContent"]["tool"] == "refresh_plan"
    assert refresh["result"]["structuredContent"]["refresh"]["network_touched"] is False
    assert any(
        "lesson-context" in command
        for command in refresh["result"]["structuredContent"]["refresh"]["planned_commands"]["local_query_commands"]
    )

    preflight = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "live_preflight", "arguments": {"platforms": ["stepik"]}},
    })
    preflight_result = preflight["result"]
    assert preflight_result["isError"] is False
    assert preflight_result["structuredContent"]["tool"] == "live_preflight"
    assert preflight_result["structuredContent"]["preflight"]["network_touched"] is False
    semantic_preflight = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 40,
        "method": "tools/call",
        "params": {"name": "semantic_provider_preflight", "arguments": {"run": "starter-fixture"}},
    })
    assert semantic_preflight["result"]["structuredContent"]["tool"] == "semantic_provider_preflight"
    assert semantic_preflight["result"]["structuredContent"]["preflight"]["network_touched"] is False
    snapshot_audit = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 401,
        "method": "tools/call",
        "params": {
            "name": "browser_snapshot_audit",
            "arguments": {
                "snapshot_path": "connector/fixtures/browser/getcourse_starter_snapshot.json",
                "platform": "getcourse",
            },
        },
    })
    snapshot_content = snapshot_audit["result"]["structuredContent"]
    assert snapshot_content["tool"] == "browser_snapshot_audit"
    assert snapshot_content["audit"]["schema"] == "aoa_course_browser_snapshot_audit_v1"
    assert snapshot_content["audit"]["network_touched"] is False
    assert snapshot_content["audit"]["privacy"]["raw_html_included"] is False
    assert "rollback index" not in json.dumps(snapshot_content)
    upsert_source(storage.data, "stepik", "67", "Stepik Public", access_mode="public_api")

    connected_plan = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 41,
        "method": "tools/call",
        "params": {
            "name": "connected_source_plan",
            "arguments": {
                "platforms": ["stepik"],
                "live_scope": "full-course",
                "include_step_sources": True,
                "max_step_sources": "all",
                "step_source_timeout": 0.5,
            },
        },
    })
    assert connected_plan["result"]["structuredContent"]["tool"] == "connected_source_plan"
    assert connected_plan["result"]["structuredContent"]["plan"]["network_touched"] is False
    assert connected_plan["result"]["structuredContent"]["plan"]["live_scope"] == "full-course"
    assert connected_plan["result"]["structuredContent"]["plan"]["include_step_sources"] is True
    assert connected_plan["result"]["structuredContent"]["plan"]["max_step_sources"] == "all"
    assert connected_plan["result"]["structuredContent"]["plan"]["step_source_timeout"] == 0.5
    connected_run = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 411,
        "method": "tools/call",
        "params": {
            "name": "connected_run",
            "arguments": {"run": "jsonrpc-connected-fixture", "mode": "fixture", "platforms": ["stepik"]},
        },
    })
    assert connected_run["result"]["structuredContent"]["tool"] == "connected_run"
    assert connected_run["result"]["structuredContent"]["connected_run"]["status"] == "ok"
    assert connected_run["result"]["structuredContent"]["connected_run"]["network_touched"] is False
    connected_query = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 412,
        "method": "tools/call",
        "params": {
            "name": "connected_run_query",
            "arguments": {"run": "jsonrpc-connected-fixture", "kinds": ["smoke"]},
        },
    })
    assert connected_query["result"]["structuredContent"]["tool"] == "connected_run_query"
    assert connected_query["result"]["structuredContent"]["query_packet"]["status"] == "ok"
    assert connected_query["result"]["structuredContent"]["query_packet"]["quality"]["ready"] is True
    assert connected_query["result"]["structuredContent"]["query_packet"]["response_count"] == 1
    connected_matrix = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 413,
        "method": "tools/call",
        "params": {
            "name": "connected_run_query_matrix",
            "arguments": {
                "run": "jsonrpc-connected-fixture",
                "kinds": ["smoke"],
                "queries": ["Stepik public API evidence", "canonical course objects"],
            },
        },
    })
    assert connected_matrix["result"]["structuredContent"]["tool"] == "connected_run_query_matrix"
    assert connected_matrix["result"]["structuredContent"]["query_matrix"]["status"] == "ok"
    assert connected_matrix["result"]["structuredContent"]["query_matrix"]["quality"]["ready"] is True
    assert connected_matrix["result"]["structuredContent"]["query_matrix"]["query_count"] == 2
    connected_status = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 42,
        "method": "tools/call",
        "params": {"name": "connected_run_status", "arguments": {"run": "missing-connected-run"}},
    })
    assert connected_status["result"]["structuredContent"]["tool"] == "connected_run_status"
    assert connected_status["result"]["structuredContent"]["connected_run"]["status"] == "missing"
    readiness = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 43,
        "method": "tools/call",
        "params": {
            "name": "connector_readiness",
            "arguments": {
                "runs": ["starter-fixture"],
                "platforms": ["stepik"],
                "live_scope": "full-course",
                "include_step_sources": True,
                "max_step_sources": "all",
                "step_source_timeout": 0.5,
                "max_lessons": 9,
                "max_pages": 4,
                "max_sources": 2,
            },
        },
    })
    readiness_content = readiness["result"]["structuredContent"]
    assert readiness_content["tool"] == "connector_readiness"
    assert readiness_content["schema"] == "aoa_course_connector_readiness_v1"
    assert readiness_content["runs"][0]["readiness"]["agent_query_ready"] is True
    assert readiness_content["mcp"]["ready"] is True
    compact_plan = readiness_content["connected_source_plan"]
    assert compact_plan["live_scope"] == "full-course"
    assert compact_plan["include_step_sources"] is True
    assert compact_plan["max_step_sources"] == "all"
    assert compact_plan["step_source_timeout"] == 0.5
    assert compact_plan["max_lessons"] == 9
    assert compact_plan["max_pages"] == 4
    assert compact_plan["max_sources"] == 2
    assert compact_plan["connected_run_plan"]["ready"] is True
    assert "--live-scope full-course" in compact_plan["connected_run_plan"]["command"]
    assert "--include-step-sources" in compact_plan["connected_run_plan"]["command"]
    assert "--max-step-sources all" in compact_plan["connected_run_plan"]["command"]
    assert "--step-source-timeout 0.5" in compact_plan["connected_run_plan"]["command"]
    assert "--max-lessons 9" in compact_plan["connected_run_plan"]["command"]
    assert "--max-pages 4" in compact_plan["connected_run_plan"]["command"]
    assert "--max-sources 2" in compact_plan["connected_run_plan"]["command"]
    assert compact_plan["connected_run_plan"]["mcp_tool_call"]["arguments"]["live_scope"] == "full-course"
    assert compact_plan["connected_run_plan"]["mcp_tool_call"]["arguments"]["include_step_sources"] is True
    assert compact_plan["connected_run_plan"]["mcp_tool_call"]["arguments"]["max_step_sources"] == "all"
    assert compact_plan["connected_run_plan"]["mcp_tool_call"]["arguments"]["step_source_timeout"] == 0.5
    assert compact_plan["connected_run_plan"]["mcp_tool_call"]["arguments"]["max_lessons"] == 9
