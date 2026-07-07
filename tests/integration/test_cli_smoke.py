from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def cli_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["AOA_COURSE_DATA_ROOT"] = str(tmp_path / "data")
    env["AOA_COURSE_CACHE_ROOT"] = str(tmp_path / "cache")
    env["AOA_COURSE_AUTH_ROOT"] = str(tmp_path / "auth")
    env["AOA_COURSE_ARTIFACT_ROOT"] = str(tmp_path / "artifacts")
    return env


def run_cli(tmp_path: Path, *args: str) -> dict[str, object]:
    env = cli_env(tmp_path)
    result = subprocess.run([sys.executable, "-m", "aoa_course_connector.cli", *args], check=False, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_cli_rejects_path_like_run_id_before_writing_runtime_artifacts(tmp_path: Path) -> None:
    escape = tmp_path / "absolute-run-escape"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "aoa_course_connector.cli",
            "materialize",
            "fixture",
            "--run",
            str(escape),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=cli_env(tmp_path),
    )

    assert result.returncode != 0
    assert "portable runtime id" in result.stderr + result.stdout
    assert not escape.exists()


def test_cli_starter_flow(tmp_path: Path) -> None:
    assert run_cli(tmp_path, "doctor")["status"] == "ok"
    adapters = run_cli(tmp_path, "adapters", "list")
    platforms = {str(adapter["platform"]) for adapter in adapters["adapters"]}
    assert {
        "getcourse",
        "skillspace",
        "stepik",
        "moodle",
        "canvas",
        "coursera",
        "teachable",
        "thinkific",
        "kajabi",
    } <= platforms
    run_cli(tmp_path, "init")
    run_cli(tmp_path, "materialize", "fixture", "--run", "starter-fixture")
    run_cli(tmp_path, "build-index", "--run", "starter-fixture")
    run_cli(tmp_path, "build-graph", "--run", "starter-fixture")
    answer = run_cli(tmp_path, "answer", "bootloader unlock rollback", "--run", "starter-fixture")
    assert answer["result_count"] >= 1
    assert answer["evidence_chain"]
    assert answer["quality"]["ready"] is True
    assert answer["quality"]["top_result"]["doc_id"] == answer["results"][0]["doc_id"]
    assert answer["evidence_chain"][0]["snippet"]
    lesson_context = run_cli(tmp_path, "lesson-context", "bootloader rollback", "--run", "starter-fixture", "--graph-limit", "6")
    assert lesson_context["schema"] == "aoa_course_lesson_context_packet_v1"
    assert lesson_context["answer_packet"]["evidence_chain"]
    assert lesson_context["answer_packet"]["quality"]["ready"] is True
    assert lesson_context["graph_context"]["status"] == "ready"
    assert lesson_context["graph_context"]["contexts"][0]["graph"]["neighbors"]
    evidence_inspect = run_cli(tmp_path, "evidence", "inspect", "rollback", "--run", "starter-fixture")
    assert evidence_inspect["evidence_chain"]
    assert evidence_inspect["evidence_chain"][0]["snippet"]
    assert evidence_inspect["freshness_report"]["has_source_timestamps"] is True
    browser_snapshot_audit = run_cli(
        tmp_path,
        "inspect",
        "browser-snapshot",
        "connector/fixtures/browser/getcourse_starter_snapshot.json",
        "--platform",
        "getcourse",
        "--require-ready",
    )
    assert browser_snapshot_audit["schema"] == "aoa_course_browser_snapshot_audit_v1"
    assert browser_snapshot_audit["readiness"]["ready_for_materialize"] is True
    assert browser_snapshot_audit["privacy"]["raw_html_included"] is False
    mcp_snapshot_audit = run_cli(
        tmp_path,
        "mcp",
        "call",
        "browser_snapshot_audit",
        '{"snapshot_path":"connector/fixtures/browser/getcourse_starter_snapshot.json","platform":"getcourse"}',
    )
    assert mcp_snapshot_audit["result"]["audit"]["schema"] == "aoa_course_browser_snapshot_audit_v1"
    assert mcp_snapshot_audit["result"]["audit"]["network_touched"] is False
    tools = run_cli(tmp_path, "mcp", "tools")
    assert tools["server"] == "aoa-course-connector-mcp"
    assert any(tool["name"] == "connector_readiness" for tool in tools["tools"])
    readiness = run_cli(tmp_path, "readiness", "--run", "starter-fixture", "--platform", "stepik")
    assert readiness["schema"] == "aoa_course_connector_readiness_v1"
    assert readiness["network_touched"] is False
    assert readiness["operational_ready"] is True
    assert readiness["connected_live_ready"] is False
    assert readiness["connected_live_ready"] == readiness["lanes"]["connected_live_ready"]
    assert readiness["lanes"]["agent_query_ready"] is True
    assert readiness["mcp"]["ready"] is True
    mcp_readiness = run_cli(tmp_path, "mcp", "call", "connector_readiness", '{"runs":["starter-fixture"],"platforms":["stepik"]}')
    assert mcp_readiness["result"]["schema"] == "aoa_course_connector_readiness_v1"
    assert mcp_readiness["result"]["runs"][0]["readiness"]["agent_query_ready"] is True
    ingest = run_cli(tmp_path, "mcp", "call", "ingest_status", '{"run":"starter-fixture"}')
    assert ingest["result"]["status"] == "ready"
    assert ingest["result"]["readiness"]["agent_query_ready"] is True
    assert ingest["result"]["normalized"]["counts"]["lessons"] >= 1
    graph = run_cli(tmp_path, "mcp", "call", "graph_neighbors", '{"node_id":"lesson:starter:unlock-risk","run":"starter-fixture"}')
    assert graph["result"]["graph"]["node"]["node_id"] == "lesson:starter:unlock-risk"
    freshness = run_cli(tmp_path, "mcp", "call", "freshness_report", '{"run":"starter-fixture"}')
    assert freshness["result"]["freshness"]["states"]
    mcp_answer = run_cli(tmp_path, "mcp", "call", "answer", '{"query":"bootloader rollback","run":"starter-fixture","mode":"keyword"}')
    assert mcp_answer["result"]["answer_packet"]["schema"] == "aoa_course_answer_packet_v1"
    assert mcp_answer["result"]["answer_packet"]["quality"]["ready"] is True
    assert mcp_answer["result"]["answer_packet"]["evidence_chain"]
    evidence = run_cli(tmp_path, "mcp", "call", "evidence_report", '{"query":"rollback","run":"starter-fixture"}')
    assert evidence["result"]["evidence_chain"]
    assert evidence["result"]["quality"]["ready"] is True
    assert evidence["result"]["quality"]["top_result"]["doc_id"] == evidence["result"]["result_refs"][0]["doc_id"]
    assert evidence["result"]["result_refs"][0]["snippet"]
    refresh = run_cli(tmp_path, "mcp", "call", "refresh_plan", '{"query":"rollback","run":"starter-fixture","mode":"keyword"}')
    assert refresh["result"]["refresh"]["schema"] == "aoa_course_refresh_cycle_v1"
    assert refresh["result"]["refresh"]["network_touched"] is False
    assert any("lesson-context" in command for command in refresh["result"]["refresh"]["planned_commands"]["local_query_commands"])
    preflight = run_cli(tmp_path, "mcp", "call", "live_preflight", '{"platforms":["stepik"]}')
    assert preflight["result"]["preflight"]["network_touched"] is False
    plan = run_cli(tmp_path, "mcp", "call", "connected_source_plan", '{"platforms":["stepik"]}')
    assert plan["result"]["plan"]["network_touched"] is False


def test_cli_fixture_bootstrap_prepares_fresh_agent_route(tmp_path: Path) -> None:
    initial = run_cli(tmp_path, "readiness", "--run", "starter-fixture", "--platform", "stepik")
    assert initial["operational_ready"] is False
    assert any(command.startswith("aoa-course bootstrap fixture") for command in initial["next_commands"])

    receipt = run_cli(
        tmp_path,
        "bootstrap",
        "fixture",
        "--run",
        "starter-fixture",
        "--connected-run",
        "connected-calibration",
    )

    assert receipt["schema"] == "aoa_course_fixture_bootstrap_receipt_v1"
    assert receipt["status"] == "ok"
    assert receipt["network_touched"] is False
    assert receipt["materialize"]["status"] == "ok"
    assert receipt["connected_receipt"]["status"] == "ok"
    assert receipt["connected_receipt"]["platforms"] == ["getcourse", "skillspace", "stepik"]
    assert receipt["connected_receipt"]["network_touched"] is False
    assert receipt["connected_receipt"]["stage_count"] == 9
    assert Path(str(receipt["artifacts"]["keyword_index_path"])).is_file()
    assert Path(str(receipt["artifacts"]["semantic_index_path"])).is_file()
    assert Path(str(receipt["artifacts"]["graph_path"])).is_file()
    assert receipt["readiness"]["operational_ready"] is True
    assert receipt["readiness"]["connected_live_ready"] is False
    assert receipt["readiness"]["connected_live_ready"] == receipt["readiness"]["lanes"]["connected_live_ready"]
    assert receipt["readiness"]["lanes"]["agent_query_ready"] is True
    assert receipt["readiness"]["lanes"]["connected_run_receipt_ready"] is True
    assert receipt["readiness"]["sources"]["platform_counts"]["getcourse"] >= 1
    assert receipt["readiness"]["sources"]["platform_counts"]["skillspace"] >= 1
    assert receipt["readiness"]["sources"]["platform_counts"]["stepik"] >= 1

    readiness = run_cli(
        tmp_path,
        "mcp",
        "call",
        "connector_readiness",
        '{"runs":["starter-fixture"],"platforms":["stepik"],"connected_run":"connected-calibration"}',
    )
    assert readiness["result"]["operational_ready"] is True
    assert readiness["result"]["connected_run"]["status"] == "ok"
    assert readiness["result"]["lanes"]["connected_run_receipt_ready"] is True

    answer = run_cli(tmp_path, "answer", "bootloader rollback", "--run", "starter-fixture", "--mode", "hybrid")
    assert answer["result_count"] >= 1
    connected_status = run_cli(tmp_path, "calibration", "status", "--run", "connected-calibration")
    assert connected_status["status"] == "ok"


def test_cli_connection_profile_route(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AOA_COURSE_TEST_EMBEDDING_TOKEN", "SUPER_SECRET_EMBEDDING_TOKEN")
    runbook_path = tmp_path / "artifacts" / "connections" / "operator-live.runbook.md"
    receipt = run_cli(
        tmp_path,
        "connect",
        "profile",
        "--name",
        "operator-live",
        "--getcourse-url",
        "https://school.operator.edu/teach/control/stream",
        "--skillspace-url",
        "https://academy.example/course/demo",
        "--stepik-course-id",
        "67",
        "--run",
        "connected-live-calibration",
        "--query",
        "course-specific question",
        "--live-scope",
        "full-course",
        "--include-step-sources",
        "--semantic-provider",
        "http_json_v1",
        "--embedding-endpoint",
        "https://embed.example/v1",
        "--embedding-model",
        "course-embedding",
        "--embedding-token-env",
        "AOA_COURSE_TEST_EMBEDDING_TOKEN",
        "--write-runbook",
        str(runbook_path),
    )

    profile_path = Path(str(receipt["profile_path"]))
    assert receipt["schema"] == "aoa_course_connection_profile_receipt_v1"
    assert profile_path.is_file()
    assert receipt["inspection"]["runbook"]["written"] is True
    assert runbook_path.is_file()
    assert "Course Connection Profile Runbook" in runbook_path.read_text(encoding="utf-8")
    assert receipt["inspection"]["live_readiness"]["schema"] == "aoa_course_connection_profile_readiness_v1"
    assert receipt["inspection"]["live_readiness"]["ready_for_connected_run"] is False
    assert receipt["inspection"]["source_registry"]["registered_profile_source_count"] == 0
    assert "SUPER_SECRET_EMBEDDING_TOKEN" not in json.dumps(receipt)

    inspection = run_cli(tmp_path, "connect", "inspect", str(profile_path))
    assert inspection["schema"] == "aoa_course_connection_profile_inspection_v1"
    assert any("sources add" in command for command in inspection["next_commands"])
    status = run_cli(tmp_path, "connect", "status", str(profile_path))
    assert status["schema"] == "aoa_course_connection_profile_status_v1"
    assert status["live_readiness"]["ready_for_connected_run"] is False

    apply_runbook = tmp_path / "artifacts" / "connections" / "operator-live-applied.runbook.md"
    applied = run_cli(tmp_path, "connect", "apply", str(profile_path), "--write-runbook", str(apply_runbook))
    assert applied["schema"] == "aoa_course_connection_profile_apply_v1"
    assert len(applied["applied"]) == 3
    assert applied["inspection"]["source_registry"]["registered_profile_source_count"] == 3
    assert applied["inspection"]["runbook"]["written"] is True
    assert apply_runbook.is_file()

    sources = run_cli(tmp_path, "sources", "list")
    assert len(sources["registry"]["sources"]) == 3
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    getcourse_source = next(source for source in profile["sources"] if source["platform"] == "getcourse")
    state_file = Path(str(getcourse_source["state_file"]))
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )
    run_plan = run_cli(tmp_path, "connect", "run", str(profile_path), "--platform", "getcourse")
    assert run_plan["schema"] == "aoa_course_connection_profile_run_receipt_v1"
    assert run_plan["status"] == "planned"
    assert run_plan["network_touched"] is False
    assert run_plan["executed"] is False
    assert run_plan["run_plan"]["ready"] is True
    assert run_plan["run_plan"]["platform"] == "getcourse"
    assert "--allow-network" in run_plan["run_plan"]["command"]
    assert "SUPER_SECRET_COOKIE" not in json.dumps(run_plan)
    assert "SUPER_SECRET_TOKEN" not in json.dumps(run_plan)
    mcp = run_cli(tmp_path, "mcp", "call", "connection_profile_inspect", json.dumps({"profile_path": str(profile_path)}))
    assert mcp["result"]["inspection"]["schema"] == "aoa_course_connection_profile_inspection_v1"
    assert mcp["result"]["inspection"]["network_touched"] is False
    mcp_status = run_cli(tmp_path, "mcp", "call", "connection_profile_status", json.dumps({"profile_path": str(profile_path)}))
    assert mcp_status["result"]["status"]["schema"] == "aoa_course_connection_profile_status_v1"
    assert mcp_status["result"]["status"]["network_touched"] is False
    mcp_run_plan = run_cli(tmp_path, "mcp", "call", "connection_profile_run_plan", json.dumps({"profile_path": str(profile_path), "platform": "getcourse"}))
    assert mcp_run_plan["result"]["run_plan"]["schema"] == "aoa_course_connection_profile_run_plan_v1"
    assert mcp_run_plan["result"]["run_plan"]["ready"] is True
    assert mcp_run_plan["result"]["run_plan"]["network_touched"] is False
    assert mcp_run_plan["result"]["run_plan"]["platform"] == "getcourse"
    assert "--allow-network" in mcp_run_plan["result"]["run_plan"]["command"]
    assert "SUPER_SECRET_COOKIE" not in json.dumps(mcp_run_plan)
    assert "SUPER_SECRET_TOKEN" not in json.dumps(mcp_run_plan)


def test_cli_readiness_surfaces_partial_connected_run_repair_lanes(tmp_path: Path) -> None:
    run_cli(
        tmp_path,
        "bootstrap",
        "fixture",
        "--run",
        "starter-fixture",
        "--connected-run",
        "connected-calibration",
        "--platform",
        "stepik",
    )
    partial = subprocess.run(
        [
            sys.executable,
            "-m",
            "aoa_course_connector.cli",
            "calibration",
            "connected-run",
            "--mode",
            "live",
            "--platform",
            "stepik",
            "--run",
            "partial-connected-run",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=cli_env(tmp_path),
    )
    assert partial.returncode == 1
    partial_receipt = json.loads(partial.stdout)
    assert partial_receipt["status"] == "partial"
    assert partial_receipt["repair_lanes"][0]["lane"] == "network_gate"

    readiness = run_cli(
        tmp_path,
        "readiness",
        "--run",
        "starter-fixture",
        "--platform",
        "stepik",
        "--connected-run",
        "partial-connected-run",
    )

    assert readiness["connected_run"]["status"] == "partial"
    assert any(command.startswith("aoa-course preflight connected-plan --platform stepik") for command in readiness["next_commands"])
    assert any("aoa-course calibration connected-run --mode live --allow-network --run partial-connected-run" in command for command in readiness["next_commands"])
    assert not any(command == "aoa-course bootstrap fixture --connected-run partial-connected-run" for command in readiness["next_commands"])


def test_cli_http_json_semantic_provider_flow(tmp_path: Path, monkeypatch) -> None:
    server = _EmbeddingServer()
    monkeypatch.setenv("AOA_COURSE_TEST_EMBEDDING_TOKEN", "SUPER_SECRET_EMBEDDING_TOKEN")
    try:
        run_cli(tmp_path, "materialize", "fixture", "--run", "starter-fixture")
        receipt = run_cli(
            tmp_path,
            "build-semantic-index",
            "--run",
            "starter-fixture",
            "--provider",
            "http_json_v1",
            "--embedding-endpoint",
            server.url,
            "--embedding-model",
            "fixture-embedding",
            "--embedding-token-env",
            "AOA_COURSE_TEST_EMBEDDING_TOKEN",
        )
        assert receipt["provider"] == "http_json_v1"
        assert receipt["provider_config"]["token_env"] == "AOA_COURSE_TEST_EMBEDDING_TOKEN"
        assert "SUPER_SECRET_EMBEDDING_TOKEN" not in json.dumps(receipt)

        result = run_cli(tmp_path, "query", "bootloader rollback", "--run", "starter-fixture", "--mode", "semantic")
        assert result["results"]
        assert result["results"][0]["semantic_provider"] == "http_json_v1"
        assert all(request["authorization"] == "Bearer SUPER_SECRET_EMBEDDING_TOKEN" for request in server.requests)
    finally:
        server.close()


def test_cli_semantic_provider_preflight_redacts_secret_and_feeds_readiness(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AOA_COURSE_TEST_EMBEDDING_TOKEN", "SUPER_SECRET_EMBEDDING_TOKEN")
    run_cli(tmp_path, "materialize", "fixture", "--run", "starter-fixture")
    preflight = run_cli(
        tmp_path,
        "preflight",
        "semantic-provider",
        "--run",
        "starter-fixture",
        "--provider",
        "http_json_v1",
        "--embedding-endpoint",
        "https://embed.example/v1",
        "--embedding-model",
        "course-embedding",
        "--embedding-token-env",
        "AOA_COURSE_TEST_EMBEDDING_TOKEN",
        "--require-ready",
    )
    assert preflight["schema"] == "aoa_course_semantic_provider_preflight_v1"
    assert preflight["ready"] is True
    assert preflight["network_touched"] is False
    assert preflight["provider_config"]["token_env_present"] is True
    assert "SUPER_SECRET_EMBEDDING_TOKEN" not in json.dumps(preflight)

    readiness = run_cli(
        tmp_path,
        "readiness",
        "--run",
        "starter-fixture",
        "--platform",
        "stepik",
        "--semantic-provider",
        "http_json_v1",
        "--embedding-endpoint",
        "https://embed.example/v1",
        "--embedding-model",
        "course-embedding",
        "--embedding-token-env",
        "AOA_COURSE_TEST_EMBEDDING_TOKEN",
    )
    assert readiness["lanes"]["semantic_provider_ready"] is True
    assert readiness["semantic_provider_preflight"][0]["provider"] == "http_json_v1"
    assert readiness["semantic_provider_preflight"][0]["secret_values_logged"] is False
    assert "SUPER_SECRET_EMBEDDING_TOKEN" not in json.dumps(readiness)


def test_mcp_stdio_jsonrpc_flow(tmp_path: Path) -> None:
    run_cli(tmp_path, "bootstrap", "fixture", "--run", "starter-fixture", "--connected-run", "connected-calibration")
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search", "arguments": {"query": "rollback", "run": "starter-fixture"}}},
        {"jsonrpc": "2.0", "id": 31, "method": "tools/call", "params": {"name": "answer", "arguments": {"query": "rollback", "run": "starter-fixture", "mode": "hybrid"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "evidence_report", "arguments": {"query": "rollback", "run": "starter-fixture"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "refresh_plan", "arguments": {"query": "rollback", "run": "starter-fixture", "mode": "keyword"}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "live_preflight", "arguments": {"platforms": ["stepik"]}}},
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "connected_source_plan", "arguments": {"platforms": ["stepik"]}}},
        {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "semantic_provider_preflight", "arguments": {"run": "starter-fixture"}}},
        {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "browser_snapshot_audit", "arguments": {"snapshot_path": "connector/fixtures/browser/getcourse_starter_snapshot.json", "platform": "getcourse"}}},
        {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "connected_run_status", "arguments": {"run": "missing-connected-run"}}},
        {"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "connector_readiness", "arguments": {"runs": ["starter-fixture"], "platforms": ["stepik"]}}},
    ]
    stdin = "\n".join(json.dumps(request) for request in requests) + "\n"

    result = subprocess.run(
        [sys.executable, "-m", "aoa_course_connector.mcp.server"],
        input=stdin,
        check=False,
        capture_output=True,
        text=True,
        env=cli_env(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert [response["id"] for response in responses] == [1, 2, 3, 31, 4, 5, 6, 7, 8, 9, 10, 11]
    assert responses[0]["result"]["serverInfo"]["name"] == "aoa-course-connector-mcp"
    assert any(tool["name"] == "search" for tool in responses[1]["result"]["tools"])
    assert any(tool["name"] == "answer" for tool in responses[1]["result"]["tools"])
    assert responses[2]["result"]["structuredContent"]["results"]
    assert responses[3]["result"]["structuredContent"]["answer_packet"]["schema"] == "aoa_course_answer_packet_v1"
    assert responses[3]["result"]["structuredContent"]["answer_packet"]["quality"]["ready"] is True
    assert responses[4]["result"]["structuredContent"]["evidence_chain"]
    assert responses[5]["result"]["structuredContent"]["refresh"]["network_touched"] is False
    assert responses[6]["result"]["structuredContent"]["preflight"]["network_touched"] is False
    assert responses[7]["result"]["structuredContent"]["plan"]["network_touched"] is False
    assert responses[8]["result"]["structuredContent"]["preflight"]["schema"] == "aoa_course_semantic_provider_preflight_v1"
    assert responses[8]["result"]["structuredContent"]["preflight"]["network_touched"] is False
    assert responses[9]["result"]["structuredContent"]["audit"]["schema"] == "aoa_course_browser_snapshot_audit_v1"
    assert responses[9]["result"]["structuredContent"]["audit"]["network_touched"] is False
    assert responses[9]["result"]["structuredContent"]["audit"]["privacy"]["raw_html_included"] is False
    assert responses[10]["result"]["structuredContent"]["connected_run"]["status"] == "missing"
    assert responses[11]["result"]["structuredContent"]["schema"] == "aoa_course_connector_readiness_v1"
    assert responses[11]["result"]["structuredContent"]["mcp"]["ready"] is True
    assert responses[11]["result"]["structuredContent"]["semantic_provider_preflight"][0]["network_touched"] is False


def test_cli_browser_auth_state_inspect(tmp_path: Path) -> None:
    plan = run_cli(tmp_path, "auth", "plan-browser-state", "getcourse", "https://school.example")
    assert "capture-browser-state" in plan["capture_command"]
    assert plan["expected_origin_contains"] == "school.example"
    assert "--state-file" in plan["capture_command"]
    assert "--expect-origin-contains school.example" in plan["capture_command"]
    assert "--expect-origin-contains school.example" in plan["inspect_command"]
    state_file = Path(str(plan["state_file"]))
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_PRIVATE_COOKIE", "domain": ".school.example", "path": "/"}],
            "origins": [{"origin": "https://school.example", "localStorage": [{"name": "token", "value": "SUPER_PRIVATE_TOKEN"}]}],
        }),
        encoding="utf-8",
    )

    status = run_cli(tmp_path, "auth", "inspect-browser-state", str(state_file), "--expect-origin-contains", "school.example")

    assert status["status"] == "ok"
    assert status["usable"] is True
    assert status["cookie_count"] == 1
    assert status["local_storage_entry_count"] == 1


def test_cli_live_preflight_uses_registered_source_and_redacted_auth_state(tmp_path: Path) -> None:
    run_cli(tmp_path, "sources", "add", "https://school.operator.edu/teach/control/stream", "--platform", "getcourse", "--title", "School")
    state_file = tmp_path / "auth" / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "secret", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "secret"}]}],
        }),
        encoding="utf-8",
    )

    report = run_cli(tmp_path, "preflight", "live", "--platform", "getcourse", "--expect-origin", "school.operator.edu")

    assert report["schema"] == "aoa_course_live_preflight_v1"
    assert report["ready"] is True
    assert report["network_touched"] is False
    assert report["source_registry"]["selected_source_count"] == 1
    rendered = json.dumps(report)
    assert "SUPER_PRIVATE_COOKIE" not in rendered
    assert "SUPER_PRIVATE_TOKEN" not in rendered

    plan = run_cli(
        tmp_path,
        "preflight",
        "connected-plan",
        "--platform",
        "getcourse",
        "--expect-origin",
        "school.operator.edu",
        "--query",
        "course-specific question",
        "--link-pattern",
        "*/lessons/*",
    )

    assert plan["schema"] == "aoa_course_connected_source_plan_v1"
    assert plan["ready"] is True
    assert plan["live_scope"] == "bounded"
    assert plan["link_pattern"] == "*/lessons/*"
    assert any("sync browser-live" in command for command in plan["next_commands"])
    assert any("smoke browser-live" in command for command in plan["next_commands"])
    assert any("--link-pattern '*/lessons/*'" in command for command in plan["next_commands"])
    assert any("calibration connected-run --mode live --allow-network" in command for command in plan["next_commands"])
    assert any("--link-pattern '*/lessons/*'" in command for command in plan["next_commands"] if "calibration connected-run" in command)
    assert any("calibration build" in command for command in plan["next_commands"])
    assert any("${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/getcourse-live-smoke" in command for command in plan["next_commands"])
    assert plan["connected_run_plan"]["ready"] is True
    assert plan["connected_run_plan"]["source_ids"] == [plan["source_plans"][0]["source_id"]]
    assert any("${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/connected-live-calibration" in action["artifact_path"] for stage in plan["stages"] for action in stage["actions"] if action["kind"] == "calibration")
    plan = plan["browser_auth_plans"][0]
    assert plan["ready"] is True
    assert plan["source_hosts"] == ["school.operator.edu"]
    assert "capture-browser-state getcourse account" in plan["commands"]["capture"]
    assert "preflight connected-plan --platform getcourse" in plan["commands"]["recheck"]
    rendered_plan = json.dumps(plan)
    assert "SUPER_PRIVATE_COOKIE" not in rendered_plan
    assert "SUPER_PRIVATE_TOKEN" not in rendered_plan

    runbook_path = tmp_path / "artifacts" / "connected-source-runbook.md"
    plan_with_runbook = run_cli(
        tmp_path,
        "preflight",
        "connected-plan",
        "--platform",
        "getcourse",
        "--expect-origin",
        "school.operator.edu",
        "--query",
        "course-specific question",
        "--link-pattern",
        "*/lessons/*",
        "--write-runbook",
        str(runbook_path),
    )

    assert plan_with_runbook["runbook"]["written"] is True
    assert Path(str(plan_with_runbook["runbook"]["path"])).is_file()
    runbook = runbook_path.read_text(encoding="utf-8")
    assert "# Connected Source Runbook" in runbook
    assert "Browser Auth Plans" in runbook
    assert "capture-browser-state getcourse account" in runbook
    assert "preflight connected-plan --platform getcourse" in runbook
    assert "calibration connected-run --mode live --allow-network" in runbook
    assert "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/connected-live-calibration" in runbook
    assert "secret" not in runbook

    readiness = run_cli(
        tmp_path,
        "readiness",
        "--platform",
        "getcourse",
        "--expect-origin",
        "school.example",
        "--query",
        "course-specific question",
        "--link-pattern",
        "*/lessons/*",
        "--max-lessons",
        "7",
        "--max-pages",
        "3",
        "--max-sources",
        "4",
    )
    assert readiness["connected_live_ready"] is True
    assert readiness["connected_source_plan"]["live_scope"] == "bounded"
    assert readiness["connected_source_plan"]["include_step_sources"] is False
    assert readiness["connected_source_plan"]["max_lessons"] == 7
    assert readiness["connected_source_plan"]["max_pages"] == 3
    assert readiness["connected_source_plan"]["max_sources"] == 4
    assert readiness["connected_source_plan"]["connected_run_plan"]["ready"] is True
    assert "--link-pattern '*/lessons/*'" in readiness["connected_source_plan"]["connected_run_plan"]["command"]
    assert "--max-lessons 7" in readiness["connected_source_plan"]["connected_run_plan"]["command"]
    assert "--max-pages 3" in readiness["connected_source_plan"]["connected_run_plan"]["command"]
    assert "--max-sources 4" in readiness["connected_source_plan"]["connected_run_plan"]["command"]
    assert any("--link-pattern '*/lessons/*'" in command for command in readiness["next_commands"] if "calibration connected-run" in command)
    assert any("--max-lessons 7" in command for command in readiness["next_commands"] if "calibration connected-run" in command)
    assert any("--max-pages 3" in command for command in readiness["next_commands"] if "calibration connected-run" in command)
    assert any("--max-sources 4" in command for command in readiness["next_commands"] if "calibration connected-run" in command)


def test_cli_and_mcp_connected_plan_can_scope_to_selected_source(tmp_path: Path) -> None:
    source_a = run_cli(tmp_path, "sources", "add", "https://a.operator.edu/teach/control/stream", "--platform", "getcourse", "--title", "A")["source"]
    source_b = run_cli(tmp_path, "sources", "add", "https://b.operator.edu/teach/control/stream", "--platform", "getcourse", "--title", "B")["source"]
    state_file = tmp_path / "auth" / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "secret", "domain": ".a.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://a.operator.edu", "localStorage": [{"name": "token", "value": "secret"}]}],
        }),
        encoding="utf-8",
    )

    unscoped = run_cli(tmp_path, "preflight", "connected-plan", "--platform", "getcourse")
    scoped = run_cli(tmp_path, "preflight", "connected-plan", "--platform", "getcourse", "--source-id", str(source_a["source_id"]))
    readiness = run_cli(tmp_path, "readiness", "--platform", "getcourse", "--source-id", str(source_a["source_id"]))
    mcp = run_cli(
        tmp_path,
        "mcp",
        "call",
        "connected_source_plan",
        json.dumps({"platforms": ["getcourse"], "source_ids": [source_a["source_id"]]}),
    )

    assert unscoped["ready"] is False
    assert {source["source_id"] for source in unscoped["source_plans"]} == {source_a["source_id"], source_b["source_id"]}
    candidates = unscoped["browser_auth_plans"][0]["state_file_candidates"]
    assert {candidate["host"] for candidate in candidates} == {"a.operator.edu", "b.operator.edu"}
    candidate_a = next(candidate for candidate in candidates if candidate["host"] == "a.operator.edu")
    assert candidate_a["state_file"].endswith("/getcourse/a-operator-edu.storage-state.json")
    assert candidate_a["selected_by_default"] is True
    assert candidate_a["source_ids"] == [source_a["source_id"]]
    assert f"--source-id {source_a['source_id']}" in candidate_a["commands"]["recheck"]
    assert str(source_b["source_id"]) not in candidate_a["commands"]["recheck"]
    assert scoped["ready"] is True
    assert scoped["source_ids"] == [source_a["source_id"]]
    assert [source["source_id"] for source in scoped["source_plans"]] == [source_a["source_id"]]
    assert scoped["browser_auth_plans"][0]["state_file_candidates"][0]["host"] == "a.operator.edu"
    assert str(source_b["source_id"]) not in scoped["connected_run_plan"]["command"]
    assert readiness["connected_live_ready"] is True
    assert readiness["sources"]["selected_source_ids"] == [source_a["source_id"]]
    assert readiness["sources"]["selected_source_count"] == 1
    assert mcp["result"]["plan"]["ready"] is True
    assert mcp["result"]["plan"]["source_ids"] == [source_a["source_id"]]


def test_cli_stepik_fixture_flow(tmp_path: Path) -> None:
    run_cli(tmp_path, "materialize", "stepik-fixture", "--run", "stepik-fixture")
    run_cli(tmp_path, "build-index", "--run", "stepik-fixture")
    run_cli(tmp_path, "build-semantic-index", "--run", "stepik-fixture")
    run_cli(tmp_path, "build-graph", "--run", "stepik-fixture")
    answer = run_cli(tmp_path, "answer", "Stepik public API evidence", "--run", "stepik-fixture")
    assert answer["result_count"] >= 1
    assert answer["evidence_chain"]


def test_cli_refresh_query_fixture_cycle(tmp_path: Path) -> None:
    source = run_cli(tmp_path, "sources", "add", "67", "--platform", "stepik", "--title", "Stepik Refresh Fixture")["source"]
    run_cli(tmp_path, "sources", "add", "not-a-course", "--platform", "stepik", "--title", "Broken Stepik Fixture")
    sync = run_cli(
        tmp_path,
        "sync",
        "stepik-fixture",
        "--run",
        "stepik-refresh-initial",
        "--source-id",
        str(source["source_id"]),
        "--build-artifacts",
    )
    assert sync["source_count"] == 1
    assert sync["failed_count"] == 0
    initial_run = sync["synced_sources"][0]["run_id"]
    run_cli(tmp_path, "build-semantic-index", "--run", str(initial_run))

    plan = run_cli(
        tmp_path,
        "refresh",
        "query",
        "Stepik public API evidence",
        "--run",
        str(initial_run),
        "--mode",
        "hybrid",
    )
    assert plan["schema"] == "aoa_course_refresh_cycle_v1"
    assert plan["status"] == "planned"
    assert plan["network_touched"] is False

    refreshed = run_cli(
        tmp_path,
        "refresh",
        "query",
        "Stepik public API evidence",
        "--run",
        str(initial_run),
        "--mode",
        "hybrid",
        "--strategy",
        "fixture",
        "--execute",
        "--sync-run",
        "stepik-refresh-cycle",
    )
    assert refreshed["status"] == "ok"
    assert refreshed["network_touched"] is False
    assert refreshed["refreshed_answer_packet"]["result_count"] >= 1
    assert refreshed["comparison"]["source_id_preserved"] is True


def test_cli_stepik_account_fixture_discovery(tmp_path: Path) -> None:
    receipt = run_cli(
        tmp_path,
        "discover",
        "stepik-account",
        "--from-fixture",
        "--run",
        "stepik-account-discovery-fixture",
        "--register",
    )

    assert receipt["status"] == "ok"
    assert receipt["course_count"] == 2
    assert len(receipt["registered_sources"]) == 2
    registry = run_cli(tmp_path, "sources", "list")["registry"]
    assert {source["source_ref"] for source in registry["sources"]} == {"67", "100"}


def test_cli_browser_hard_adapter_fixture_flow(tmp_path: Path) -> None:
    for platform, query in [
        ("getcourse", "GetCourse bootloader rollback evidence"),
        ("skillspace", "Skillspace logcat bugreport evidence"),
    ]:
        run_id = f"{platform}-browser-fixture"
        run_cli(tmp_path, "materialize", "browser-fixture", "--platform", platform, "--run", run_id)
        run_cli(tmp_path, "build-index", "--run", run_id)
        run_cli(tmp_path, "build-graph", "--run", run_id)
        answer = run_cli(tmp_path, "answer", query, "--run", run_id)
        assert answer["result_count"] >= 1
        assert answer["evidence_chain"]
    eval_result = run_cli(tmp_path, "eval", "browser-hard-adapters")
    assert eval_result["status"] == "ok"
    progress_comments_eval = run_cli(tmp_path, "eval", "browser-progress-comments")
    assert progress_comments_eval["status"] == "ok"
    transcripts_eval = run_cli(tmp_path, "eval", "browser-transcripts")
    assert transcripts_eval["status"] == "ok"
    mcp_context = run_cli(tmp_path, "mcp", "call", "lesson_context", '{"query":"mentor anti-rollback vendor boot","run":"getcourse-browser-fixture"}')
    assert mcp_context["result"]["answer_packet"]["result_count"] >= 1
    assert mcp_context["result"]["answer_packet"]["evidence_chain"]
    assert mcp_context["result"]["graph_context"]["status"] == "ready"
    assert mcp_context["result"]["graph_context"]["contexts"][0]["graph"]["neighbors"]
    smoke = run_cli(tmp_path, "smoke", "browser-fixture", "--platform", "getcourse", "--run", "getcourse-browser-smoke-fixture")
    assert smoke["status"] == "ok"
    assert smoke["course"]["comment_count"] >= 1
    assert smoke["course"]["transcript_count"] >= 2
    assert smoke["artifacts"]["answer"]["result_count"] >= 1


def test_cli_answer_quality_eval_proves_source_path_freshness_and_evidence(tmp_path: Path) -> None:
    run_cli(tmp_path, "materialize", "fixture", "--run", "starter-fixture")
    run_cli(tmp_path, "build-index", "--run", "starter-fixture")
    run_cli(tmp_path, "build-semantic-index", "--run", "starter-fixture")
    run_cli(tmp_path, "materialize", "stepik-fixture", "--run", "stepik-fixture")
    run_cli(tmp_path, "build-index", "--run", "stepik-fixture")
    run_cli(tmp_path, "build-semantic-index", "--run", "stepik-fixture")
    run_cli(tmp_path, "materialize", "browser-fixture", "--platform", "getcourse", "--run", "getcourse-browser-fixture")
    run_cli(tmp_path, "build-index", "--run", "getcourse-browser-fixture")

    result = run_cli(tmp_path, "eval", "answer-quality")

    assert result["status"] == "ok"
    assert result["suite_id"] == "answer-quality-packets"
    assert all(case["quality_ready"] is True for case in result["case_results"])
    assert {case["failure_count"] for case in result["case_results"]} == {0}


def test_cli_retrieval_loop_eval_proves_cli_and_mcp_context(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "eval", "retrieval-loop")

    assert result["schema"] == "aoa_course_eval_retrieval_loop_v1"
    assert result["status"] == "ok"
    assert result["network_touched"] is False
    assert set(result["prepared_runs"]) == {
        "starter-fixture",
        "getcourse-browser-fixture",
        "skillspace-browser-fixture",
        "stepik-fixture",
    }
    assert {case["failure_count"] for case in result["case_results"]} == {0}
    assert all(case["answer_result_count"] >= 1 for case in result["case_results"])
    assert all(case["mcp_search_result_count"] >= 1 for case in result["case_results"])
    assert {case["lesson_graph_status"] for case in result["case_results"]} == {"ready"}


def test_cli_freshness_ranking_eval_proves_current_beats_stale_tie(tmp_path: Path) -> None:
    fixture = Path("connector/fixtures/course/freshness_conflict_course.json")
    run_cli(tmp_path, "materialize", "fixture", "--run", "freshness-ranking-fixture", "--fixture", str(fixture))
    run_cli(tmp_path, "build-index", "--run", "freshness-ranking-fixture")
    run_cli(tmp_path, "build-semantic-index", "--run", "freshness-ranking-fixture")

    result = run_cli(tmp_path, "eval", "freshness-ranking")

    assert result["status"] == "ok"
    assert result["suite_id"] == "freshness-ranking"
    assert {case["failure_count"] for case in result["case_results"]} == {0}


def test_cli_authority_ranking_eval_proves_higher_authority_beats_lower_tie(tmp_path: Path) -> None:
    fixture = Path("connector/fixtures/course/authority_conflict_course.json")
    run_cli(tmp_path, "materialize", "fixture", "--run", "authority-ranking-fixture", "--fixture", str(fixture))
    run_cli(tmp_path, "build-index", "--run", "authority-ranking-fixture")
    run_cli(tmp_path, "build-semantic-index", "--run", "authority-ranking-fixture")

    result = run_cli(tmp_path, "eval", "authority-ranking")

    assert result["status"] == "ok"
    assert result["suite_id"] == "authority-ranking"
    assert {case["failure_count"] for case in result["case_results"]} == {0}


def test_cli_adapter_authority_eval_proves_adapter_metadata_reaches_query(tmp_path: Path) -> None:
    run_cli(tmp_path, "materialize", "stepik-fixture", "--run", "stepik-fixture")
    run_cli(tmp_path, "build-index", "--run", "stepik-fixture")
    for platform in ["getcourse", "skillspace"]:
        run_id = f"{platform}-browser-fixture"
        run_cli(tmp_path, "materialize", "browser-fixture", "--platform", platform, "--run", run_id)
        run_cli(tmp_path, "build-index", "--run", run_id)

    result = run_cli(tmp_path, "eval", "adapter-authority")

    assert result["status"] == "ok"
    assert result["suite_id"] == "adapter-authority"
    assert {case["failure_count"] for case in result["case_results"]} == {0}


def test_cli_live_calibration_eval_and_build_route(tmp_path: Path) -> None:
    eval_result = run_cli(tmp_path, "eval", "live-calibration")

    assert eval_result["status"] == "ok"
    assert eval_result["suite_id"] == "live-calibration"
    assert eval_result["report_count"] == 3
    assert eval_result["platforms"] == ["getcourse", "skillspace", "stepik"]
    assert eval_result["quality"]["transcript_count_total"] >= 4
    assert eval_result["quality"]["caption_sidecar_count_total"] >= 2
    assert eval_result["quality"]["caption_resource_error_count_total"] == 0
    assert Path(str(eval_result["packet_path"])).is_file()

    getcourse = run_cli(tmp_path, "smoke", "browser-fixture", "--platform", "getcourse", "--run", "getcourse-calibration-cli", "--register")
    skillspace = run_cli(tmp_path, "smoke", "browser-fixture", "--platform", "skillspace", "--run", "skillspace-calibration-cli", "--register")
    stepik = run_cli(tmp_path, "smoke", "stepik-fixture", "67", "--run", "stepik-calibration-cli", "--query", "Stepik public API evidence")
    preflight = run_cli(tmp_path, "preflight", "live", "--platform", "stepik")
    report_paths = []
    for name, payload in [("getcourse", getcourse), ("skillspace", skillspace), ("stepik", stepik)]:
        path = tmp_path / f"{name}-smoke.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        report_paths.append(path)
    preflight_path = tmp_path / "stepik-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    build_result = run_cli(
        tmp_path,
        "calibration",
        "build",
        "--run",
        "manual-calibration-cli",
        "--report",
        str(report_paths[0]),
        "--report",
        str(report_paths[1]),
        "--report",
        str(report_paths[2]),
        "--preflight-report",
        str(preflight_path),
    )

    assert build_result["status"] == "ok"
    assert build_result["report_count"] == 3
    assert Path(str(build_result["packet_path"])).is_file()
    intake_result = run_cli(
        tmp_path,
        "calibration",
        "intake",
        "--run",
        "manual-calibration-intake-cli",
        "--packet",
        str(build_result["packet_path"]),
    )

    assert intake_result["schema"] == "aoa_course_live_calibration_intake_v1"
    assert intake_result["status"] == "ok"
    assert intake_result["authority"]["central_proof_owner"] == "aoa-evals"
    assert Path(str(intake_result["intake_path"])).is_file()

    connected = run_cli(tmp_path, "calibration", "connected-run", "--mode", "fixture", "--run", "connected-fixture-cli")
    assert connected["schema"] == "aoa_course_connected_calibration_run_receipt_v1"
    assert connected["status"] == "ok"
    assert connected["network_touched"] is False
    assert connected["snapshot_audit"]["status"] == "ok"
    assert connected["snapshot_audit"]["browser_report_count"] == 2
    assert connected["snapshot_audit"]["all_snapshot_audits_ok"] is True
    assert Path(str(connected["artifacts"]["packet_path"])).is_file()
    assert Path(str(connected["artifacts"]["intake_path"])).is_file()
    assert Path(str(connected["receipt_path"])).is_file()
    connected_status = run_cli(tmp_path, "calibration", "status", "--run", "connected-fixture-cli")
    assert connected_status["schema"] == "aoa_course_connected_calibration_run_status_v1"
    assert connected_status["status"] == "ok"
    assert connected_status["read_only"] is True
    assert connected_status["snapshot_audit"] == connected["snapshot_audit"]
    status_entry = connected_status["query_plan"]["entries"][0]
    assert status_entry["query_mode"] in {"hybrid", "keyword"}
    assert f"--mode {status_entry['query_mode']}" in status_entry["commands"]["query"]
    assert status_entry["commands"]["lesson_context"].startswith("aoa-course lesson-context ")
    assert "--graph-limit 12" in status_entry["commands"]["lesson_context"]
    assert status_entry["mcp_commands"]["search"].startswith("aoa-course mcp call search ")
    assert status_entry["mcp_commands"]["answer"].startswith("aoa-course mcp call answer ")
    assert "lesson_context" in status_entry["mcp_commands"]
    assert "evidence_report" in status_entry["mcp_commands"]
    mcp_connected_status = run_cli(tmp_path, "mcp", "call", "connected_run_status", '{"run":"connected-fixture-cli"}')
    assert mcp_connected_status["result"]["connected_run"]["status"] == "ok"
    assert mcp_connected_status["result"]["connected_run"]["network_touched"] is False
    assert mcp_connected_status["result"]["connected_run"]["snapshot_audit"]["status"] == "ok"
    mcp_entry = mcp_connected_status["result"]["connected_run"]["query_plan"]["entries"][0]
    assert mcp_entry["mcp_commands"]["lesson_context"].startswith("aoa-course mcp call lesson_context ")
    assert mcp_entry["mcp_commands"]["answer"].startswith("aoa-course mcp call answer ")
    assert '"graph_limit":12' in mcp_entry["mcp_commands"]["lesson_context"]


def test_cli_browser_course_tree_crawl_fixture_flow(tmp_path: Path) -> None:
    for platform, query in [
        ("getcourse", "GetCourse bootloader rollback evidence"),
        ("skillspace", "Skillspace logcat bugreport evidence"),
    ]:
        run_id = f"{platform}-browser-crawl-fixture"
        receipt = run_cli(tmp_path, "crawl", "browser-fixture", "--platform", platform, "--run", run_id)
        assert receipt["crawl"]["discovered_lesson_count"] == 2
        run_cli(tmp_path, "build-index", "--run", run_id)
        run_cli(tmp_path, "build-graph", "--run", run_id)
        answer = run_cli(tmp_path, "answer", query, "--run", run_id)
        assert answer["result_count"] >= 1
        assert answer["evidence_chain"]
    eval_result = run_cli(tmp_path, "eval", "browser-crawl")
    assert eval_result["status"] == "ok"


def test_cli_browser_account_discovery_registers_sources(tmp_path: Path) -> None:
    for platform in ["getcourse", "skillspace"]:
        receipt = run_cli(
            tmp_path,
            "discover",
            "browser-fixture",
            "--platform",
            platform,
            "--run",
            f"{platform}-browser-discovery-fixture",
            "--register",
        )
        assert receipt["course_count"] == 3
        assert receipt["page_count"] == 2
        assert receipt["pagination"]["next_link_count"] == 1
        assert len(receipt["registered_sources"]) == 3
    registry = run_cli(tmp_path, "sources", "list")["registry"]
    assert len(registry["sources"]) == 6
    eval_result = run_cli(tmp_path, "eval", "browser-discovery")
    assert eval_result["status"] == "ok"


def test_cli_browser_source_sync_checkpoint_flow(tmp_path: Path) -> None:
    for platform in ["getcourse", "skillspace"]:
        run_cli(
            tmp_path,
            "discover",
            "browser-fixture",
            "--platform",
            platform,
            "--run",
            f"{platform}-browser-discovery-fixture",
            "--register",
        )
    receipt = run_cli(tmp_path, "sync", "browser-fixture", "--run", "browser-sync-fixture", "--build-artifacts")
    assert receipt["status"] == "ok"
    assert receipt["synced_count"] == 6
    status = run_cli(tmp_path, "sync", "status", "--run", "browser-sync-fixture")
    assert status["ok_count"] == 6
    eval_result = run_cli(tmp_path, "eval", "browser-sync")
    assert eval_result["status"] == "ok"
    mcp_status = run_cli(tmp_path, "mcp", "call", "sync_status", '{"sync_run":"browser-sync-fixture"}')
    assert mcp_status["result"]["sync"]["ok_count"] == 6


class _EmbeddingServer:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self._server = HTTPServer(("127.0.0.1", 0), self._handler())
        self.url = f"http://127.0.0.1:{self._server.server_port}/embeddings"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)
        self._server.server_close()

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - stdlib handler API.
                length = int(self.headers.get("Content-Length") or "0")
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                inputs = body.get("input")
                if not isinstance(inputs, list):
                    self.send_response(400)
                    self.end_headers()
                    return
                owner.requests.append(
                    {
                        "authorization": self.headers.get("Authorization"),
                        "model": body.get("model"),
                        "count": len(inputs),
                    }
                )
                encoded = json.dumps({"data": [{"embedding": _fixture_embedding(str(text))} for text in inputs]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        return Handler


def _fixture_embedding(text: str) -> list[float]:
    lowered = text.casefold()
    return [
        1.0 if "bootloader" in lowered else 0.0,
        1.0 if "rollback" in lowered else 0.0,
        0.8 if "unlock" in lowered else 0.0,
        0.7 if "vendor" in lowered else 0.0,
        0.6 if "mentor" in lowered else 0.0,
        min(len(lowered.split()) / 40.0, 1.0),
    ]
