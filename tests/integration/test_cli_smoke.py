from __future__ import annotations

import json
import os
import subprocess
import sys
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
    tools = run_cli(tmp_path, "mcp", "tools")
    assert tools["server"] == "aoa-course-connector-mcp"


def test_mcp_stdio_jsonrpc_flow(tmp_path: Path) -> None:
    run_cli(tmp_path, "materialize", "fixture", "--run", "starter-fixture")
    run_cli(tmp_path, "build-index", "--run", "starter-fixture")
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search", "arguments": {"query": "rollback", "run": "starter-fixture"}}},
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
    assert [response["id"] for response in responses] == [1, 2, 3]
    assert responses[0]["result"]["serverInfo"]["name"] == "aoa-course-connector-mcp"
    assert any(tool["name"] == "search" for tool in responses[1]["result"]["tools"])
    assert responses[2]["result"]["structuredContent"]["results"]


def test_cli_browser_auth_state_inspect(tmp_path: Path) -> None:
    plan = run_cli(tmp_path, "auth", "plan-browser-state", "getcourse", "https://school.example")
    assert "capture-browser-state" in plan["capture_command"]
    state_file = Path(str(plan["state_file"]))
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "secret", "domain": ".school.example", "path": "/"}],
            "origins": [{"origin": "https://school.example", "localStorage": [{"name": "token", "value": "secret"}]}],
        }),
        encoding="utf-8",
    )

    status = run_cli(tmp_path, "auth", "inspect-browser-state", str(state_file), "--expect-origin-contains", "school.example")

    assert status["status"] == "ok"
    assert status["usable"] is True
    assert status["cookie_count"] == 1
    assert status["local_storage_entry_count"] == 1


def test_cli_stepik_fixture_flow(tmp_path: Path) -> None:
    run_cli(tmp_path, "materialize", "stepik-fixture", "--run", "stepik-fixture")
    run_cli(tmp_path, "build-index", "--run", "stepik-fixture")
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
    mcp_context = run_cli(tmp_path, "mcp", "call", "lesson_context", '{"query":"mentor anti-rollback vendor boot","run":"getcourse-browser-fixture"}')
    assert mcp_context["result"]["answer_packet"]["result_count"] >= 1
    assert mcp_context["result"]["answer_packet"]["evidence_chain"]
    smoke = run_cli(tmp_path, "smoke", "browser-fixture", "--platform", "getcourse", "--run", "getcourse-browser-smoke-fixture")
    assert smoke["status"] == "ok"
    assert smoke["course"]["comment_count"] >= 1
    assert smoke["artifacts"]["answer"]["result_count"] >= 1


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
