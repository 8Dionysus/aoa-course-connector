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


def test_cli_starter_flow(tmp_path: Path) -> None:
    assert run_cli(tmp_path, "doctor")["status"] == "ok"
    run_cli(tmp_path, "init")
    run_cli(tmp_path, "materialize", "fixture", "--run", "starter-fixture")
    run_cli(tmp_path, "build-index", "--run", "starter-fixture")
    run_cli(tmp_path, "build-graph", "--run", "starter-fixture")
    answer = run_cli(tmp_path, "answer", "bootloader unlock rollback", "--run", "starter-fixture")
    assert answer["result_count"] >= 1
    assert answer["evidence_chain"]
    evidence_inspect = run_cli(tmp_path, "evidence", "inspect", "rollback", "--run", "starter-fixture")
    assert evidence_inspect["evidence_chain"]
    assert evidence_inspect["freshness_report"]["has_source_timestamps"] is True
    tools = run_cli(tmp_path, "mcp", "tools")
    assert tools["server"] == "aoa-course-connector-mcp"
    graph = run_cli(tmp_path, "mcp", "call", "graph_neighbors", '{"node_id":"lesson:starter:unlock-risk","run":"starter-fixture"}')
    assert graph["result"]["graph"]["node"]["node_id"] == "lesson:starter:unlock-risk"
    freshness = run_cli(tmp_path, "mcp", "call", "freshness_report", '{"run":"starter-fixture"}')
    assert freshness["result"]["freshness"]["states"]
    evidence = run_cli(tmp_path, "mcp", "call", "evidence_report", '{"query":"rollback","run":"starter-fixture"}')
    assert evidence["result"]["evidence_chain"]
    preflight = run_cli(tmp_path, "mcp", "call", "live_preflight", '{"platforms":["stepik"]}')
    assert preflight["result"]["preflight"]["network_touched"] is False
    plan = run_cli(tmp_path, "mcp", "call", "connected_source_plan", '{"platforms":["stepik"]}')
    assert plan["result"]["plan"]["network_touched"] is False


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


def test_mcp_stdio_jsonrpc_flow(tmp_path: Path) -> None:
    run_cli(tmp_path, "materialize", "fixture", "--run", "starter-fixture")
    run_cli(tmp_path, "build-index", "--run", "starter-fixture")
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search", "arguments": {"query": "rollback", "run": "starter-fixture"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "evidence_report", "arguments": {"query": "rollback", "run": "starter-fixture"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "live_preflight", "arguments": {"platforms": ["stepik"]}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "connected_source_plan", "arguments": {"platforms": ["stepik"]}}},
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
    assert [response["id"] for response in responses] == [1, 2, 3, 4, 5, 6]
    assert responses[0]["result"]["serverInfo"]["name"] == "aoa-course-connector-mcp"
    assert any(tool["name"] == "search" for tool in responses[1]["result"]["tools"])
    assert responses[2]["result"]["structuredContent"]["results"]
    assert responses[3]["result"]["structuredContent"]["evidence_chain"]
    assert responses[4]["result"]["structuredContent"]["preflight"]["network_touched"] is False
    assert responses[5]["result"]["structuredContent"]["plan"]["network_touched"] is False


def test_cli_browser_auth_state_inspect(tmp_path: Path) -> None:
    plan = run_cli(tmp_path, "auth", "plan-browser-state", "getcourse", "https://school.example")
    assert "capture-browser-state" in plan["capture_command"]
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
    run_cli(tmp_path, "sources", "add", "https://school.example/teach/control/stream", "--platform", "getcourse", "--title", "School")
    state_file = tmp_path / "auth" / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "secret", "domain": ".school.example", "path": "/"}],
            "origins": [{"origin": "https://school.example", "localStorage": [{"name": "token", "value": "secret"}]}],
        }),
        encoding="utf-8",
    )

    report = run_cli(tmp_path, "preflight", "live", "--platform", "getcourse", "--expect-origin", "school.example")

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
        "school.example",
        "--query",
        "course-specific question",
    )

    assert plan["schema"] == "aoa_course_connected_source_plan_v1"
    assert plan["ready"] is True
    assert plan["live_scope"] == "bounded"
    assert any("sync browser-live" in command for command in plan["next_commands"])
    assert any("smoke browser-live" in command for command in plan["next_commands"])
    assert any("calibration build" in command for command in plan["next_commands"])
    assert any("${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/getcourse-live-smoke" in command for command in plan["next_commands"])
    assert any("${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/connected-live-calibration" in action["artifact_path"] for stage in plan["stages"] for action in stage["actions"] if action["kind"] == "calibration")
    handoff = plan["browser_auth_handoffs"][0]
    assert handoff["ready"] is True
    assert handoff["source_hosts"] == ["school.example"]
    assert "capture-browser-state getcourse account" in handoff["commands"]["capture"]
    assert "preflight connected-plan --platform getcourse" in handoff["commands"]["recheck"]
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
        "school.example",
        "--write-runbook",
        str(runbook_path),
    )

    assert plan_with_runbook["runbook"]["written"] is True
    assert Path(str(plan_with_runbook["runbook"]["path"])).is_file()
    runbook = runbook_path.read_text(encoding="utf-8")
    assert "# Connected Source Runbook" in runbook
    assert "Browser Auth Handoffs" in runbook
    assert "capture-browser-state getcourse account" in runbook
    assert "preflight connected-plan --platform getcourse" in runbook
    assert "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/connected-live-calibration" in runbook
    assert "secret" not in runbook


def test_cli_stepik_fixture_flow(tmp_path: Path) -> None:
    run_cli(tmp_path, "materialize", "stepik-fixture", "--run", "stepik-fixture")
    run_cli(tmp_path, "build-index", "--run", "stepik-fixture")
    run_cli(tmp_path, "build-semantic-index", "--run", "stepik-fixture")
    run_cli(tmp_path, "build-graph", "--run", "stepik-fixture")
    answer = run_cli(tmp_path, "answer", "Stepik public API evidence", "--run", "stepik-fixture")
    assert answer["result_count"] >= 1
    assert answer["evidence_chain"]


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
    assert {case["failure_count"] for case in result["case_results"]} == {0}


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
