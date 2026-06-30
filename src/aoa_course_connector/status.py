"""Read-only connector status packets for humans and agents."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from aoa_course_connector.adapters import adapter_list
from aoa_course_connector.calibration.connected_run import load_connected_calibration_status
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.readiness import connected_source_plan, live_preflight
from aoa_course_connector.sources import load_registry, registry_path
from aoa_course_connector.storage import storage_status


DEFAULT_RUN = "starter-fixture"
DEFAULT_CONNECTED_RUN = "connected-calibration"
DEFAULT_PLATFORMS = ["getcourse", "skillspace", "stepik"]
REQUIRED_ROUTE_FILES = [
    "AGENTS.md",
    "README.md",
    "connector/SOURCE_POLICY.md",
    "connector/STORAGE_POLICY.md",
    "docs/AGENT_INSTALL_ROUTE.md",
    "docs/CLI_USAGE.md",
    "docs/MCP_USAGE.md",
    "docs/STATUS.md",
]
REQUIRED_MCP_TOOLS = [
    "connector_readiness",
    "list_sources",
    "ingest_status",
    "sync_status",
    "live_preflight",
    "connected_source_plan",
    "connected_run_status",
    "refresh_plan",
    "search",
    "semantic_search",
    "hybrid_search",
    "lesson_context",
    "graph_neighbors",
    "freshness_report",
    "evidence_report",
]


def connector_readiness(
    repo_root: Path,
    roots: StorageRoots,
    *,
    runs: list[str] | None = None,
    platforms: list[str] | None = None,
    connected_run: str = DEFAULT_CONNECTED_RUN,
    stepik_token_env: str = "STEPIK_API_TOKEN",
    browser_state_file: Path | None = None,
    expect_origin_contains: str | None = None,
    include_disabled: bool = False,
    query: str | None = None,
    mcp_tool_names: list[str] | set[str] | None = None,
) -> dict[str, object]:
    """Build a single read-only route audit for install, query, and live handoff."""

    selected_runs = _dedupe([str(run) for run in (runs or [DEFAULT_RUN]) if str(run)])
    selected_platforms = _dedupe([str(platform) for platform in (platforms or DEFAULT_PLATFORMS) if str(platform)])
    missing_route_files = [rel for rel in REQUIRED_ROUTE_FILES if not (repo_root / rel).exists()]
    storage = storage_status(repo_root, roots)
    registry = load_registry(roots.data)
    source_summary = _source_registry_summary(roots, registry, include_disabled=include_disabled)
    run_statuses = [ingest_status(roots, run_id) for run_id in selected_runs]
    preflight = live_preflight(
        roots,
        platforms=selected_platforms,
        stepik_token_env=stepik_token_env,
        browser_state_file=browser_state_file,
        expect_origin_contains=expect_origin_contains,
        include_disabled=include_disabled,
    )
    plan = connected_source_plan(
        roots,
        platforms=selected_platforms,
        stepik_token_env=stepik_token_env,
        browser_state_file=browser_state_file,
        expect_origin_contains=expect_origin_contains,
        include_disabled=include_disabled,
        query=query,
    )
    connected_status = load_connected_calibration_status(roots, run_id=connected_run)
    mcp = _mcp_surface(mcp_tool_names)
    storage_exists = storage.get("exists") if isinstance(storage.get("exists"), dict) else {}
    query_ready = any(
        bool(status.get("readiness", {}).get("agent_query_ready"))
        for status in run_statuses
        if isinstance(status.get("readiness"), dict)
    )
    lanes = {
        "repo_route_ready": not missing_route_files,
        "data_artifact_roots_ready": bool(storage_exists.get("data")) and bool(storage_exists.get("artifact")),
        "all_storage_roots_exist": all(bool(storage_exists.get(name)) for name in ["data", "cache", "auth", "artifact"]),
        "source_registry_configured": int(source_summary.get("enabled_source_count", 0)) > 0,
        "agent_query_ready": query_ready,
        "connected_live_ready": bool(plan.get("ready")),
        "connected_run_receipt_ready": connected_status.get("status") == "ok",
        "mcp_tools_ready": bool(mcp.get("ready")),
    }
    operational_ready = bool(lanes["repo_route_ready"] and lanes["agent_query_ready"] and lanes["mcp_tools_ready"])
    status = "error" if missing_route_files else "ready" if operational_ready else "partial"
    return {
        "schema": "aoa_course_connector_readiness_v1",
        "tool": "connector_readiness",
        "status": status,
        "operational_ready": operational_ready,
        "network_touched": False,
        "read_only": True,
        "repo": {
            "root": str(repo_root),
            "missing_route_files": missing_route_files,
            "adapter_count": len(adapter_list()),
            "adapters": adapter_list(),
        },
        "storage": storage,
        "sources": source_summary,
        "runs": run_statuses,
        "live_preflight": _compact_preflight(preflight),
        "connected_source_plan": _compact_connected_plan(plan),
        "connected_run": connected_status,
        "mcp": mcp,
        "lanes": lanes,
        "next_commands": _next_commands(
            storage_exists=storage_exists,
            source_summary=source_summary,
            run_statuses=run_statuses,
            preflight=preflight,
            connected_plan=plan,
            connected_run=connected_status,
            mcp=mcp,
        ),
    }


def ingest_status(roots: StorageRoots, run_id: str) -> dict[str, object]:
    """Inspect one local run without reading raw private payloads."""

    data_dir = roots.data / "runs" / run_id
    artifact_dir = roots.artifact / "runs" / run_id
    normalized_path = data_dir / "normalized" / "course_bundle.json"
    keyword_path = artifact_dir / "indexes" / "keyword_index.json"
    semantic_path = artifact_dir / "indexes" / "semantic_index.json"
    graph_path = artifact_dir / "graphs" / "course_graph.json"
    normalized = _normalized_bundle_status(normalized_path)
    keyword = _artifact_json_status(
        keyword_path,
        keys=["schema", "built_at", "doc_count", "term_count", "unit"],
    )
    semantic = _artifact_json_status(
        semantic_path,
        keys=["schema", "built_at", "doc_count", "provider", "dimensions", "unit", "feature_contract"],
    )
    graph = _artifact_json_status(
        graph_path,
        keys=["schema", "built_at", "node_count", "edge_count"],
    )
    ready = bool(normalized.get("exists")) and bool(keyword.get("exists")) and bool(graph.get("exists"))
    partial = data_dir.exists() or artifact_dir.exists()
    return {
        "schema": "aoa_course_ingest_status_v1",
        "tool": "ingest_status",
        "run_id": run_id,
        "status": "ready" if ready else "partial" if partial else "missing",
        "network_touched": False,
        "read_only": True,
        "storage": {
            "data_dir": str(data_dir),
            "artifact_dir": str(artifact_dir),
        },
        "normalized": normalized,
        "receipts": _run_receipt_summaries(data_dir),
        "indexes": {
            "keyword": keyword,
            "semantic": semantic,
        },
        "graph": graph,
        "readiness": {
            "normalized_ready": bool(normalized.get("exists")),
            "query_ready": bool(keyword.get("exists")),
            "semantic_query_ready": bool(semantic.get("exists")),
            "graph_ready": bool(graph.get("exists")),
            "agent_query_ready": ready,
        },
        "next_commands": _ingest_status_next_commands(
            run_id,
            normalized_exists=bool(normalized.get("exists")),
            keyword_exists=bool(keyword.get("exists")),
            semantic_exists=bool(semantic.get("exists")),
            graph_exists=bool(graph.get("exists")),
        ),
    }


def _source_registry_summary(roots: StorageRoots, registry: dict[str, object], *, include_disabled: bool) -> dict[str, object]:
    sources = [source for source in registry.get("sources", []) if isinstance(source, dict)]
    selected_sources = [source for source in sources if include_disabled or source.get("enabled", True)]
    platform_counts = Counter(str(source.get("platform") or "unknown") for source in selected_sources)
    access_mode_counts = Counter(str(source.get("access_mode") or "unknown") for source in selected_sources)
    return {
        "schema": registry.get("schema"),
        "path": str(registry_path(roots.data)),
        "exists": registry_path(roots.data).exists(),
        "source_count": len(sources),
        "enabled_source_count": len([source for source in sources if source.get("enabled", True)]),
        "selected_source_count": len(selected_sources),
        "platform_counts": dict(sorted(platform_counts.items())),
        "access_mode_counts": dict(sorted(access_mode_counts.items())),
        "sources": [
            {
                "source_id": source.get("source_id"),
                "platform": source.get("platform"),
                "title": source.get("title"),
                "access_mode": source.get("access_mode"),
                "enabled": source.get("enabled", True),
                "updated_at": source.get("updated_at"),
            }
            for source in selected_sources
        ],
    }


def _mcp_surface(tool_names: list[str] | set[str] | None) -> dict[str, object]:
    advertised = sorted({str(name) for name in (tool_names or []) if str(name)})
    missing = [name for name in REQUIRED_MCP_TOOLS if name not in advertised]
    return {
        "server": "aoa-course-connector-mcp",
        "expected_tools": REQUIRED_MCP_TOOLS,
        "advertised_tools": advertised,
        "missing_tools": missing,
        "tool_count": len(advertised),
        "ready": not missing,
    }


def _compact_preflight(preflight: dict[str, object]) -> dict[str, object]:
    return {
        "schema": preflight.get("schema"),
        "status": preflight.get("status"),
        "ready": bool(preflight.get("ready")),
        "network_touched": bool(preflight.get("network_touched")),
        "platforms": preflight.get("platforms", []),
        "source_registry": preflight.get("source_registry"),
        "workflow_count": len(preflight.get("workflows", [])) if isinstance(preflight.get("workflows"), list) else 0,
        "next_commands": preflight.get("next_commands", []),
    }


def _compact_connected_plan(plan: dict[str, object]) -> dict[str, object]:
    return {
        "schema": plan.get("schema"),
        "status": plan.get("status"),
        "ready": bool(plan.get("ready")),
        "actionable": bool(plan.get("actionable")),
        "network_touched": bool(plan.get("network_touched")),
        "live_scope": plan.get("live_scope"),
        "platforms": plan.get("platforms", []),
        "source_registry": plan.get("source_registry"),
        "platform_plans": plan.get("platform_plans", []),
        "browser_auth_handoffs": plan.get("browser_auth_handoffs", []),
        "next_commands": plan.get("next_commands", []),
    }


def _next_commands(
    *,
    storage_exists: dict[str, object],
    source_summary: dict[str, object],
    run_statuses: list[dict[str, object]],
    preflight: dict[str, object],
    connected_plan: dict[str, object],
    connected_run: dict[str, object],
    mcp: dict[str, object],
) -> list[str]:
    commands: list[str] = []
    if not all(bool(storage_exists.get(name)) for name in ["data", "cache", "auth", "artifact"]):
        commands.append("aoa-course init")
    for run_status in run_statuses:
        commands.extend([str(command) for command in run_status.get("next_commands", []) if str(command)])
    if int(source_summary.get("enabled_source_count", 0)) == 0:
        commands.extend(
            [
                'aoa-course discover stepik 67 --register --title "Stepik course 67"',
                "aoa-course discover stepik-account --from-fixture --register --source-limit 1",
                "aoa-course discover browser-fixture --platform getcourse --register",
                "aoa-course discover browser-fixture --platform skillspace --register",
            ]
        )
    if not bool(preflight.get("ready")):
        commands.extend([str(command) for command in preflight.get("next_commands", []) if str(command)])
    if not bool(connected_plan.get("ready")):
        commands.extend([str(command) for command in connected_plan.get("next_commands", []) if str(command)])
    if connected_run.get("status") != "ok":
        commands.append(f"aoa-course calibration connected-run --mode fixture --run {DEFAULT_CONNECTED_RUN}")
    if not bool(mcp.get("ready")):
        commands.append("aoa-course mcp tools")
    commands.append("aoa-course readiness --run starter-fixture")
    return _dedupe(commands)


def _normalized_bundle_status(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    payload = _load_json_file(path)
    if _json_load_error(payload):
        return {"exists": True, "path": str(path), "status": "error", "error": payload.get("_load_error")}
    if not isinstance(payload, dict):
        return {"exists": True, "path": str(path), "status": "error", "error": "normalized bundle is not a JSON object"}
    counts = _bundle_counts(payload)
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    return {
        "exists": True,
        "path": str(path),
        "schema": payload.get("schema"),
        "source": {
            "source_id": source.get("source_id"),
            "platform": source.get("platform"),
            "access_mode": source.get("access_mode"),
            "source_ref": source.get("source_ref"),
            "title": source.get("title"),
        },
        "counts": counts,
        "fetched_at": _bundle_fetched_at(payload),
    }


def _artifact_json_status(path: Path, *, keys: list[str]) -> dict[str, object]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    payload = _load_json_file(path)
    if _json_load_error(payload):
        return {"exists": True, "path": str(path), "status": "error", "error": payload.get("_load_error")}
    if not isinstance(payload, dict):
        return {"exists": True, "path": str(path), "status": "error", "error": "artifact is not a JSON object"}
    summary = {"exists": True, "path": str(path), "status": "ok"}
    for key in keys:
        if key in payload:
            summary[key] = payload.get(key)
    return summary


def _run_receipt_summaries(data_dir: Path) -> list[dict[str, object]]:
    if not data_dir.exists():
        return []
    summaries: list[dict[str, object]] = []
    for path in sorted(data_dir.glob("*receipt*.json")):
        payload = _load_json_file(path)
        if _json_load_error(payload):
            summaries.append({"path": str(path), "status": "error", "error": payload.get("_load_error")})
            continue
        if not isinstance(payload, dict):
            summaries.append({"path": str(path), "status": "error", "error": "receipt is not a JSON object"})
            continue
        summaries.append(
            {
                "path": str(path),
                "schema": payload.get("schema"),
                "status": payload.get("status"),
                "source_mode": payload.get("source_mode"),
                "network_touched": bool(payload.get("network_touched")),
                "completed_at": payload.get("completed_at"),
                "course_count": payload.get("course_count"),
                "evidence_count": payload.get("evidence_count"),
                "raw_path": payload.get("raw_path"),
                "normalized_path": payload.get("normalized_path"),
            }
        )
    return summaries


def _bundle_counts(bundle: dict[str, object]) -> dict[str, int]:
    counts = {
        "courses": 0,
        "modules": 0,
        "lessons": 0,
        "steps": 0,
        "assets": 0,
        "transcripts": 0,
        "assignments": 0,
        "comment_threads": 0,
        "comments": 0,
        "evidence": len(bundle.get("evidence", [])) if isinstance(bundle.get("evidence"), list) else 0,
    }
    for course in _dict_items(bundle.get("courses")):
        counts["courses"] += 1
        for module in _dict_items(course.get("modules")):
            counts["modules"] += 1
            for lesson in _dict_items(module.get("lessons")):
                counts["lessons"] += 1
                counts["steps"] += len(_dict_items(lesson.get("steps")))
                counts["assets"] += len(_dict_items(lesson.get("assets")))
                counts["transcripts"] += len(_dict_items(lesson.get("transcripts")))
                counts["assignments"] += len(_dict_items(lesson.get("assignments")))
                threads = _dict_items(lesson.get("comment_threads"))
                counts["comment_threads"] += len(threads)
                counts["comments"] += sum(len(_dict_items(thread.get("comments"))) for thread in threads)
    return counts


def _bundle_fetched_at(bundle: dict[str, object]) -> dict[str, object]:
    timestamps = sorted(
        {
            str(evidence.get("fetched_at"))
            for evidence in _dict_items(bundle.get("evidence"))
            if evidence.get("fetched_at")
        }
    )
    return {
        "count": len(timestamps),
        "earliest": timestamps[0] if timestamps else None,
        "latest": timestamps[-1] if timestamps else None,
    }


def _dict_items(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _ingest_status_next_commands(
    run_id: str,
    *,
    normalized_exists: bool,
    keyword_exists: bool,
    semantic_exists: bool,
    graph_exists: bool,
) -> list[str]:
    if not normalized_exists:
        if run_id == "starter-fixture":
            return [f"aoa-course materialize fixture --run {run_id}"]
        return [
            "aoa-course sources list",
            "aoa-course sync status",
            f"run an ingest, materialize, crawl, or source sync command that writes data/runs/{run_id}/normalized/course_bundle.json",
        ]
    commands: list[str] = []
    if not keyword_exists:
        commands.append(f"aoa-course build-index --run {run_id}")
    if not semantic_exists:
        commands.append(f"aoa-course build-semantic-index --run {run_id}")
    if not graph_exists:
        commands.append(f"aoa-course build-graph --run {run_id}")
    if keyword_exists:
        commands.append(f'aoa-course answer "course-specific question" --run {run_id}')
    return commands


def _load_json_file(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"_load_error": str(exc)}


def _json_load_error(payload: object) -> bool:
    return isinstance(payload, dict) and "_load_error" in payload


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys([item for item in items if item]))
