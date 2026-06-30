from __future__ import annotations

import json
import os
from pathlib import Path

from aoa_course_connector.auth import browser_state_plan, default_browser_state_path, inspect_browser_state
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index
from aoa_course_connector.ingest import materialize_fixture
from aoa_course_connector.mcp.server import call_tool, handle_jsonrpc_message, tools_manifest
from aoa_course_connector.sources import load_registry, upsert_source
from aoa_course_connector.sync.checkpoints import make_checkpoint, upsert_checkpoint


def test_source_registry_and_browser_plan(tmp_path: Path) -> None:
    source, path, state = upsert_source(tmp_path / "data", "getcourse", "https://school.example", "School")
    assert state == "added"
    assert source["access_mode"] == "browser_session"
    assert path.exists()
    assert load_registry(tmp_path / "data")["sources"]
    plan = browser_state_plan(tmp_path / "auth", "getcourse", "https://school.example")
    assert plan["state_file"]
    assert plan["state_file"] == str(default_browser_state_path(tmp_path / "auth", "getcourse", "https://school.example"))
    assert "capture-browser-state" in plan["capture_command"]
    assert "inspect-browser-state" in plan["inspect_command"]
    assert plan["git_safe"] is False


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
    assert any(tool["name"] == "search" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "sync_status" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "live_preflight" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "connected_source_plan" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "graph_neighbors" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "freshness_report" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "evidence_report" for tool in tools_manifest()["tools"])
    result = call_tool("search", {"query": "rollback", "run": "starter-fixture"})
    assert result["results"]
    graph = call_tool("graph_neighbors", {"node_id": "lesson:starter:unlock-risk", "run": "starter-fixture"})
    assert graph["graph"]["node"]["node_id"] == "lesson:starter:unlock-risk"
    assert graph["graph"]["neighbors"]
    freshness = call_tool("freshness_report", {"run": "starter-fixture"})
    assert freshness["freshness"]["states"]
    evidence = call_tool("evidence_report", {"query": "rollback", "run": "starter-fixture"})
    assert evidence["evidence_chain"]
    assert evidence["freshness_report"]["has_source_timestamps"] is True
    assert evidence["refresh_report"]["local_rebuild_commands"]
    assert evidence["result_refs"][0]["evidence_id"]
    assert evidence["result_refs"][0]["refresh_hint"]["schema"] == "aoa_course_refresh_hint_v1"
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


def test_mcp_live_preflight_reports_readiness_without_secret_values(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
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
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    result = call_tool(
        "live_preflight",
        {"platforms": ["getcourse"], "state_file": str(state_file), "expect_origin": "school.example"},
    )

    assert result["tool"] == "live_preflight"
    assert result["preflight"]["ready"] is True
    assert result["preflight"]["network_touched"] is False
    rendered = json.dumps(result)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered

    plan = call_tool(
        "connected_source_plan",
        {"platforms": ["getcourse"], "state_file": str(state_file), "expect_origin": "school.example"},
    )

    assert plan["tool"] == "connected_source_plan"
    assert plan["plan"]["ready"] is True
    assert any("smoke browser-live" in command for command in plan["plan"]["next_commands"])
    handoff = plan["plan"]["browser_auth_handoffs"][0]
    assert handoff["ready"] is True
    assert handoff["source_hosts"] == ["school.example"]
    assert "capture-browser-state getcourse account" in handoff["commands"]["capture"]
    rendered_plan = json.dumps(plan)
    assert "SUPER_SECRET_COOKIE" not in rendered_plan
    assert "SUPER_SECRET_TOKEN" not in rendered_plan


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
    search_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "search")
    preflight_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "live_preflight")
    connected_plan_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "connected_source_plan")
    evidence_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "evidence_report")
    assert search_tool["inputSchema"]["required"] == ["query"]
    assert "platforms" in preflight_tool["inputSchema"]["properties"]
    assert "calibration_run" in connected_plan_tool["inputSchema"]["properties"]
    assert connected_plan_tool["inputSchema"]["properties"]["live_scope"]["enum"] == ["bounded", "full-course"]
    assert "include_step_sources" in connected_plan_tool["inputSchema"]["properties"]
    assert evidence_tool["inputSchema"]["required"] == ["query"]

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

    evidence = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 31,
        "method": "tools/call",
        "params": {"name": "evidence_report", "arguments": {"query": "rollback", "run": "starter-fixture"}},
    })
    assert evidence["result"]["structuredContent"]["tool"] == "evidence_report"
    assert evidence["result"]["structuredContent"]["evidence_chain"]

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

    connected_plan = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 41,
        "method": "tools/call",
        "params": {"name": "connected_source_plan", "arguments": {"platforms": ["stepik"], "live_scope": "full-course", "include_step_sources": True}},
    })
    assert connected_plan["result"]["structuredContent"]["tool"] == "connected_source_plan"
    assert connected_plan["result"]["structuredContent"]["plan"]["network_touched"] is False
    assert connected_plan["result"]["structuredContent"]["plan"]["live_scope"] == "full-course"
    assert connected_plan["result"]["structuredContent"]["plan"]["include_step_sources"] is True
