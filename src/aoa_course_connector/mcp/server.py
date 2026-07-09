"""Dependency-free MCP stdio server and local tool dispatcher.

The full runtime registration belongs in abyss-stack. This module keeps the
tool contract testable from the public repository while exposing a JSON-RPC
stdio surface that MCP clients can launch directly.
"""

from __future__ import annotations

import json
import shlex
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TextIO

from aoa_course_connector.adapters.browser import audit_browser_snapshot_file
from aoa_course_connector.connection_profile import connection_profile_run_plan, connection_profile_status, inspect_connection_profile, load_connection_profile
from aoa_course_connector.calibration.connected_run import (
    load_connected_calibration_status,
    query_connected_calibration,
    query_connected_calibration_matrix,
    run_connected_calibration,
)
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.index import HTTP_JSON_PROVIDER, LOCAL_HASHING_PROVIDER
from aoa_course_connector.query import freshness_report, graph_neighbors, query_index, render_answer_packet, render_lesson_context_packet
from aoa_course_connector.readiness import connected_source_plan, live_preflight, semantic_provider_preflight
from aoa_course_connector.refresh import refresh_query_cycle
from aoa_course_connector.sources import load_registry
from aoa_course_connector.stepik_options import (
    DEFAULT_MAX_STEP_SOURCES,
    DEFAULT_STEP_SOURCE_TIMEOUT,
    normalize_max_step_sources,
    normalize_step_source_timeout,
)
from aoa_course_connector.status import connector_readiness, ingest_status, source_registry_catalog
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


def _lesson_context_schema() -> dict[str, object]:
    properties = {
        "query": _string_schema("Search query."),
        "run": _string_schema("Connector run id."),
        "limit": _integer_schema("Maximum result count.", 1),
        "mode": {"type": "string", "enum": ["keyword", "semantic", "hybrid"], "description": "Query mode."},
        "graph_limit": _integer_schema("Maximum graph edge count per evidence lesson.", 1),
    }
    return _object_schema(properties, required=["query"])


def _run_schema() -> dict[str, object]:
    return _object_schema({"run": _string_schema("Connector run id.")})


def _list_sources_schema() -> dict[str, object]:
    return _object_schema(
        {
            "platforms": {
                "type": "array",
                "items": {"type": "string", "enum": ["getcourse", "skillspace", "stepik"]},
                "description": "Optional platforms to select from the registry.",
            },
            "source_ids": _source_ids_schema("Optional source ids to select from the registry."),
            "include_disabled": {"type": "boolean", "description": "Include disabled sources in the catalog."},
            "include_source_refs": {"type": "boolean", "description": "Include operator source refs in catalog sources. They are not secrets, but can be private runtime context."},
            "include_connected_runs": {"type": "boolean", "description": "Include latest query-ready connected-run entries for each selected source."},
            "connected_run_limit": _integer_schema("Maximum query-ready connected-run entries per source.", 1),
            "connected_receipt_limit": _integer_schema("Maximum connected-run receipts to scan.", 1),
        }
    )


def _source_answer_schema() -> dict[str, object]:
    return _object_schema(
        {
            "query": _string_schema("Course question to answer from the selected source's latest query-ready connected run."),
            "source_id": _string_schema("Optional source id to select exactly one configured source."),
            "platforms": {
                "type": "array",
                "items": {"type": "string", "enum": ["getcourse", "skillspace", "stepik"]},
                "description": "Optional platforms to narrow source selection.",
            },
            "kinds": {
                "type": "array",
                "items": {"type": "string", "enum": ["smoke", "sync"]},
                "description": "Optional connected-run entry kinds. Without this, sync entries are preferred when present.",
            },
            "include_disabled": {"type": "boolean", "description": "Include disabled sources while selecting the source."},
            "include_source_refs": {"type": "boolean", "description": "Include operator source refs in the returned packet. Defaults to false."},
            "limit": _integer_schema("Maximum result count.", 1),
            "mode": {"type": "string", "enum": ["keyword", "semantic", "hybrid"], "description": "Optional query mode override."},
            "graph_limit": _integer_schema("Maximum graph edge count per evidence lesson.", 1),
            "connected_run_limit": _integer_schema("Maximum query-ready connected-run entries to inspect for the selected source.", 1),
            "connected_receipt_limit": _integer_schema("Maximum connected-run receipts to scan.", 1),
        },
        required=["query"],
    )


def _sources_answer_schema() -> dict[str, object]:
    properties = dict(_source_answer_schema()["properties"])
    properties.pop("source_id", None)
    properties["source_ids"] = _source_ids_schema("Optional source ids to select from the registry.")
    properties["source_limit"] = _integer_schema("Maximum selected sources to answer from.", 1)
    return _object_schema(properties, required=["query"])


def _sources_answer_matrix_schema() -> dict[str, object]:
    properties = dict(_sources_answer_schema()["properties"])
    properties.pop("query", None)
    properties["queries"] = {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 1,
        "description": "Course questions to answer across the selected query-ready sources.",
    }
    properties["coverage_mode"] = {
        "type": "string",
        "enum": ["all-sources", "portfolio"],
        "description": "Use all-sources for strict source-scoped readiness, or portfolio when each query only needs source-backed evidence from at least one selected source.",
    }
    return _object_schema(properties, required=["queries"])


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
            "source_ids": _source_ids_schema("Optional source ids to select from the registry for connected planning."),
            "connected_run": _string_schema("Connected calibration run id to inspect."),
            "stepik_token_env": _string_schema("Environment variable that holds the Stepik token."),
            "state_file": _string_schema("Optional browser storage-state file."),
            "expect_origin": _string_schema("Expected browser auth origin or host fragment."),
            "include_disabled": {"type": "boolean", "description": "Include disabled sources in readiness checks."},
            "query": _string_schema("Optional course-specific smoke query for connected planning."),
            "max_lessons": _integer_schema("Maximum lessons for browser live smoke/sync commands.", 1),
            "max_pages": _integer_schema("Maximum catalog pages for browser live smoke commands.", 1),
            "max_sources": _integer_schema("Maximum discovered sources for browser live smoke commands.", 1),
            "link_pattern": _string_schema("Optional browser lesson/course link glob for connected browser live commands."),
            "live_scope": {"type": "string", "enum": ["bounded", "full-course"], "description": "Use bounded smoke/sync commands by default, or explicit full-course commands."},
            "include_step_sources": {"type": "boolean", "description": "Add Stepik step-source enrichment flags to planned commands."},
            "max_step_sources": _max_step_sources_schema("Maximum Stepik step-source requests when include_step_sources is true. Use 'all' for the full selected course."),
            "step_source_timeout": _number_schema("Per-step Stepik step-source request timeout seconds.", 0.1),
            "semantic_provider": {"type": "string", "enum": [LOCAL_HASHING_PROVIDER, HTTP_JSON_PROVIDER], "description": "Semantic index provider to preflight."},
            "dimensions": _integer_schema("Local hashing vector dimensions.", 8),
            "embedding_endpoint": _string_schema("Operator-configured http_json_v1 embedding endpoint."),
            "embedding_model": _string_schema("Embedding model name for http_json_v1."),
            "embedding_token_env": _string_schema("Environment variable that holds the embedding endpoint token."),
            "embedding_batch_size": _integer_schema("Embedding request batch size.", 1),
            "embedding_timeout_seconds": _number_schema("Embedding request timeout seconds.", 0.1),
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
            "source_ids": _source_ids_schema("Optional source ids to inspect from the registry."),
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
            "source_ids": _source_ids_schema("Optional source ids to select from the registry for this connected plan."),
            "stepik_token_env": _string_schema("Environment variable that holds the Stepik token."),
            "state_file": _string_schema("Optional browser storage-state file."),
            "expect_origin": _string_schema("Expected browser auth origin or host fragment."),
            "include_disabled": {"type": "boolean", "description": "Include disabled sources in readiness checks."},
            "query": _string_schema("Optional course-specific smoke query."),
            "max_lessons": _integer_schema("Maximum lessons for browser live smoke/sync commands.", 1),
            "max_pages": _integer_schema("Maximum catalog pages for browser live smoke commands.", 1),
            "max_sources": _integer_schema("Maximum discovered sources for browser live smoke commands.", 1),
            "link_pattern": _string_schema("Optional browser lesson/course link glob for connected browser live commands."),
            "calibration_run": _string_schema("Calibration run id for the plan packet."),
            "live_scope": {"type": "string", "enum": ["bounded", "full-course"], "description": "Use bounded smoke/sync commands by default, or explicit full-course commands."},
            "include_step_sources": {"type": "boolean", "description": "Add Stepik step-source enrichment flags to planned commands."},
            "max_step_sources": _max_step_sources_schema("Maximum Stepik step-source requests when include_step_sources is true. Use 'all' for the full selected course."),
            "step_source_timeout": _number_schema("Per-step Stepik step-source request timeout seconds.", 0.1),
        }
    )


def _connected_run_schema() -> dict[str, object]:
    return _object_schema(
        {
            "run": _string_schema("Connected calibration run id."),
            "mode": {"type": "string", "enum": ["fixture", "live"], "description": "Use fixture mode for no-network proof or live mode for gated connected sources."},
            "platforms": {
                "type": "array",
                "items": {"type": "string", "enum": ["getcourse", "skillspace", "stepik"]},
                "description": "Optional connected platforms to run.",
            },
            "source_ids": _source_ids_schema("Optional source ids to select from the registry for live mode."),
            "query": _string_schema("Optional course-specific smoke query."),
            "live_scope": {"type": "string", "enum": ["bounded", "full-course"], "description": "Use bounded smoke/sync commands by default, or explicit full-course commands."},
            "include_step_sources": {"type": "boolean", "description": "Add Stepik step-source enrichment flags to live Stepik runs."},
            "max_step_sources": _max_step_sources_schema("Maximum Stepik step-source requests when include_step_sources is true. Use 'all' for the full selected course."),
            "step_source_timeout": _number_schema("Per-step Stepik step-source request timeout seconds.", 0.1),
            "allow_network": {"type": "boolean", "description": "Required before live mode can touch connected sources."},
            "stepik_token_env": _string_schema("Environment variable that holds the Stepik token."),
            "state_file": _string_schema("Optional browser storage-state file."),
            "expect_origin": _string_schema("Expected browser auth origin or host fragment."),
            "max_lessons": _integer_schema("Maximum lessons for browser live smoke/sync commands.", 1),
            "max_pages": _integer_schema("Maximum catalog pages for browser live smoke commands.", 1),
            "max_sources": _integer_schema("Maximum discovered sources for browser live smoke commands.", 1),
            "link_pattern": _string_schema("Optional browser lesson/course link glob for connected browser live commands."),
            "source_limit": _integer_schema("Maximum selected sources to execute.", 1),
        }
    )


def _connected_run_query_schema() -> dict[str, object]:
    return _object_schema(
        {
            "run": _string_schema("Connected calibration run id."),
            "query": _string_schema("Optional query override. Required for sync entries that did not save a smoke query."),
            "platforms": {
                "type": "array",
                "items": {"type": "string", "enum": ["getcourse", "skillspace", "stepik"]},
                "description": "Optional platforms to select from the connected-run query plan.",
            },
            "source_ids": _source_ids_schema("Optional source ids to select from the connected-run query plan."),
            "kinds": {
                "type": "array",
                "items": {"type": "string", "enum": ["smoke", "sync"]},
                "description": "Optional query-plan entry kinds to select.",
            },
            "limit": _integer_schema("Maximum result count per selected entry.", 1),
            "mode": {"type": "string", "enum": ["keyword", "semantic", "hybrid"], "description": "Optional query mode override."},
            "graph_limit": _integer_schema("Maximum graph edge count per evidence lesson.", 1),
            "entry_limit": _integer_schema("Maximum query-plan entries to execute.", 1),
        }
    )


def _connected_run_query_matrix_schema() -> dict[str, object]:
    properties = dict(_connected_run_query_schema()["properties"])
    properties.pop("query", None)
    properties["queries"] = {
        "type": "array",
        "items": {"type": "string"},
        "description": "Course-specific questions to execute against each selected query-ready entry.",
    }
    return _object_schema(properties, required=["queries"])


def _connection_profile_inspect_schema() -> dict[str, object]:
    return _object_schema({"profile_path": _string_schema("Local runtime connection profile JSON path.")}, required=["profile_path"])


def _connection_profile_status_schema() -> dict[str, object]:
    return _object_schema({"profile_path": _string_schema("Local runtime connection profile JSON path.")}, required=["profile_path"])


def _connection_profile_run_plan_schema() -> dict[str, object]:
    return _object_schema(
        {
            "profile_path": _string_schema("Local runtime connection profile JSON path."),
            "platform": {"type": "string", "enum": ["getcourse", "skillspace", "stepik"], "description": "Optional platform to select one executable profile run plan."},
            "source_ids": _source_ids_schema("Optional source ids to select one executable profile run plan."),
        },
        required=["profile_path"],
    )


def _semantic_provider_preflight_schema() -> dict[str, object]:
    return _object_schema(
        {
            "run": _string_schema("Connector run id."),
            "provider": {"type": "string", "enum": [LOCAL_HASHING_PROVIDER, HTTP_JSON_PROVIDER], "description": "Semantic index provider to preflight."},
            "dimensions": _integer_schema("Local hashing vector dimensions.", 8),
            "embedding_endpoint": _string_schema("Operator-configured http_json_v1 embedding endpoint."),
            "embedding_model": _string_schema("Embedding model name for http_json_v1."),
            "embedding_token_env": _string_schema("Environment variable that holds the embedding endpoint token."),
            "embedding_batch_size": _integer_schema("Embedding request batch size.", 1),
            "embedding_timeout_seconds": _number_schema("Embedding request timeout seconds.", 0.1),
        }
    )


def _browser_snapshot_audit_schema() -> dict[str, object]:
    return _object_schema(
        {
            "snapshot_path": _string_schema("Local browser snapshot JSON path."),
            "platform": {"type": "string", "enum": ["getcourse", "skillspace"], "description": "Browser-session platform."},
            "max_sources": _integer_schema("Maximum course sources to inspect.", 1),
            "max_lessons": _integer_schema("Maximum lesson links to inspect.", 1),
            "link_pattern": _string_schema("Optional browser lesson/course link glob."),
        },
        required=["snapshot_path"],
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


def _number_schema(description: str, minimum: float) -> dict[str, Any]:
    return {"type": "number", "minimum": minimum, "description": description}


def _max_step_sources_schema(description: str) -> dict[str, Any]:
    return {
        "oneOf": [
            {"type": "integer", "minimum": 0},
            {"type": "string", "enum": ["all"]},
        ],
        "description": description,
    }


def _source_ids_schema(description: str) -> dict[str, object]:
    return {"type": "array", "items": {"type": "string"}, "description": description}


TOOLS = [
    {"name": "list_sources", "description": "List configured course sources as a read-only catalog with counts, filters, registry path, and privacy flags.", "inputSchema": _list_sources_schema()},
    {"name": "source_answer", "description": "Select one configured source and answer a course question from its latest query-ready connected run without touching the network.", "inputSchema": _source_answer_schema()},
    {"name": "sources_answer", "description": "Answer one course question across selected query-ready sources and return per-source evidence packets without touching the network.", "inputSchema": _sources_answer_schema()},
    {"name": "sources_answer_matrix", "description": "Answer several course questions across selected query-ready sources and return aggregate source-scoped retrieval quality without touching the network.", "inputSchema": _sources_answer_matrix_schema()},
    {"name": "connector_readiness", "description": "Inspect install, storage, source, run, connected-run, and MCP readiness without touching the network.", "inputSchema": _connector_readiness_schema()},
    {"name": "ingest_status", "description": "Inspect local ingest run status.", "inputSchema": _run_schema()},
    {"name": "sync_status", "description": "Inspect source sync checkpoints.", "inputSchema": _object_schema({"sync_run": _string_schema("Sync run id."), "platform": _string_schema("Optional platform filter.")})},
    {"name": "live_preflight", "description": "Inspect connected-source readiness without touching the network or printing secrets.", "inputSchema": _live_preflight_schema()},
    {"name": "connected_source_plan", "description": "Plan connected-source preflight, sync, smoke, connected-run, and calibration commands without touching the network.", "inputSchema": _connected_source_plan_schema()},
    {"name": "connection_profile_inspect", "description": "Inspect a local redacted aoa_course_connection_profile_v1 file and return aoa_course_connection_profile_inspection_v1 source/auth/semantic next commands with network_touched false and without mutation.", "inputSchema": _connection_profile_inspect_schema()},
    {"name": "connection_profile_status", "description": "Return compact aoa_course_connection_profile_status_v1 go/no-go readiness, including ready_for_connected_run, blockers, and network_touched false, for a local connection profile.", "inputSchema": _connection_profile_status_schema()},
    {"name": "connection_profile_run_plan", "description": "Return one selected aoa_course_connection_profile_run_plan_v1 executable connected-run plan from a local connection profile without touching the network.", "inputSchema": _connection_profile_run_plan_schema()},
    {"name": "semantic_provider_preflight", "description": "Inspect semantic provider build readiness without touching the network or printing token values.", "inputSchema": _semantic_provider_preflight_schema()},
    {"name": "browser_snapshot_audit", "description": "Inspect a local GetCourse/Skillspace browser snapshot for discovery, crawl, transcript, caption, comment, progress, pagination, and repair readiness without printing raw HTML.", "inputSchema": _browser_snapshot_audit_schema()},
    {"name": "connected_run", "description": "Execute the connected-source calibration route. Fixture mode is network-free; live mode requires explicit allow_network.", "inputSchema": _connected_run_schema()},
    {"name": "connected_run_status", "description": "Inspect a connected calibration run receipt without touching the network.", "inputSchema": _run_schema()},
    {"name": "connected_run_query", "description": "Read a connected-run receipt and execute source-backed answer, lesson_context, and evidence packets for query-ready entries without touching the network.", "inputSchema": _connected_run_query_schema()},
    {"name": "connected_run_query_matrix", "description": "Execute several course questions against a connected-run query plan without touching the network and return aggregate retrieval quality.", "inputSchema": _connected_run_query_matrix_schema()},
    {"name": "refresh_plan", "description": "Plan a query refresh cycle from current evidence without touching the network.", "inputSchema": _refresh_plan_schema()},
    {"name": "search", "description": "Search indexed course knowledge.", "inputSchema": _query_schema(mode=True)},
    {"name": "semantic_search", "description": "Search the local semantic/vector index.", "inputSchema": _query_schema()},
    {"name": "hybrid_search", "description": "Search with keyword and semantic scores combined.", "inputSchema": _query_schema()},
    {"name": "answer", "description": "Return a source-backed aoa_course_answer_packet_v1 with evidence, freshness, authority, refresh, and quality reports.", "inputSchema": _query_schema(mode=True)},
    {"name": "lesson_context", "description": "Return source-backed lesson context and nearby course graph context for a query.", "inputSchema": _lesson_context_schema()},
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
        registry = load_registry(roots.data)
        include_source_refs = _bool_arg(args.get("include_source_refs"), default=True, tool_name="list_sources", field_name="include_source_refs")
        include_connected_runs = _bool_arg(args.get("include_connected_runs"), default=True, tool_name="list_sources", field_name="include_connected_runs")
        catalog = source_registry_catalog(
            roots,
            registry,
            include_disabled=_bool_arg(args.get("include_disabled"), default=False, tool_name="list_sources", field_name="include_disabled"),
            platforms=_platform_arg(args.get("platforms"), tool_name="list_sources"),
            source_ids=_string_array_arg(args.get("source_ids"), tool_name="list_sources", field_name="source_ids"),
            include_source_refs=include_source_refs,
            include_connected_runs=include_connected_runs,
            connected_run_limit=_positive_int_arg(args.get("connected_run_limit"), default=3, tool_name="list_sources", field_name="connected_run_limit"),
            connected_receipt_limit=_positive_int_arg(args.get("connected_receipt_limit"), default=50, tool_name="list_sources", field_name="connected_receipt_limit"),
        )
        registry_view = registry if include_source_refs else {"schema": registry.get("schema"), "sources": catalog.get("sources", [])}
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "catalog": catalog, "registry": registry_view}
    if name == "source_answer":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "source_answer": _call_source_answer(roots, args)}
    if name == "sources_answer":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "sources_answer": _call_sources_answer(roots, args)}
    if name == "sources_answer_matrix":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "sources_answer_matrix": _call_sources_answer_matrix(roots, args)}
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
    if name == "connection_profile_inspect":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "inspection": _call_connection_profile_inspect(roots, args)}
    if name == "connection_profile_status":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "status": _call_connection_profile_status(roots, args)}
    if name == "connection_profile_run_plan":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "run_plan": _call_connection_profile_run_plan(roots, args)}
    if name == "semantic_provider_preflight":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "preflight": _call_semantic_provider_preflight(roots, args)}
    if name == "browser_snapshot_audit":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "audit": _call_browser_snapshot_audit(args)}
    if name == "connected_run":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "connected_run": _call_connected_run(roots, args)}
    if name == "connected_run_status":
        connected_run_id = str(args.get("run") or DEFAULT_CONNECTED_RUN)
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "connected_run": load_connected_calibration_status(roots, run_id=connected_run_id)}
    if name == "connected_run_query":
        connected_run_id = str(args.get("run") or DEFAULT_CONNECTED_RUN)
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "query_packet": _call_connected_run_query(roots, {**args, "run": connected_run_id})}
    if name == "connected_run_query_matrix":
        connected_run_id = str(args.get("run") or DEFAULT_CONNECTED_RUN)
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "query_matrix": _call_connected_run_query_matrix(roots, {**args, "run": connected_run_id})}
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
    if name == "answer":
        return {
            "schema": "aoa_course_mcp_result_v1",
            "tool": name,
            "answer_packet": render_answer_packet(
                roots,
                str(args.get("query") or ""),
                run_id,
                int(args.get("limit") or 5),
                str(args.get("mode") or "keyword"),
            ),
        }
    if name == "lesson_context":
        packet = render_lesson_context_packet(roots, str(args.get("query") or ""), run_id, int(args.get("limit") or 5), str(args.get("mode") or "keyword"), int(args.get("graph_limit") or 12))
        return {
            "schema": "aoa_course_mcp_result_v1",
            "tool": name,
            "lesson_context": packet,
            "answer_packet": packet["answer_packet"],
            "graph_context": packet["graph_context"],
        }
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
            "quality": packet.get("quality"),
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
            _compact_dict(
                {
                    "doc_id": result.get("doc_id"),
                    "kind": result.get("kind"),
                    "source_id": result.get("source_id"),
                    "source_url": result.get("source_url"),
                    "evidence_id": result.get("evidence_id"),
                    "snippet": result.get("snippet"),
                    "platform": result.get("platform"),
                    "path": result.get("path"),
                    "lesson_id": result.get("lesson_id"),
                    "lesson_title": result.get("lesson_title"),
                    "fetched_at": result.get("fetched_at"),
                    "freshness_state": result.get("freshness_state"),
                    "authority_tier": result.get("authority_tier"),
                    "authority_label": result.get("authority_label"),
                    "source_authority": result.get("source_authority"),
                    "score": result.get("score"),
                    "rank_score": result.get("rank_score"),
                    "rank_features": result.get("rank_features"),
                    "refresh_hint": result.get("refresh_hint"),
                }
            )
        )
    return refs


def _compact_dict(value: dict[str, object]) -> dict[str, object]:
    return {key: item for key, item in value.items() if item is not None}


def _call_source_answer(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    query_value = args.get("query")
    if not isinstance(query_value, str) or not query_value.strip():
        raise ValueError("source_answer query must be a non-empty string")
    source_id_value = args.get("source_id")
    if source_id_value is not None and not isinstance(source_id_value, str):
        raise ValueError("source_answer source_id must be a string")
    source_id = source_id_value.strip() if isinstance(source_id_value, str) else ""
    mode_value = args.get("mode")
    if mode_value is not None and not isinstance(mode_value, str):
        raise ValueError("source_answer mode must be a string")
    include_source_refs = _bool_arg(args.get("include_source_refs"), default=False, tool_name="source_answer", field_name="include_source_refs")
    source_ids = [source_id] if source_id else None
    platforms = _platform_arg(args.get("platforms"), tool_name="source_answer")
    kinds = _string_array_arg(args.get("kinds"), tool_name="source_answer", field_name="kinds")
    catalog = source_registry_catalog(
        roots,
        load_registry(roots.data),
        include_disabled=_bool_arg(args.get("include_disabled"), default=False, tool_name="source_answer", field_name="include_disabled"),
        platforms=platforms,
        source_ids=source_ids,
        include_source_refs=include_source_refs,
        include_connected_runs=True,
        connected_run_limit=_positive_int_arg(args.get("connected_run_limit"), default=5, tool_name="source_answer", field_name="connected_run_limit"),
        connected_receipt_limit=_positive_int_arg(args.get("connected_receipt_limit"), default=50, tool_name="source_answer", field_name="connected_receipt_limit"),
    )
    sources = catalog.get("sources") if isinstance(catalog.get("sources"), list) else []
    if catalog.get("missing_source_ids"):
        return _source_answer_blocked(catalog, str(query_value), "missing_source", "selected source id is not present in the local registry")
    if not sources:
        return _source_answer_blocked(catalog, str(query_value), "no_matching_source", "no configured source matched the requested source scope", status="missing")
    if len(sources) != 1:
        return _source_answer_blocked(catalog, str(query_value), "ambiguous_source", "pass source_id or a narrower platform scope so exactly one source is selected")
    source = sources[0] if isinstance(sources[0], dict) else {}
    entries = _source_answer_entries(source, kinds)
    if not entries:
        return _source_answer_blocked(catalog, str(query_value), "no_query_ready_connected_run", "selected source has no local query-ready connected run yet")
    selected_entry = entries[0]
    connected_run_id = str(selected_entry.get("connected_run_id") or selected_entry.get("sync_run_id") or selected_entry.get("run_id") or "")
    if not connected_run_id:
        return _source_answer_blocked(catalog, str(query_value), "missing_query_run_id", "selected query-ready entry has no connected_run_id or run_id")
    external_provider_failure = _external_semantic_provider_failure(source, selected_entry, mode_value)
    if external_provider_failure:
        return _source_answer_blocked(
            catalog,
            str(query_value),
            "external_semantic_provider_requires_network",
            str(external_provider_failure["detail"]),
        )
    query_packet = _query_source_entry(
        roots,
        source,
        selected_entry,
        query=str(query_value),
        mode=mode_value,
        limit=int(args.get("limit") or 5),
        graph_limit=int(args.get("graph_limit") or 12),
    )
    if not include_source_refs:
        query_packet = _drop_source_refs(query_packet)
    responses = query_packet.get("responses") if isinstance(query_packet.get("responses"), list) else []
    response = responses[0] if responses and isinstance(responses[0], dict) else {}
    answer_packet = response.get("answer_packet") if isinstance(response.get("answer_packet"), dict) else {}
    lesson_context = response.get("lesson_context") if isinstance(response.get("lesson_context"), dict) else {}
    evidence_report = response.get("evidence_report") if isinstance(response.get("evidence_report"), dict) else {}
    status = "ok" if query_packet.get("status") == "ok" and response else str(query_packet.get("status") or "partial")
    return {
        "schema": "aoa_course_source_answer_packet_v1",
        "status": status,
        "network_touched": False,
        "read_only": True,
        "query": str(query_value),
        "source_refs_included": include_source_refs,
        "selected_source": source,
        "selected_entry": selected_entry,
        "connected_run_id": connected_run_id,
        "candidate_source_count": len(sources),
        "candidate_run_count": len(entries),
        "catalog_summary": _source_answer_catalog_summary(catalog),
        "query_packet": query_packet,
        "answer_packet": answer_packet,
        "lesson_context": lesson_context,
        "evidence_report": evidence_report,
        "quality": query_packet.get("quality", {}),
        "next_commands": _source_answer_next_commands(source, selected_entry, str(query_value), mode_value),
    }


def _call_sources_answer(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    query_value = args.get("query")
    if not isinstance(query_value, str) or not query_value.strip():
        raise ValueError("sources_answer query must be a non-empty string")
    mode_value = args.get("mode")
    if mode_value is not None and not isinstance(mode_value, str):
        raise ValueError("sources_answer mode must be a string")
    include_source_refs = _bool_arg(args.get("include_source_refs"), default=False, tool_name="sources_answer", field_name="include_source_refs")
    platforms = _platform_arg(args.get("platforms"), tool_name="sources_answer")
    source_ids = _string_array_arg(args.get("source_ids"), tool_name="sources_answer", field_name="source_ids")
    kinds = _string_array_arg(args.get("kinds"), tool_name="sources_answer", field_name="kinds")
    source_limit = _positive_int_arg(args.get("source_limit"), default=10, tool_name="sources_answer", field_name="source_limit")
    catalog = source_registry_catalog(
        roots,
        load_registry(roots.data),
        include_disabled=_bool_arg(args.get("include_disabled"), default=False, tool_name="sources_answer", field_name="include_disabled"),
        platforms=platforms,
        source_ids=source_ids,
        include_source_refs=include_source_refs,
        include_connected_runs=True,
        connected_run_limit=_positive_int_arg(args.get("connected_run_limit"), default=5, tool_name="sources_answer", field_name="connected_run_limit"),
        connected_receipt_limit=_positive_int_arg(args.get("connected_receipt_limit"), default=50, tool_name="sources_answer", field_name="connected_receipt_limit"),
    )
    sources = catalog.get("sources") if isinstance(catalog.get("sources"), list) else []
    selected_sources = [source for source in sources[:source_limit] if isinstance(source, dict)]
    blocked_sources: list[dict[str, object]] = []
    for missing_id in catalog.get("missing_source_ids", []) if isinstance(catalog.get("missing_source_ids"), list) else []:
        blocked_sources.append({"source_id": missing_id, "reason": "missing_source", "detail": "selected source id is not present in the local registry"})
    if len(sources) > source_limit:
        for source in sources[source_limit:]:
            if isinstance(source, dict):
                blocked_sources.append(_source_blocked(source, "source_limit", "source was not queried because source_limit was reached"))
    responses: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for source in selected_sources:
        entries = _source_answer_entries(source, kinds)
        if not entries:
            blocked_sources.append(_source_blocked(source, "no_query_ready_connected_run", "selected source has no local query-ready connected run yet"))
            continue
        selected_entry = entries[0]
        connected_run_id = str(selected_entry.get("connected_run_id") or selected_entry.get("sync_run_id") or selected_entry.get("run_id") or "")
        if not connected_run_id:
            blocked_sources.append(_source_blocked(source, "missing_query_run_id", "selected query-ready entry has no connected_run_id or run_id"))
            continue
        external_provider_failure = _external_semantic_provider_failure(source, selected_entry, mode_value)
        if external_provider_failure:
            blocked_sources.append(_source_blocked(
                source,
                "external_semantic_provider_requires_network",
                str(external_provider_failure["detail"]),
                selected_entry=selected_entry,
                query_packet={"failures": [external_provider_failure]},
            ))
            continue
        try:
            query_packet = _query_source_entry(
                roots,
                source,
                selected_entry,
                query=str(query_value),
                mode=mode_value,
                limit=int(args.get("limit") or 5),
                graph_limit=int(args.get("graph_limit") or 12),
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            failures.append(
                {
                    "source_id": source.get("source_id"),
                    "platform": source.get("platform"),
                    "title": source.get("title"),
                    "connected_run_id": connected_run_id,
                    "reason": exc.__class__.__name__,
                    "error": str(exc),
                }
            )
            continue
        if not include_source_refs:
            query_packet = _drop_source_refs(query_packet)
        query_responses = query_packet.get("responses") if isinstance(query_packet.get("responses"), list) else []
        response = query_responses[0] if query_responses and isinstance(query_responses[0], dict) else {}
        if not response:
            blocked_sources.append(
                _source_blocked(
                    source,
                    str(query_packet.get("status") or "no_response"),
                    "query-ready connected run returned no response for this source",
                    selected_entry=selected_entry,
                    query_packet=query_packet,
                )
            )
            continue
        answer_packet = response.get("answer_packet") if isinstance(response.get("answer_packet"), dict) else {}
        lesson_context = response.get("lesson_context") if isinstance(response.get("lesson_context"), dict) else {}
        evidence_report = response.get("evidence_report") if isinstance(response.get("evidence_report"), dict) else {}
        responses.append(
            {
                "source_id": source.get("source_id"),
                "platform": source.get("platform"),
                "title": source.get("title"),
                "selected_source": source,
                "selected_entry": selected_entry,
                "connected_run_id": connected_run_id,
                "status": query_packet.get("status"),
                "answer_ready": bool(response.get("answer_ready")),
                "result_count": answer_packet.get("result_count", 0),
                "evidence_count": len(answer_packet.get("evidence_chain", [])) if isinstance(answer_packet.get("evidence_chain"), list) else 0,
                "graph_status": (lesson_context.get("graph_context") if isinstance(lesson_context.get("graph_context"), dict) else {}).get("status"),
                "query_packet": query_packet,
                "answer_packet": answer_packet,
                "lesson_context": lesson_context,
                "evidence_report": evidence_report,
                "quality": query_packet.get("quality", {}),
            }
        )
    quality = _sources_answer_quality(responses, blocked_sources, failures)
    return {
        "schema": "aoa_course_sources_answer_packet_v1",
        "status": _sources_answer_status(responses, blocked_sources, failures),
        "network_touched": False,
        "read_only": True,
        "query": str(query_value),
        "source_refs_included": include_source_refs,
        "candidate_source_count": len(sources),
        "selected_source_count": len(selected_sources),
        "response_count": len(responses),
        "blocked_source_count": len(blocked_sources),
        "failure_count": len(failures),
        "source_limit": source_limit,
        "catalog_summary": _source_answer_catalog_summary(catalog),
        "responses": responses,
        "blocked_sources": blocked_sources,
        "failures": failures,
        "quality": quality,
        "next_commands": _sources_answer_next_commands(str(query_value), source_ids, platforms, mode_value),
    }


def _call_sources_answer_matrix(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    mode_value = args.get("mode")
    if mode_value is not None and not isinstance(mode_value, str):
        raise ValueError("sources_answer_matrix mode must be a string")
    coverage_mode = str(args.get("coverage_mode") or "all-sources")
    if coverage_mode not in {"all-sources", "portfolio"}:
        raise ValueError("sources_answer_matrix coverage_mode must be all-sources or portfolio")
    queries = _string_array_arg(args.get("queries"), tool_name="sources_answer_matrix", field_name="queries")
    if not queries:
        raise ValueError("sources_answer_matrix queries must include at least one string")
    query_packets = [
        _call_sources_answer(roots, {key: value for key, value in args.items() if key != "queries"} | {"query": query})
        for query in queries
    ]
    quality = _sources_answer_matrix_quality(query_packets, coverage_mode=coverage_mode)
    source_ids = _string_array_arg(args.get("source_ids"), tool_name="sources_answer_matrix", field_name="source_ids")
    platforms = _platform_arg(args.get("platforms"), tool_name="sources_answer_matrix")
    return {
        "schema": "aoa_course_sources_answer_matrix_v1",
        "status": _sources_answer_matrix_status(query_packets, quality),
        "network_touched": False,
        "read_only": True,
        "coverage_mode": coverage_mode,
        "queries": queries,
        "query_count": len(queries),
        "source_refs_included": bool(query_packets[0].get("source_refs_included")) if query_packets else False,
        "response_count_total": quality["response_count_total"],
        "blocked_source_count_total": quality["blocked_source_count_total"],
        "failure_count_total": quality["failure_count_total"],
        "query_packets": query_packets,
        "query_summaries": [_sources_answer_matrix_summary(packet, coverage_mode=coverage_mode) for packet in query_packets],
        "blocked_sources": _sources_answer_matrix_nested_items(query_packets, "blocked_sources"),
        "failures": _sources_answer_matrix_nested_items(query_packets, "failures"),
        "quality": quality,
        "next_commands": _sources_answer_matrix_next_commands(queries, source_ids, platforms, mode_value, coverage_mode),
    }


def _source_answer_entries(source: dict[str, object], kinds: list[str] | None) -> list[dict[str, object]]:
    entries = source.get("latest_connected_runs") if isinstance(source.get("latest_connected_runs"), list) else []
    if kinds:
        kind_set = set(kinds)
        entries = [entry for entry in entries if isinstance(entry, dict) and str(entry.get("kind") or "") in kind_set]
    else:
        sync_entries = [entry for entry in entries if isinstance(entry, dict) and entry.get("kind") == "sync"]
        if sync_entries:
            entries = sync_entries
    return [entry for entry in entries if isinstance(entry, dict) and bool(entry.get("query_ready"))]


def _external_semantic_provider_failure(source: dict[str, object], selected_entry: dict[str, object], mode: str | None) -> dict[str, object] | None:
    entry_mode = str(mode or selected_entry.get("query_mode") or "keyword")
    if entry_mode not in {"semantic", "hybrid"}:
        return None
    paths = selected_entry.get("paths") if isinstance(selected_entry.get("paths"), dict) else {}
    semantic_path = str(paths.get("semantic_index") or paths.get("semantic_index_path") or "")
    provider = _semantic_index_provider(semantic_path)
    if not semantic_path or not provider or provider == LOCAL_HASHING_PROVIDER:
        return None
    run_id = str(selected_entry.get("run_id") or "")
    next_command = "aoa-course build-semantic-index"
    if run_id:
        next_command += f" --run {shlex.quote(run_id)}"
    next_command += f" --provider {LOCAL_HASHING_PROVIDER}"
    return {
        "surface": "sources_answer",
        "source_id": str(source.get("source_id") or selected_entry.get("source_id") or ""),
        "run_id": run_id,
        "field": "semantic_index.provider",
        "expected": LOCAL_HASHING_PROVIDER,
        "actual": provider,
        "path": semantic_path,
        "reason": "external_semantic_provider_requires_network",
        "detail": "selected semantic index uses an external embedding provider; rebuild with local_hashing_v1 before using no-network answer routes",
        "next_command": next_command,
    }


def _semantic_index_provider(path: str) -> str:
    if not path:
        return ""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if isinstance(payload, dict):
        return str(payload.get("provider") or "")
    return ""


def _query_source_entry(
    roots: StorageRoots,
    source: dict[str, object],
    selected_entry: dict[str, object],
    *,
    query: str,
    mode: str | None,
    limit: int,
    graph_limit: int,
) -> dict[str, object]:
    if selected_entry.get("entry_source") != "sync_checkpoint":
        return _call_connected_run_query(
            roots,
            {
                "run": str(selected_entry.get("connected_run_id") or ""),
                "query": query,
                "source_ids": [str(source.get("source_id") or "")],
                "kinds": [str(selected_entry.get("kind") or "")],
                "limit": limit,
                "mode": mode,
                "graph_limit": graph_limit,
                "entry_limit": 1,
            },
        )
    run_id = str(selected_entry.get("run_id") or "")
    if not run_id:
        raise ValueError("sync checkpoint query-ready entry has no run_id")
    entry_mode = str(mode or selected_entry.get("query_mode") or "keyword")
    answer_packet = render_answer_packet(roots, query, run_id, limit, entry_mode)
    lesson_context = render_lesson_context_packet(roots, query, run_id, limit, entry_mode, graph_limit)
    graph_context = lesson_context.get("graph_context") if isinstance(lesson_context.get("graph_context"), dict) else {}
    quality = answer_packet.get("quality") if isinstance(answer_packet.get("quality"), dict) else {}
    evidence_report = _evidence_report_from_answer_packet(answer_packet)
    response = {
        "kind": selected_entry.get("kind") or "sync",
        "platform": selected_entry.get("platform") or source.get("platform"),
        "run_id": run_id,
        "source_id": source.get("source_id"),
        "title": source.get("title"),
        "query": query,
        "mode": entry_mode,
        "query_ready": True,
        "answer_ready": bool(quality.get("ready")),
        "result_count": answer_packet.get("result_count", 0),
        "evidence_count": len(answer_packet.get("evidence_chain", [])) if isinstance(answer_packet.get("evidence_chain"), list) else 0,
        "graph_status": graph_context.get("status"),
        "graph_context_count": graph_context.get("context_count", 0),
        "quality": quality,
        "answer_packet": answer_packet,
        "lesson_context": lesson_context,
        "evidence_report": evidence_report,
        "commands": selected_entry.get("commands", {}),
        "mcp_commands": selected_entry.get("mcp_commands", {}),
    }
    packet_quality = {
        "ready": bool(response["answer_ready"]),
        "response_count": 1,
        "answer_ready_count": 1 if response["answer_ready"] else 0,
        "result_count_total": int(answer_packet.get("result_count") or 0),
        "evidence_count_total": int(response["evidence_count"] or 0),
        "blocked_entry_count": 0,
        "failure_count": 0,
        "all_responses_have_evidence": int(response["evidence_count"] or 0) > 0,
    }
    return {
        "schema": "aoa_course_connected_run_query_packet_v1",
        "status": "ok" if packet_quality["ready"] else "partial",
        "connected_run_id": selected_entry.get("connected_run_id") or selected_entry.get("sync_run_id") or run_id,
        "connected_run_status": selected_entry.get("connected_run_status") or "ok",
        "receipt_path": selected_entry.get("receipt_path") or "",
        "query": query,
        "limit": limit,
        "mode": entry_mode,
        "graph_limit": graph_limit,
        "entry_limit": 1,
        "entry_count": 1,
        "selected_entry_count": 1,
        "response_count": 1,
        "blocked_entry_count": 0,
        "failure_count": 0,
        "responses": [response],
        "blocked_entries": [],
        "failures": [],
        "quality": packet_quality,
        "next_commands": selected_entry.get("commands", {}),
        "network_touched": False,
        "read_only": True,
    }


def _evidence_report_from_answer_packet(answer_packet: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "aoa_course_connected_run_evidence_report_v1",
        "run_id": answer_packet.get("run_id"),
        "query": answer_packet.get("query"),
        "mode": answer_packet.get("mode"),
        "result_count": answer_packet.get("result_count"),
        "evidence_chain": answer_packet.get("evidence_chain", []),
        "quality": answer_packet.get("quality", {}),
        "freshness_report": answer_packet.get("freshness_report", {}),
        "authority_report": answer_packet.get("authority_report", {}),
        "refresh_report": answer_packet.get("refresh_report", {}),
        "result_refs": _evidence_result_refs(answer_packet),
    }


def _source_blocked(
    source: dict[str, object],
    reason: str,
    detail: str,
    *,
    selected_entry: dict[str, object] | None = None,
    query_packet: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = _compact_dict(
        {
            "source_id": source.get("source_id"),
            "platform": source.get("platform"),
            "title": source.get("title"),
            "access_mode": source.get("access_mode"),
            "reason": reason,
            "detail": detail,
            "selected_entry": selected_entry,
            "query_packet_status": query_packet.get("status") if isinstance(query_packet, dict) else None,
            "query_packet_blocked_entries": query_packet.get("blocked_entries") if isinstance(query_packet, dict) else None,
            "query_packet_failures": query_packet.get("failures") if isinstance(query_packet, dict) else None,
        }
    )
    return _drop_source_refs(payload) if isinstance(payload, dict) else payload


def _sources_answer_quality(responses: list[dict[str, object]], blocked_sources: list[dict[str, object]], failures: list[dict[str, object]]) -> dict[str, object]:
    answer_ready_count = sum(1 for response in responses if bool(response.get("answer_ready")))
    evidence_count_total = sum(int(response.get("evidence_count") or 0) for response in responses)
    result_count_total = sum(int(response.get("result_count") or 0) for response in responses)
    grounded_response_count = sum(1 for response in responses if _response_is_grounded(response))
    top_result_path_count = sum(1 for response in responses if _response_top_result_field(response, "path"))
    top_result_fetched_at_count = sum(1 for response in responses if _response_top_result_field(response, "fetched_at"))
    top_result_freshness_count = sum(1 for response in responses if _response_top_result_field(response, "freshness_state"))
    return {
        "ready": bool(responses) and answer_ready_count == len(responses) and not blocked_sources and not failures,
        "response_count": len(responses),
        "answer_ready_count": answer_ready_count,
        "grounded_response_count": grounded_response_count,
        "result_count_total": result_count_total,
        "evidence_count_total": evidence_count_total,
        "blocked_source_count": len(blocked_sources),
        "failure_count": len(failures),
        "platforms": sorted({str(response.get("platform") or "") for response in responses if response.get("platform")}),
        "source_ids": sorted({str(response.get("source_id") or "") for response in responses if response.get("source_id")}),
        "all_responses_have_evidence": bool(responses) and all(int(response.get("evidence_count") or 0) > 0 for response in responses),
        "all_grounded_responses_have_path": grounded_response_count > 0 and grounded_response_count == top_result_path_count,
        "all_grounded_responses_have_fetched_at": grounded_response_count > 0 and grounded_response_count == top_result_fetched_at_count,
        "all_grounded_responses_have_freshness": grounded_response_count > 0 and grounded_response_count == top_result_freshness_count,
    }


def _response_is_grounded(response: dict[str, object]) -> bool:
    answer_packet = response.get("answer_packet") if isinstance(response.get("answer_packet"), dict) else {}
    quality = answer_packet.get("quality") if isinstance(answer_packet.get("quality"), dict) else {}
    return bool(quality.get("ready")) and int(response.get("evidence_count") or 0) > 0


def _response_top_result_field(response: dict[str, object], field: str) -> object:
    if not _response_is_grounded(response):
        return None
    answer_packet = response.get("answer_packet") if isinstance(response.get("answer_packet"), dict) else {}
    quality = answer_packet.get("quality") if isinstance(answer_packet.get("quality"), dict) else {}
    top_result = quality.get("top_result") if isinstance(quality.get("top_result"), dict) else {}
    return top_result.get(field)


def _sources_answer_status(responses: list[dict[str, object]], blocked_sources: list[dict[str, object]], failures: list[dict[str, object]]) -> str:
    if responses and not blocked_sources and not failures and all(bool(response.get("answer_ready")) for response in responses):
        return "ok"
    if responses:
        return "partial"
    if blocked_sources or failures:
        return "blocked"
    return "missing"


def _sources_answer_matrix_quality(query_packets: list[dict[str, object]], *, coverage_mode: str = "all-sources") -> dict[str, object]:
    summaries = [_sources_answer_matrix_summary(packet) for packet in query_packets]
    ready_count = sum(1 for summary in summaries if bool(summary.get("ready")))
    evidence_ready_count = sum(1 for summary in summaries if int(summary.get("evidence_count_total") or 0) > 0)
    grounded_ready_count = sum(1 for summary in summaries if int(summary.get("grounded_response_count") or 0) > 0)
    response_count_total = sum(int(summary.get("response_count") or 0) for summary in summaries)
    evidence_count_total = sum(int(summary.get("evidence_count_total") or 0) for summary in summaries)
    result_count_total = sum(int(summary.get("result_count_total") or 0) for summary in summaries)
    grounded_response_count_total = sum(int(summary.get("grounded_response_count") or 0) for summary in summaries)
    blocked_source_count_total = sum(int(summary.get("blocked_source_count") or 0) for summary in summaries)
    failure_count_total = sum(int(summary.get("failure_count") or 0) for summary in summaries)
    source_scoped_ready = (
        bool(query_packets)
        and ready_count == len(query_packets)
        and response_count_total >= len(query_packets)
        and evidence_count_total >= len(query_packets)
        and blocked_source_count_total == 0
        and failure_count_total == 0
    )
    portfolio_ready = bool(query_packets) and grounded_ready_count == len(query_packets) and blocked_source_count_total == 0 and failure_count_total == 0
    ready = portfolio_ready if coverage_mode == "portfolio" else source_scoped_ready
    selected_ready_count = grounded_ready_count if coverage_mode == "portfolio" else ready_count
    return {
        "ready": ready,
        "coverage_mode": coverage_mode,
        "source_scoped_ready": source_scoped_ready,
        "portfolio_ready": portfolio_ready,
        "query_count": len(query_packets),
        "ready_query_count": selected_ready_count,
        "source_scoped_ready_query_count": ready_count,
        "portfolio_ready_query_count": grounded_ready_count,
        "evidence_ready_query_count": evidence_ready_count,
        "grounded_ready_query_count": grounded_ready_count,
        "blocked_query_count": len(query_packets) - selected_ready_count,
        "source_scoped_gap_query_count": len(query_packets) - ready_count,
        "evidence_gap_query_count": len(query_packets) - evidence_ready_count,
        "grounding_gap_query_count": len(query_packets) - grounded_ready_count,
        "response_count_total": response_count_total,
        "result_count_total": result_count_total,
        "evidence_count_total": evidence_count_total,
        "grounded_response_count_total": grounded_response_count_total,
        "blocked_source_count_total": blocked_source_count_total,
        "failure_count_total": failure_count_total,
        "all_queries_have_responses": bool(query_packets) and all(int(summary.get("response_count") or 0) > 0 for summary in summaries),
        "all_queries_have_evidence": bool(query_packets) and all(int(summary.get("evidence_count_total") or 0) > 0 for summary in summaries),
        "all_queries_have_grounded_response": bool(query_packets) and all(int(summary.get("grounded_response_count") or 0) > 0 for summary in summaries),
        "all_grounded_responses_have_path": grounded_response_count_total > 0 and all(bool(summary.get("all_grounded_responses_have_path")) for summary in summaries if int(summary.get("grounded_response_count") or 0) > 0),
        "all_grounded_responses_have_fetched_at": grounded_response_count_total > 0 and all(bool(summary.get("all_grounded_responses_have_fetched_at")) for summary in summaries if int(summary.get("grounded_response_count") or 0) > 0),
        "all_grounded_responses_have_freshness": grounded_response_count_total > 0 and all(bool(summary.get("all_grounded_responses_have_freshness")) for summary in summaries if int(summary.get("grounded_response_count") or 0) > 0),
        "platforms": sorted({
            platform
            for summary in summaries
            for platform in summary.get("platforms", [])
            if isinstance(platform, str) and platform
        }),
        "source_ids": sorted({
            source_id
            for summary in summaries
            for source_id in summary.get("source_ids", [])
            if isinstance(source_id, str) and source_id
        }),
    }


def _sources_answer_matrix_summary(packet: dict[str, object], *, coverage_mode: str = "all-sources") -> dict[str, object]:
    quality = packet.get("quality") if isinstance(packet.get("quality"), dict) else {}
    response_count = int(packet.get("response_count") or 0)
    blocked_source_count = int(packet.get("blocked_source_count") or 0)
    failure_count = int(packet.get("failure_count") or 0)
    grounded_response_count = int(quality.get("grounded_response_count") or 0)
    source_scoped_ready = bool(quality.get("ready"))
    portfolio_ready = grounded_response_count > 0 and blocked_source_count == 0 and failure_count == 0
    selected_ready = portfolio_ready if coverage_mode == "portfolio" else source_scoped_ready
    return {
        "query": packet.get("query"),
        "status": "ok" if selected_ready else packet.get("status"),
        "ready": selected_ready,
        "source_scoped_ready": source_scoped_ready,
        "portfolio_ready": portfolio_ready,
        "response_count": response_count,
        "blocked_source_count": blocked_source_count,
        "failure_count": failure_count,
        "result_count_total": int(quality.get("result_count_total") or 0),
        "evidence_count_total": int(quality.get("evidence_count_total") or 0),
        "grounded_response_count": grounded_response_count,
        "all_responses_have_evidence": bool(quality.get("all_responses_have_evidence")),
        "all_grounded_responses_have_path": bool(quality.get("all_grounded_responses_have_path")),
        "all_grounded_responses_have_fetched_at": bool(quality.get("all_grounded_responses_have_fetched_at")),
        "all_grounded_responses_have_freshness": bool(quality.get("all_grounded_responses_have_freshness")),
        "platforms": quality.get("platforms", []),
        "source_ids": quality.get("source_ids", []),
        "top_result_refs": _sources_answer_matrix_top_result_refs(packet, grounded_only=coverage_mode == "portfolio"),
    }


def _sources_answer_matrix_top_result_refs(packet: dict[str, object], *, grounded_only: bool = False) -> list[dict[str, object]]:
    responses = packet.get("responses") if isinstance(packet.get("responses"), list) else []
    refs: list[dict[str, object]] = []
    for response in responses:
        if not isinstance(response, dict):
            continue
        if grounded_only and not _response_is_grounded(response):
            continue
        answer_packet = response.get("answer_packet") if isinstance(response.get("answer_packet"), dict) else {}
        quality = answer_packet.get("quality") if isinstance(answer_packet.get("quality"), dict) else {}
        top_result = quality.get("top_result") if isinstance(quality.get("top_result"), dict) else {}
        ref = _compact_dict(
            {
                "source_id": response.get("source_id"),
                "platform": response.get("platform"),
                "connected_run_id": response.get("connected_run_id"),
                "doc_id": top_result.get("doc_id"),
                "path": top_result.get("path"),
                "fetched_at": top_result.get("fetched_at"),
                "freshness_state": top_result.get("freshness_state"),
                "score": top_result.get("score"),
                "rank_score": top_result.get("rank_score"),
            }
        )
        if grounded_only and not ref.get("doc_id"):
            continue
        refs.append(ref)
    if grounded_only:
        refs = sorted(refs, key=lambda ref: (float(ref.get("rank_score") or 0.0), float(ref.get("score") or 0.0)), reverse=True)
    return refs


def _sources_answer_matrix_status(query_packets: list[dict[str, object]], quality: dict[str, object]) -> str:
    if not query_packets:
        return "missing"
    if bool(quality.get("ready")):
        return "ok"
    if int(quality.get("response_count_total") or 0) > 0:
        return "partial"
    return "blocked"


def _sources_answer_matrix_nested_items(query_packets: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for packet in query_packets:
        values = packet.get(key) if isinstance(packet.get(key), list) else []
        for item in values:
            if isinstance(item, dict):
                items.append({"query": packet.get("query"), **item})
    return items


def _sources_answer_next_commands(query: str, source_ids: list[str] | None, platforms: list[str] | None, mode: str | None) -> list[str]:
    payload: dict[str, object] = {"query": query}
    if source_ids:
        payload["source_ids"] = source_ids
    if platforms:
        payload["platforms"] = platforms
    if mode:
        payload["mode"] = mode
    return [
        _sources_answer_cli_command(query, source_ids=source_ids, platforms=platforms, mode=mode),
        f"aoa-course mcp call sources_answer {shlex.quote(json.dumps(payload, ensure_ascii=True, separators=(',', ':')))}",
        "aoa-course mcp call list_sources '{\"include_source_refs\":false,\"connected_run_limit\":5}'",
    ]


def _sources_answer_matrix_next_commands(
    queries: list[str],
    source_ids: list[str] | None,
    platforms: list[str] | None,
    mode: str | None,
    coverage_mode: str = "all-sources",
) -> list[str]:
    payload: dict[str, object] = {"queries": queries}
    if source_ids:
        payload["source_ids"] = source_ids
    if platforms:
        payload["platforms"] = platforms
    if mode:
        payload["mode"] = mode
    if coverage_mode != "all-sources":
        payload["coverage_mode"] = coverage_mode
    return [
        _sources_answer_matrix_cli_command(queries, source_ids=source_ids, platforms=platforms, mode=mode, coverage_mode=coverage_mode),
        f"aoa-course mcp call sources_answer_matrix {shlex.quote(json.dumps(payload, ensure_ascii=True, separators=(',', ':')))}",
        "aoa-course sources list --no-source-refs --connected-run-limit 5",
    ]


def _source_answer_blocked(
    catalog: dict[str, object],
    query: str,
    reason: str,
    detail: str,
    *,
    status: str = "blocked",
) -> dict[str, object]:
    return {
        "schema": "aoa_course_source_answer_packet_v1",
        "status": status,
        "reason": reason,
        "detail": detail,
        "network_touched": False,
        "read_only": True,
        "query": query,
        "source_refs_included": bool(catalog.get("source_refs_included")),
        "candidate_source_count": len(catalog.get("sources", [])) if isinstance(catalog.get("sources"), list) else 0,
        "catalog_summary": _source_answer_catalog_summary(catalog),
        "candidate_sources": _source_answer_candidate_sources(catalog),
        "next_commands": [
            "aoa-course mcp call list_sources '{\"include_source_refs\":false,\"connected_run_limit\":5}'",
            "aoa-course preflight connected-plan --live-scope bounded",
        ],
    }


def _source_answer_catalog_summary(catalog: dict[str, object]) -> dict[str, object]:
    return {
        "schema": catalog.get("schema"),
        "path": catalog.get("path"),
        "network_touched": catalog.get("network_touched"),
        "read_only": catalog.get("read_only"),
        "source_refs_included": catalog.get("source_refs_included"),
        "selected_platforms": catalog.get("selected_platforms", []),
        "selected_source_ids": catalog.get("selected_source_ids", []),
        "missing_source_ids": catalog.get("missing_source_ids", []),
        "source_count": catalog.get("source_count"),
        "selected_source_count": catalog.get("selected_source_count"),
        "connected_runs": catalog.get("connected_runs", {}),
    }


def _source_answer_candidate_sources(catalog: dict[str, object]) -> list[dict[str, object]]:
    sources = catalog.get("sources") if isinstance(catalog.get("sources"), list) else []
    return [
        _compact_dict(
            {
                "source_id": source.get("source_id"),
                "platform": source.get("platform"),
                "title": source.get("title"),
                "access_mode": source.get("access_mode"),
                "enabled": source.get("enabled"),
                "query_ready_connected_run_count": source.get("query_ready_connected_run_count"),
            }
        )
        for source in sources
        if isinstance(source, dict)
    ]


def _source_answer_next_commands(source: dict[str, object], selected_entry: dict[str, object], query: str, mode: str | None) -> list[str]:
    source_id = str(source.get("source_id") or "")
    connected_run_id = str(selected_entry.get("connected_run_id") or DEFAULT_CONNECTED_RUN)
    kind = str(selected_entry.get("kind") or "")
    source_answer_payload: dict[str, object] = {"query": query, "source_id": source_id}
    if mode:
        source_answer_payload["mode"] = mode
    if selected_entry.get("entry_source") == "sync_checkpoint":
        run_id = str(selected_entry.get("run_id") or "")
        query_mode = mode or str(selected_entry.get("query_mode") or "keyword")
        return [
            _sources_answer_cli_command(query, source_ids=[source_id] if source_id else None, kinds=[kind] if kind else None, mode=mode),
            f"aoa-course mcp call source_answer {shlex.quote(json.dumps(source_answer_payload, ensure_ascii=True, separators=(',', ':')))}",
            f"aoa-course answer {shlex.quote(query)} --run {shlex.quote(run_id)} --mode {query_mode}",
            f"aoa-course lesson-context {shlex.quote(query)} --run {shlex.quote(run_id)} --mode {query_mode} --graph-limit 12",
            f"aoa-course mcp call evidence_report {shlex.quote(json.dumps({'query': query, 'run': run_id, 'mode': query_mode}, ensure_ascii=True, separators=(',', ':')))}",
        ]
    connected_query_payload = {
        "run": connected_run_id,
        "query": query,
        "source_ids": [source_id],
        "kinds": [kind],
        "entry_limit": 1,
    }
    return [
        _sources_answer_cli_command(query, source_ids=[source_id] if source_id else None, kinds=[kind] if kind else None, mode=mode),
        f"aoa-course mcp call source_answer {shlex.quote(json.dumps(source_answer_payload, ensure_ascii=True, separators=(',', ':')))}",
        f"aoa-course mcp call connected_run_query {shlex.quote(json.dumps(connected_query_payload, ensure_ascii=True, separators=(',', ':')))}",
    ]


def _sources_answer_cli_command(
    query: str,
    *,
    source_ids: list[str] | None = None,
    platforms: list[str] | None = None,
    kinds: list[str] | None = None,
    mode: str | None = None,
) -> str:
    parts = ["aoa-course", "sources", "answer", shlex.quote(query)]
    for source_id in source_ids or []:
        if source_id:
            parts.extend(["--source-id", shlex.quote(source_id)])
    for platform in platforms or []:
        if platform:
            parts.extend(["--platform", shlex.quote(platform)])
    for kind in kinds or []:
        if kind:
            parts.extend(["--kind", shlex.quote(kind)])
    if mode:
        parts.extend(["--mode", shlex.quote(mode)])
    return " ".join(parts)


def _sources_answer_matrix_cli_command(
    queries: list[str],
    *,
    source_ids: list[str] | None = None,
    platforms: list[str] | None = None,
    mode: str | None = None,
    coverage_mode: str = "all-sources",
) -> str:
    parts = ["aoa-course", "sources", "answer-matrix"]
    for query in queries:
        if query:
            parts.extend(["--query", shlex.quote(query)])
    for source_id in source_ids or []:
        if source_id:
            parts.extend(["--source-id", shlex.quote(source_id)])
    for platform in platforms or []:
        if platform:
            parts.extend(["--platform", shlex.quote(platform)])
    if mode:
        parts.extend(["--mode", shlex.quote(mode)])
    if coverage_mode != "all-sources":
        parts.extend(["--coverage-mode", shlex.quote(coverage_mode)])
    return " ".join(parts)


def _drop_source_refs(value: object) -> object:
    if isinstance(value, dict):
        return {key: _drop_source_refs(item) for key, item in value.items() if key != "source_ref"}
    if isinstance(value, list):
        return [_drop_source_refs(item) for item in value]
    return value


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
        source_ids=_string_array_arg(args.get("source_ids"), tool_name="live_preflight", field_name="source_ids"),
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
        source_ids=_string_array_arg(args.get("source_ids"), tool_name="connector_readiness", field_name="source_ids"),
        connected_run=str(args.get("connected_run") or DEFAULT_CONNECTED_RUN),
        stepik_token_env=str(args.get("stepik_token_env") or "STEPIK_API_TOKEN"),
        browser_state_file=Path(state_file) if state_file else None,
        expect_origin_contains=str(args.get("expect_origin") or "") or None,
        include_disabled=bool(args.get("include_disabled", False)),
        query=str(args.get("query") or "") or None,
        max_lessons=int(args.get("max_lessons") or 50),
        max_pages=int(args.get("max_pages") or 5),
        max_sources=int(args.get("max_sources") or 50),
        link_pattern=str(args.get("link_pattern") or "") or None,
        live_scope=str(args.get("live_scope") or "bounded"),
        include_step_sources=_bool_arg(args.get("include_step_sources"), default=False, tool_name="connector_readiness", field_name="include_step_sources"),
        max_step_sources=_max_step_sources_arg(args.get("max_step_sources", DEFAULT_MAX_STEP_SOURCES), tool_name="connector_readiness"),
        step_source_timeout=_step_source_timeout_arg(args.get("step_source_timeout"), tool_name="connector_readiness"),
        semantic_provider=str(args.get("semantic_provider") or LOCAL_HASHING_PROVIDER),
        dimensions=int(args.get("dimensions") or 256),
        embedding_endpoint=str(args.get("embedding_endpoint") or "") or None,
        embedding_model=str(args.get("embedding_model") or "") or None,
        embedding_token_env=str(args.get("embedding_token_env") or "AOA_COURSE_EMBEDDING_TOKEN"),
        embedding_batch_size=int(args.get("embedding_batch_size") or 32),
        embedding_timeout_seconds=float(args.get("embedding_timeout_seconds") or 30.0),
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
        source_ids=_string_array_arg(args.get("source_ids"), tool_name="connected_source_plan", field_name="source_ids"),
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
        include_step_sources=_bool_arg(args.get("include_step_sources"), default=False, tool_name="connected_source_plan", field_name="include_step_sources"),
        max_step_sources=_max_step_sources_arg(args.get("max_step_sources", DEFAULT_MAX_STEP_SOURCES), tool_name="connected_source_plan"),
        step_source_timeout=_step_source_timeout_arg(args.get("step_source_timeout"), tool_name="connected_source_plan"),
    )


def _call_connection_profile_inspect(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    profile_path = args.get("profile_path")
    if not isinstance(profile_path, str) or not profile_path:
        raise ValueError("connection_profile_inspect profile_path must be a non-empty string")
    path = Path(profile_path)
    profile = load_connection_profile(path)
    return inspect_connection_profile(roots, profile, profile_path=path)


def _call_connection_profile_status(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    profile_path = args.get("profile_path")
    if not isinstance(profile_path, str) or not profile_path:
        raise ValueError("connection_profile_status profile_path must be a non-empty string")
    path = Path(profile_path)
    profile = load_connection_profile(path)
    return connection_profile_status(inspect_connection_profile(roots, profile, profile_path=path))


def _call_connection_profile_run_plan(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    profile_path = args.get("profile_path")
    if not isinstance(profile_path, str) or not profile_path:
        raise ValueError("connection_profile_run_plan profile_path must be a non-empty string")
    platform = args.get("platform")
    if platform is not None and not isinstance(platform, str):
        raise ValueError("connection_profile_run_plan platform must be a string")
    path = Path(profile_path)
    profile = load_connection_profile(path)
    inspection = inspect_connection_profile(roots, profile, profile_path=path)
    return connection_profile_run_plan(
        profile,
        inspection,
        platform=platform,
        source_ids=_string_array_arg(args.get("source_ids"), tool_name="connection_profile_run_plan", field_name="source_ids"),
    )


def _call_semantic_provider_preflight(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    return semantic_provider_preflight(
        roots,
        run_id=str(args.get("run") or DEFAULT_RUN),
        provider=str(args.get("provider") or LOCAL_HASHING_PROVIDER),
        dimensions=int(args.get("dimensions") or 256),
        embedding_endpoint=str(args.get("embedding_endpoint") or "") or None,
        embedding_model=str(args.get("embedding_model") or "") or None,
        embedding_token_env=str(args.get("embedding_token_env") or "AOA_COURSE_EMBEDDING_TOKEN"),
        embedding_batch_size=int(args.get("embedding_batch_size") or 32),
        embedding_timeout_seconds=float(args.get("embedding_timeout_seconds") or 30.0),
    )


def _call_browser_snapshot_audit(args: dict[str, object]) -> dict[str, object]:
    snapshot_path = args.get("snapshot_path")
    if not isinstance(snapshot_path, str) or not snapshot_path:
        raise ValueError("browser_snapshot_audit snapshot_path must be a non-empty string")
    path = Path(snapshot_path).expanduser()
    if not path.is_absolute():
        path = find_repo_root() / path
    platform = args.get("platform")
    if platform is not None and not isinstance(platform, str):
        raise ValueError("browser_snapshot_audit platform must be a string")
    return audit_browser_snapshot_file(
        path,
        platform=platform,
        max_sources=int(args.get("max_sources") or 50),
        max_lessons=int(args.get("max_lessons") or 50),
        link_pattern=str(args.get("link_pattern") or "") or None,
    )


def _call_connected_run(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    state_file = args.get("state_file")
    if state_file is not None and not isinstance(state_file, str):
        raise ValueError("connected_run state_file must be a string")
    source_limit_value = args.get("source_limit")
    source_limit = int(source_limit_value) if source_limit_value is not None else None
    return run_connected_calibration(
        roots,
        run_id=str(args.get("run") or DEFAULT_CONNECTED_RUN),
        mode=str(args.get("mode") or "fixture"),
        platforms=_platform_arg(args.get("platforms"), tool_name="connected_run"),
        source_ids=_string_array_arg(args.get("source_ids"), tool_name="connected_run", field_name="source_ids"),
        query=str(args.get("query") or "") or None,
        live_scope=str(args.get("live_scope") or "bounded"),
        include_step_sources=_bool_arg(args.get("include_step_sources"), default=False, tool_name="connected_run", field_name="include_step_sources"),
        max_step_sources=_max_step_sources_arg(args.get("max_step_sources", DEFAULT_MAX_STEP_SOURCES), tool_name="connected_run"),
        step_source_timeout=_step_source_timeout_arg(args.get("step_source_timeout"), tool_name="connected_run"),
        allow_network=bool(args.get("allow_network", False)),
        stepik_token_env=str(args.get("stepik_token_env") or "STEPIK_API_TOKEN"),
        browser_state_file=Path(state_file) if state_file else None,
        expect_origin_contains=str(args.get("expect_origin") or "") or None,
        max_lessons=int(args.get("max_lessons") or 50),
        max_pages=int(args.get("max_pages") or 5),
        max_sources=int(args.get("max_sources") or 50),
        link_pattern=str(args.get("link_pattern") or "") or None,
        source_limit=source_limit,
    )


def _call_connected_run_query(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    mode_value = args.get("mode")
    if mode_value is not None and not isinstance(mode_value, str):
        raise ValueError("connected_run_query mode must be a string")
    return query_connected_calibration(
        roots,
        run_id=str(args.get("run") or DEFAULT_CONNECTED_RUN),
        query=str(args.get("query") or "") or None,
        platforms=_platform_arg(args.get("platforms"), tool_name="connected_run_query"),
        source_ids=_string_array_arg(args.get("source_ids"), tool_name="connected_run_query", field_name="source_ids"),
        kinds=_string_array_arg(args.get("kinds"), tool_name="connected_run_query", field_name="kinds"),
        limit=int(args.get("limit") or 5),
        mode=mode_value,
        graph_limit=int(args.get("graph_limit") or 12),
        entry_limit=int(args.get("entry_limit") or 5),
    )


def _call_connected_run_query_matrix(roots: StorageRoots, args: dict[str, object]) -> dict[str, object]:
    mode_value = args.get("mode")
    if mode_value is not None and not isinstance(mode_value, str):
        raise ValueError("connected_run_query_matrix mode must be a string")
    queries = _string_array_arg(args.get("queries"), tool_name="connected_run_query_matrix", field_name="queries")
    if not queries:
        raise ValueError("connected_run_query_matrix queries must include at least one string")
    return query_connected_calibration_matrix(
        roots,
        run_id=str(args.get("run") or DEFAULT_CONNECTED_RUN),
        queries=queries,
        platforms=_platform_arg(args.get("platforms"), tool_name="connected_run_query_matrix"),
        source_ids=_string_array_arg(args.get("source_ids"), tool_name="connected_run_query_matrix", field_name="source_ids"),
        kinds=_string_array_arg(args.get("kinds"), tool_name="connected_run_query_matrix", field_name="kinds"),
        limit=int(args.get("limit") or 5),
        mode=mode_value,
        graph_limit=int(args.get("graph_limit") or 12),
        entry_limit=int(args.get("entry_limit") or 5),
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


def _string_array_arg(value: object, *, tool_name: str, field_name: str) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError(f"{tool_name} {field_name} must be an array of strings")


def _bool_arg(value: object, *, default: bool, tool_name: str, field_name: str) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ValueError(f"{tool_name} {field_name} must be a boolean")


def _positive_int_arg(value: object, *, default: int, tool_name: str, field_name: str) -> int:
    if value is None:
        return default
    if isinstance(value, int) and value >= 1:
        return value
    raise ValueError(f"{tool_name} {field_name} must be an integer >= 1")


def _max_step_sources_arg(value: object, *, tool_name: str) -> int | None:
    try:
        return normalize_max_step_sources(value, default=DEFAULT_MAX_STEP_SOURCES)
    except ValueError as exc:
        raise ValueError(f"{tool_name} max_step_sources must be a non-negative integer or 'all'") from exc


def _step_source_timeout_arg(value: object, *, tool_name: str) -> float:
    try:
        return normalize_step_source_timeout(value, default=DEFAULT_STEP_SOURCE_TIMEOUT)
    except ValueError as exc:
        raise ValueError(f"{tool_name} step_source_timeout must be a positive number") from exc


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
