"""Dependency-free MCP stdio server and local tool dispatcher.

The full runtime registration belongs in abyss-stack. This module keeps the
tool contract testable from the public repository while exposing a JSON-RPC
stdio surface that MCP clients can launch directly.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TextIO

from aoa_course_connector.calibration.connected_run import load_connected_calibration_status
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.query import freshness_report, graph_neighbors, query_index, render_answer_packet
from aoa_course_connector.readiness import connected_source_plan, live_preflight
from aoa_course_connector.refresh import refresh_query_cycle
from aoa_course_connector.sources import load_registry
from aoa_course_connector.status import connector_readiness, ingest_status
from aoa_course_connector.sync import load_sync_status


SERVER_NAME = "aoa-course-connector-mcp"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-11-25"
DEFAULT_RUN = "starter-fixture"
DEFAULT_CONNECTED_RUN = "connected-calibration"


def _query_schema(*, mode: bool = False) -> dict[str, object]:
    properties = {
        "query": _string_schema("Search query."),
        "run": _string_schema("Connector run id."),
        "limit": _integer_schema("Maximum result count.", 1),
    }
    if mode:
        properties["mode"] = {"type": "string", "enum": ["keyword", "semantic", "hybrid"], "description": "Query mode."}
    return _object_schema(properties, required=["query"])


def _run_schema() -> dict[str, object]:
    return _object_schema({"run": _string_schema("Connector run id.")})


def _connector_readiness_schema() -> dict[str, object]:
    return _object_schema(
        {
            "runs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional run ids to audit.",
            },
            "platforms": {
                "type": "array",
                "items": {"type": "string", "enum": ["getcourse", "skillspace", "stepik"]},
                "description": "Optional connected platforms to audit.",
            },
            "connected_run": _string_schema("Connected calibration run id to inspect."),
            "stepik_token_env": _string_schema("Environment variable that holds the Stepik token."),
            "state_file": _string_schema("Optional browser storage-state file."),
            "expect_origin": _string_schema("Expected browser auth origin or host fragment."),
            "include_disabled": {"type": "boolean", "description": "Include disabled sources in readiness checks."},
            "query": _string_schema("Optional course-specific smoke query for connected planning."),
        }
    )


def _live_preflight_schema() -> dict[str, object]:
    return _object_schema(
        {
            "platforms": {
                "type": "array",
                "items": {"type": "string", "enum": ["getcourse", "skillspace", "stepik"]},
                "description": "Optional connected platforms to inspect.",
            },
            "stepik_token_env": _string_schema("Environment variable that holds the Stepik token."),
            "state_file": _string_schema("Optional browser storage-state file."),
            "expect_origin": _string_schema("Expected browser auth origin or host fragment."),
            "include_disabled": {"type": "boolean", "description": "Include disabled sources in readiness checks."},
        }
    )


def _connected_source_plan_schema() -> dict[str, object]:
    return _object_schema(
        {
            "platforms": {
                "type": "array",
                "items": {"type": "string", "enum": ["getcourse", "skillspace", "stepik"]},
                "description": "Optional connected platforms to plan.",
            },
            "stepik_token_env": _string_schema("Environment variable that holds the Stepik token."),
            "state_file": _string_schema("Optional browser storage-state file."),
            "expect_origin": _string_schema("Expected browser auth origin or host fragment."),
            "include_disabled": {"type": "boolean", "description": "Include disabled sources in readiness checks."},
            "query": _string_schema("Optional course-specific smoke query."),
            "max_lessons": _integer_schema("Maximum lessons for browser live smoke/sync commands.", 1),
            "max_pages": _integer_schema("Maximum catalog pages for browser live smoke commands.", 1),
            "max_sources": _integer_schema("Maximum discovered sources for browser live smoke commands.", 1),
            "link_pattern": _string_schema("Optional browser lesson/course link glob for connected browser live commands."),
            "calibration_run": _string_schema("Calibration run id for the handoff packet."),
            "live_scope": {"type": "string", "enum": ["bounded", "full-course"], "description": "Use bounded smoke/sync commands by default, or explicit full-course commands."},
            "include_step_sources": {"type": "boolean", "description": "Add Stepik step-source enrichment flags to planned commands."},
        }
    )


def _refresh_plan_schema() -> dict[str, object]:
    properties = {
        "query": _string_schema("Search query to refresh from evidence."),
        "run": _string_schema("Connector run id."),
        "limit": _integer_schema("Maximum result count.", 1),
        "mode": {"type": "string", "enum": ["keyword", "semantic", "hybrid"], "description": "Query mode."},
        "source_id": _string_schema("Optional source id to select from the answer packet."),
        "stepik_token_env": _string_schema("Environment variable that holds the Stepik token."),
        "state_file": _string_schema("Optional browser storage-state file for readiness planning."),
    }
    return _object_schema(properties, required=["query"])


def _object_schema(properties: dict[str, object], *, required: Iterable[str] = ()) -> dict[str, object]:
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def _string_schema(description: str) -> dict[str, str]:
    return {"type": "string", "description": description}


def _integer_schema(description: str, minimum: int) -> dict[str, Any]:
    return {"type": "integer", "minimum": minimum, "description": description}


TOOLS = [
    {"name": "list_sources", "description": "List configured course sources.", "inputSchema": _object_schema({})},
    {"name": "connector_readiness", "description": "Inspect install, storage, source, run, connected-run, and MCP readiness without touching the network.", "inputSchema": _connector_readiness_schema()},
    {"name": "ingest_status", "description": "Inspect local ingest run status.", "inputSchema": _run_schema()},
    {"name": "sync_status", "description": "Inspect source sync checkpoints.", "inputSchema": _object_schema({"sync_run": _string_schema("Sync run id."), "platform": _string_schema("Optional platform filter.")})},
    {"name": "live_preflight", "description": "Inspect connected-source readiness without touching the network or printing secrets.", "inputSchema": _live_preflight_schema()},
    {"name": "connected_source_plan", "description": "Plan connected-source preflight, sync, smoke, connected-run, and calibration commands without touching the network.", "inputSchema": _connected_source_plan_schema()},
    {"name": "connected_run_status", "description": "Inspect a connected calibration run receipt without touching the network.", "inputSchema": _run_schema()},
    {"name": "refresh_plan", "description": "Plan a query refresh cycle from current evidence without touching the network.", "inputSchema": _refresh_plan_schema()},
    {"name": "search", "description": "Search indexed course knowledge.", "inputSchema": _query_schema(mode=True)},
    {"name": "semantic_search", "description": "Search the local semantic/vector index.", "inputSchema": _query_schema()},
    {"name": "hybrid_search", "description": "Search with keyword and semantic scores combined.", "inputSchema": _query_schema()},
    {"name": "lesson_context", "description": "Return source-backed lesson context for a query.", "inputSchema": _query_schema(mode=True)},
    {"name": "graph_neighbors", "description": "Traverse course graph neighborhoods.", "inputSchema": _object_schema({"node_id": _string_schema("Graph node id."), "run": _string_schema("Connector run id."), "limit": _integer_schema("Maximum neighbor count.", 1)})},
    {"name": "freshness_report", "description": "Report result freshness states.", "inputSchema": _run_schema()},
    {"name": "evidence_report", "description": "Report source evidence, freshness, and authority for query results.", "inputSchema": _query_schema(mode=True)},
]
TOOL_NAMES = {str(tool["name"]) for tool in TOOLS}


def tools_manifest() -> dict[str, object]:
    return {"schema": "aoa_course_mcp_tools_v1", "server": SERVER_NAME, "protocol_version": PROTOCOL_VERSION, "tools": TOOLS}


def call_tool(name: str, arguments: dict[str, object] | None = None) -> dict[str, object]:
    args = arguments or {}
    roots = StorageRoots.from_env(find_repo_root())
    run_id = str(args.get("run") or DEFAULT_RUN)
    if name == "list_sources":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "registry": load_registry(roots.data)}
    if name == "connector_readiness":
        return _call_connector_readiness(roots, args)
    if name == "ingest_status":
        return ingest_status(roots, run_id)
    if name == "sync_status":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "sync": load_sync_status(roots, sync_run_id=str(args.get("sync_run") or ""), platform=str(args.get("platform") or ""))}
    if name == "live_preflight":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "preflight": _call_live_preflight(roots, args)}
    if name == "connected_source_plan":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "plan": _call_connected_source_plan(roots, args)}
    if name == "connected_run_status":
        connected_run_id = str(args.get("run") or DEFAULT_CONNECTED_RUN)
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "connected_run": load_connected_calibration_status(roots, run_id=connected_run_id)}
    if name == "refresh_plan":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "refresh": _call_refresh_plan(roots, args)}
    if name == "search":
        return {
            "schema": "aoa_course_mcp_result_v1",
            "tool": name,
            "mode": str(args.get("mode") or "keyword"),
            "results": query_index(roots, str(args.get("query") or ""), run_id, int(args.get("limit") or 5), str(args.get("mode") or "keyword")),
        }
    if name == "semantic_search":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "mode": "semantic", "results": query_index(roots, str(args.get("query") or ""), run_id, int(args.get("limit") or 5), "semantic")}
    if name == "hybrid_search":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "mode": "hybrid", "results": query_index(roots, str(args.get("query") or ""), run_id, int(args.get("limit") or 5), "hybrid")}
    if name == "lesson_context":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "answer_packet": render_answer_packet(roots, str(args.get("query") or ""), run_id, int(args.get("limit") or 5), str(args.get("mode") or "keyword"))}
    if name == "graph_neighbors":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "graph": graph_neighbors(roots, str(args.get("node_id") or ""), run_id, int(args.get("limit") or 20))}
    if name == "freshness_report":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "freshness": freshness_report(roots, run_id)}
    if name == "evidence_report":
        packet = render_answer_packet(
            roots,
            str(args.get("query") or ""),
            run_id,
            int(args.get("limit") or 5),
            str(args.get("mode") or "keyword"),
        )
        return {
            "schema": "aoa_course_mcp_result_v1",
            "tool": name,
            "run_id": run_id,
            "query": packet.get("query"),
            "mode": packet.get("mode"),
            "result_count": packet.get("result_count"),
            "evidence_chain": packet.get("evidence_chain"),
            "freshness_report": packet.get("freshness_report"),
            "authority_report": packet.get("authority_report"),
            "refresh_report": packet.get("refresh_report"),
            "result_refs": _evidence_result_refs(packet),
        }
    raise ValueError(f"unknown MCP tool: {name}")


def _evidence_result_refs(packet: dict[str, object]) -> list[dict[str, object]]:
    results = packet.get("results") if isinstance(packet.get("results"), list) else []
    refs: list[dict[str, object]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        refs.append(
            {
                "doc_id": result.get("doc_id"),
                "source_id": result.get("source_id"),
                "source_url": result.get("source_url"),
                "evidence_id": result.get("evidence_id"),
                "path": result.get("path"),
                "fetched_at": result.get("fetched_at"),
                "freshness_state": result.get("freshness_state"),
                "authority_tier": result.get("authority_tier"),
                "score": result.get("score"),
                "rank_score": result.get("rank_score"),
                "refresh_hint": result.get("refresh_hint"),
            }
        )
    return refs


def _call_live_preflight(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    platforms = args.get("platforms")
    if platforms is None:
        platform_list = None
    elif isinstance(platforms, list) and all(isinstance(item, str) for item in platforms):
        platform_list = platforms
    else:
        raise ValueError("live_preflight platforms must be an array of strings")
    state_file = args.get("state_file")
    if state_file is not None and not isinstance(state_file, str):
        raise ValueError("live_preflight state_file must be a string")
    return live_preflight(
        roots,
        platforms=platform_list,
        stepik_token_env=str(args.get("stepik_token_env") or "STEPIK_API_TOKEN"),
        browser_state_file=Path(state_file) if state_file else None,
        expect_origin_contains=str(args.get("expect_origin") or "") or None,
        include_disabled=bool(args.get("include_disabled", False)),
    )


def _call_connector_readiness(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    run_values = args.get("runs")
    if run_values is None:
        runs = None
    elif isinstance(run_values, list) and all(isinstance(item, str) for item in run_values):
        runs = run_values
    else:
        raise ValueError("connector_readiness runs must be an array of strings")
    platforms = _platform_arg(args.get("platforms"), tool_name="connector_readiness")
    state_file = args.get("state_file")
    if state_file is not None and not isinstance(state_file, str):
        raise ValueError("connector_readiness state_file must be a string")
    return connector_readiness(
        find_repo_root(),
        roots,
        runs=runs,
        platforms=platforms,
        connected_run=str(args.get("connected_run") or DEFAULT_CONNECTED_RUN),
        stepik_token_env=str(args.get("stepik_token_env") or "STEPIK_API_TOKEN"),
        browser_state_file=Path(state_file) if state_file else None,
        expect_origin_contains=str(args.get("expect_origin") or "") or None,
        include_disabled=bool(args.get("include_disabled", False)),
        query=str(args.get("query") or "") or None,
        mcp_tool_names=TOOL_NAMES,
    )


def _call_connected_source_plan(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    platforms = _platform_arg(args.get("platforms"), tool_name="connected_source_plan")
    state_file = args.get("state_file")
    if state_file is not None and not isinstance(state_file, str):
        raise ValueError("connected_source_plan state_file must be a string")
    return connected_source_plan(
        roots,
        platforms=platforms,
        stepik_token_env=str(args.get("stepik_token_env") or "STEPIK_API_TOKEN"),
        browser_state_file=Path(state_file) if state_file else None,
        expect_origin_contains=str(args.get("expect_origin") or "") or None,
        include_disabled=bool(args.get("include_disabled", False)),
        query=str(args.get("query") or "") or None,
        max_lessons=int(args.get("max_lessons") or 50),
        max_pages=int(args.get("max_pages") or 5),
        max_sources=int(args.get("max_sources") or 50),
        link_pattern=str(args.get("link_pattern") or "") or None,
        calibration_run=str(args.get("calibration_run") or "connected-live-calibration"),
        live_scope=str(args.get("live_scope") or "bounded"),
        include_step_sources=bool(args.get("include_step_sources", False)),
    )


def _call_refresh_plan(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    state_file = args.get("state_file")
    if state_file is not None and not isinstance(state_file, str):
        raise ValueError("refresh_plan state_file must be a string")
    return refresh_query_cycle(
        roots,
        str(args.get("query") or ""),
        run_id=str(args.get("run") or "starter-fixture"),
        limit=int(args.get("limit") or 5),
        mode=str(args.get("mode") or "keyword"),
        strategy="plan",
        execute=False,
        source_id=str(args.get("source_id") or "") or None,
        state_file=Path(state_file) if state_file else None,
        stepik_token_env=str(args.get("stepik_token_env") or "STEPIK_API_TOKEN"),
    )


def _platform_arg(value: object, *, tool_name: str) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError(f"{tool_name} platforms must be an array of strings")


def handle_jsonrpc_message(message: object) -> dict[str, object] | list[dict[str, object]] | None:
    if isinstance(message, list):
        responses = [response for item in message if (response := _handle_jsonrpc_request(item)) is not None]
        return responses or None
    return _handle_jsonrpc_request(message)


def run_stdio(input_stream: TextIO = sys.stdin, output_stream: TextIO = sys.stdout) -> int:
    for line in input_stream:
        if not line.strip():
            continue
        response: dict[str, object] | list[dict[str, object]] | None
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _error_response(None, -32700, f"parse error: {exc}")
        else:
            if _looks_like_jsonrpc(request):
                response = handle_jsonrpc_message(request)
            else:
                response = _handle_legacy_line_request(request)
        if response is not None:
            output_stream.write(json.dumps(response, sort_keys=True) + "\n")
            output_stream.flush()
    return 0


def main() -> int:
    if sys.stdin.isatty():
        print(json.dumps(tools_manifest(), indent=2, sort_keys=True))
        return 0
    return run_stdio()


def _handle_jsonrpc_request(message: object) -> dict[str, object] | None:
    if not isinstance(message, dict):
        return _error_response(None, -32600, "invalid request")
    request_id = message.get("id")
    method = message.get("method")
    if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
        return _error_response(request_id, -32600, "invalid request")
    if request_id is None and method.startswith("notifications/"):
        return None
    if method == "initialize":
        return _success_response(request_id, _initialize_result(message.get("params")))
    if method == "ping":
        return _success_response(request_id, {})
    if method == "tools/list":
        return _success_response(request_id, {"tools": TOOLS})
    if method == "tools/call":
        return _handle_tools_call(request_id, message.get("params"))
    return _error_response(request_id, -32601, f"method not found: {method}")


def _handle_tools_call(request_id: object, params: object) -> dict[str, object]:
    if not isinstance(params, dict):
        return _error_response(request_id, -32602, "tools/call params must be an object")
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if not isinstance(name, str) or name not in TOOL_NAMES:
        return _error_response(request_id, -32602, f"unknown tool: {name}")
    if not isinstance(arguments, dict):
        return _error_response(request_id, -32602, "tool arguments must be an object")
    try:
        result = call_tool(name, arguments)
    except Exception as exc:  # pragma: no cover - tool safety net.
        return _success_response(request_id, _tool_error(str(exc)))
    return _success_response(request_id, _tool_success(result))


def _handle_legacy_line_request(request: object) -> dict[str, object]:
    if not isinstance(request, dict):
        return {"status": "error", "error": "request must be a JSON object"}
    name = request.get("tool") or request.get("name")
    arguments = request.get("arguments") or {}
    if not isinstance(arguments, dict):
        return {"status": "error", "error": "arguments must be a JSON object"}
    try:
        result = call_tool(str(name), arguments)
        return {"status": "ok", "result": result}
    except Exception as exc:  # pragma: no cover - server safety net
        return {"status": "error", "error": str(exc)}


def _initialize_result(params: object) -> dict[str, object]:
    requested = params.get("protocolVersion") if isinstance(params, dict) else None
    negotiated = str(requested) if requested == PROTOCOL_VERSION else PROTOCOL_VERSION
    return {
        "protocolVersion": negotiated,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "instructions": "Search authorized local course indexes and return source-backed evidence packets.",
    }


def _tool_success(result: dict[str, object]) -> dict[str, object]:
    return {
        "content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}],
        "structuredContent": result,
        "isError": False,
    }


def _tool_error(error: str) -> dict[str, object]:
    return {
        "content": [{"type": "text", "text": error}],
        "structuredContent": {"schema": "aoa_course_mcp_error_v1", "error": error},
        "isError": True,
    }


def _success_response(request_id: object, result: dict[str, object]) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: object, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _looks_like_jsonrpc(request: object) -> bool:
    if isinstance(request, dict):
        return request.get("jsonrpc") == "2.0" or "method" in request
    if isinstance(request, list):
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
