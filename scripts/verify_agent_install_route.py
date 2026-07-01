#!/usr/bin/env python3
"""Verify a fresh agent can install and run the offline starter route."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class StdioVerificationError(ValueError):
    pass


def _parse_stdio_responses(stdout: str) -> dict[int, dict[str, object]]:
    responses: dict[int, dict[str, object]] = {}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StdioVerificationError(f"invalid JSON-RPC response line: {line}") from exc
        if not isinstance(payload, dict):
            raise StdioVerificationError(f"JSON-RPC response must be an object: {payload!r}")
        response_id = payload.get("id")
        if isinstance(response_id, int):
            responses[response_id] = payload
    return responses


def _require_tool_success(responses: dict[int, dict[str, object]], request_id: int, tool_name: str) -> dict[str, object]:
    response = responses.get(request_id)
    if response is None:
        raise StdioVerificationError(f"missing JSON-RPC response for request id {request_id}")
    if "error" in response:
        raise StdioVerificationError(f"{tool_name} JSON-RPC error: {response['error']}")
    result = response.get("result")
    if not isinstance(result, dict):
        raise StdioVerificationError(f"{tool_name} response missing result object")
    if result.get("isError") is not False:
        raise StdioVerificationError(f"{tool_name} returned MCP tool error: {result.get('structuredContent')}")
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        raise StdioVerificationError(f"{tool_name} response missing structuredContent")
    if structured.get("tool") != tool_name:
        raise StdioVerificationError(f"{tool_name} response reported wrong tool: {structured.get('tool')!r}")
    return structured


def _verify_stdio_tool_responses(stdout: str) -> None:
    responses = _parse_stdio_responses(stdout)
    search = _require_tool_success(responses, 3, "search")
    if not search.get("results"):
        raise StdioVerificationError("search stdio response did not return results")
    preflight = _require_tool_success(responses, 4, "live_preflight")
    preflight_payload = preflight.get("preflight")
    if not isinstance(preflight_payload, dict) or preflight_payload.get("network_touched") is not False:
        raise StdioVerificationError("live_preflight stdio response did not prove read-only preflight")
    plan = _require_tool_success(responses, 5, "connected_source_plan")
    plan_payload = plan.get("plan")
    if not isinstance(plan_payload, dict) or plan_payload.get("network_touched") is not False:
        raise StdioVerificationError("connected_source_plan stdio response did not prove read-only plan")
    if plan_payload.get("live_scope") != "bounded":
        raise StdioVerificationError("connected_source_plan stdio response did not preserve live_scope=bounded")
    handoff = plan_payload.get("connected_run_handoff")
    if not isinstance(handoff, dict) or handoff.get("kind") != "connected_run":
        raise StdioVerificationError("connected_source_plan stdio response missing connected_run_handoff")
    if handoff.get("network_touched") is not True:
        raise StdioVerificationError("connected_run_handoff did not declare network-touching execution")
    if handoff.get("ready") is True and "calibration connected-run --mode live --allow-network" not in str(handoff.get("command") or ""):
        raise StdioVerificationError("connected_run_handoff ready command did not expose executable live route")
    if handoff.get("ready") is False and not handoff.get("blocked_by"):
        raise StdioVerificationError("blocked connected_run_handoff did not explain blockers")
    semantic = _require_tool_success(responses, 6, "semantic_provider_preflight")
    semantic_payload = semantic.get("preflight")
    if not isinstance(semantic_payload, dict) or semantic_payload.get("network_touched") is not False:
        raise StdioVerificationError("semantic_provider_preflight stdio response did not prove read-only provider preflight")
    audit = _require_tool_success(responses, 7, "goal_audit")
    if audit.get("ready_for_operator_connection") is not True:
        raise StdioVerificationError("goal_audit stdio response did not report ready_for_operator_connection")
    if audit.get("goal_complete") is not False:
        raise StdioVerificationError("goal_audit stdio response must keep goal_complete false before live calibration")
    handoff = audit.get("connection_handoff")
    if not isinstance(handoff, dict) or handoff.get("schema") != "aoa_course_connection_handoff_v1":
        raise StdioVerificationError("goal_audit stdio response missing connection_handoff")
    if handoff.get("network_touched") is not False:
        raise StdioVerificationError("connection_handoff must be read-only")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="aoa-course-install-") as tmp:
        copy_root = Path(tmp) / "repo"
        ignore = shutil.ignore_patterns(".git", ".connector-state/data/*", ".connector-state/cache/*", ".connector-state/auth/*", ".connector-state/artifacts/*", "__pycache__", ".pytest_cache", "*.egg-info", "dist", "build")
        shutil.copytree(repo_root, copy_root, ignore=ignore)
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        env["AOA_COURSE_INSTANCE_ROOT"] = str(Path(tmp) / "state")
        connection_handoff_path = Path(tmp) / "state" / "artifacts" / "goal-connection-handoff.md"
        commands = [
            [sys.executable, "scripts/validate_connector.py"],
            [sys.executable, "-m", "compileall", "-q", "src", "scripts"],
            [sys.executable, "-m", "aoa_course_connector.cli", "doctor"],
            [sys.executable, "-m", "aoa_course_connector.cli", "bootstrap", "fixture", "--run", "starter-fixture", "--connected-run", "connected-calibration"],
            [sys.executable, "-m", "aoa_course_connector.cli", "readiness", "--run", "starter-fixture", "--connected-run", "connected-calibration", "--require-ready"],
            [sys.executable, "-m", "aoa_course_connector.cli", "goal", "audit", "--run", "starter-fixture", "--connected-run", "connected-calibration", "--require-ready-for-connection"],
            [sys.executable, "-m", "aoa_course_connector.cli", "goal", "audit", "--run", "starter-fixture", "--connected-run", "connected-calibration", "--write-connection-handoff", str(connection_handoff_path)],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "fixture", "--run", "starter-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "starter-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-semantic-index", "--run", "starter-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "starter-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "bootloader unlock rollback", "--run", "starter-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "bootloader rollback", "--run", "starter-fixture", "--mode", "hybrid"],
            [sys.executable, "-m", "aoa_course_connector.cli", "refresh", "query", "bootloader rollback", "--run", "starter-fixture", "--mode", "hybrid"],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "stepik-fixture", "--run", "stepik-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "stepik-live", "--help"],
            [sys.executable, "-m", "aoa_course_connector.cli", "discover", "stepik-account", "--from-fixture", "--run", "stepik-account-discovery-fixture", "--register", "--source-limit", "1"],
            [sys.executable, "-m", "aoa_course_connector.cli", "preflight", "live", "--platform", "stepik"],
            [sys.executable, "-m", "aoa_course_connector.cli", "preflight", "semantic-provider", "--run", "starter-fixture", "--require-ready"],
            [sys.executable, "-m", "aoa_course_connector.cli", "discover", "stepik", "67", "--register", "--title", "Stepik course 67"],
            [sys.executable, "-m", "aoa_course_connector.cli", "sync", "stepik-fixture", "--run", "stepik-sync-fixture", "--build-artifacts"],
            [sys.executable, "-m", "aoa_course_connector.cli", "sync", "status", "--run", "stepik-sync-fixture", "--platform", "stepik"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "stepik-sync"],
            [sys.executable, "-m", "aoa_course_connector.cli", "smoke", "stepik-fixture", "67", "--run", "stepik-smoke-fixture", "--query", "Stepik public API evidence"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "stepik-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-semantic-index", "--run", "stepik-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "stepik-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "Stepik public API evidence", "--run", "stepik-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "clean-api"],
            [sys.executable, "-m", "aoa_course_connector.cli", "discover", "browser-fixture", "--platform", "getcourse", "--run", "getcourse-browser-discovery-fixture", "--register"],
            [sys.executable, "-m", "aoa_course_connector.cli", "discover", "browser-fixture", "--platform", "skillspace", "--run", "skillspace-browser-discovery-fixture", "--register"],
            [sys.executable, "-m", "aoa_course_connector.cli", "sources", "list"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "browser-discovery"],
            [sys.executable, "-m", "aoa_course_connector.cli", "sync", "browser-fixture", "--run", "browser-sync-fixture", "--build-artifacts"],
            [sys.executable, "-m", "aoa_course_connector.cli", "sync", "status", "--run", "browser-sync-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "browser-sync"],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "sync_status", '{"sync_run":"browser-sync-fixture"}'],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "browser-fixture", "--platform", "getcourse", "--run", "getcourse-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "getcourse-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "getcourse-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "GetCourse bootloader rollback evidence", "--run", "getcourse-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "answer-quality"],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "fixture", "--run", "freshness-ranking-fixture", "--fixture", "connector/fixtures/course/freshness_conflict_course.json"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "freshness-ranking-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-semantic-index", "--run", "freshness-ranking-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "freshness-ranking"],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "fixture", "--run", "authority-ranking-fixture", "--fixture", "connector/fixtures/course/authority_conflict_course.json"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "authority-ranking-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-semantic-index", "--run", "authority-ranking-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "authority-ranking"],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "browser-fixture", "--platform", "skillspace", "--run", "skillspace-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "skillspace-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "skillspace-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "Skillspace logcat bugreport evidence", "--run", "skillspace-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "browser-hard-adapters"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "browser-progress-comments"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "browser-transcripts"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "adapter-authority"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "live-calibration"],
            [sys.executable, "-m", "aoa_course_connector.cli", "preflight", "live"],
            [sys.executable, "-m", "aoa_course_connector.cli", "preflight", "semantic-provider", "--run", "starter-fixture", "--require-ready"],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "live_preflight", "{}"],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "connected_source_plan", '{"live_scope":"bounded"}'],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "semantic_provider_preflight", '{"run":"starter-fixture"}'],
            [sys.executable, "-m", "aoa_course_connector.cli", "smoke", "browser-fixture", "--platform", "getcourse", "--run", "getcourse-browser-smoke-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "crawl", "browser-fixture", "--platform", "getcourse", "--run", "getcourse-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "getcourse-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "getcourse-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "GetCourse bootloader rollback evidence", "--run", "getcourse-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "crawl", "browser-fixture", "--platform", "skillspace", "--run", "skillspace-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "skillspace-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "skillspace-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "Skillspace logcat bugreport evidence", "--run", "skillspace-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "browser-crawl"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "semantic-index"],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "tools"],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "semantic_search", '{"query":"rollback","run":"starter-fixture"}'],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "hybrid_search", '{"query":"rollback","run":"starter-fixture"}'],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "graph_neighbors", '{"node_id":"lesson:starter:unlock-risk","run":"starter-fixture"}'],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "freshness_report", '{"run":"starter-fixture"}'],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "evidence_report", '{"query":"rollback","run":"starter-fixture"}'],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "refresh_plan", '{"query":"rollback","run":"starter-fixture","mode":"hybrid"}'],
        ]
        if not args.skip_pytest:
            commands.insert(1, [sys.executable, "-m", "pytest", "-q"])
        for command in commands:
            result = subprocess.run(command, cwd=copy_root, env=env, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"failed command: {' '.join(command)}", file=sys.stderr)
                print(result.stdout, file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                return result.returncode
        if not connection_handoff_path.is_file() or "Course Connector Connection Handoff" not in connection_handoff_path.read_text(encoding="utf-8"):
            print("goal connection handoff was not written correctly", file=sys.stderr)
            return 1
        stdio_requests = "\n".join([
            '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"install-route","version":"0"}}}',
            '{"jsonrpc":"2.0","id":2,"method":"tools/list"}',
            '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search","arguments":{"query":"rollback","run":"starter-fixture"}}}',
            '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"live_preflight","arguments":{}}}',
            '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"connected_source_plan","arguments":{"live_scope":"bounded"}}}',
            '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"semantic_provider_preflight","arguments":{"run":"starter-fixture"}}}',
            '{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"goal_audit","arguments":{"runs":["starter-fixture"],"connected_run":"connected-calibration"}}}',
            "",
        ])
        result = subprocess.run(
            [sys.executable, "-m", "aoa_course_connector.mcp.server"],
            input=stdio_requests,
            cwd=copy_root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        try:
            _verify_stdio_tool_responses(result.stdout)
        except StdioVerificationError as exc:
            print("failed MCP stdio route", file=sys.stderr)
            print(str(exc), file=sys.stderr)
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return result.returncode or 1
        if result.returncode != 0:
            print("failed MCP stdio route", file=sys.stderr)
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return result.returncode
    print("agent install route ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
