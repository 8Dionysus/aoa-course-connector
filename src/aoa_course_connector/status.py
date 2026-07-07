"""Read-only connector status packets for humans and agents."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from aoa_course_connector.adapters import adapter_list
from aoa_course_connector.calibration.connected_run import load_connected_calibration_status
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.index import LOCAL_HASHING_PROVIDER
from aoa_course_connector.readiness import connected_source_plan, live_preflight, semantic_provider_preflight
from aoa_course_connector.sources import load_registry, registry_path
from aoa_course_connector.storage import run_artifact_dir, run_data_dir, storage_status


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
    "semantic_provider_preflight",
    "connected_run",
    "connected_run_status",
    "connected_run_query",
    "connected_run_query_matrix",
    "refresh_plan",
    "search",
    "semantic_search",
    "hybrid_search",
    "answer",
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
    source_ids: list[str] | None = None,
    connected_run: str = DEFAULT_CONNECTED_RUN,
    stepik_token_env: str = "STEPIK_API_TOKEN",
    browser_state_file: Path | None = None,
    expect_origin_contains: str | None = None,
    include_disabled: bool = False,
    query: str | None = None,
    max_lessons: int = 50,
    max_pages: int = 5,
    max_sources: int = 50,
    link_pattern: str | None = None,
    live_scope: str = "bounded",
    include_step_sources: bool = False,
    semantic_provider: str = LOCAL_HASHING_PROVIDER,
    dimensions: int = 256,
    embedding_endpoint: str | None = None,
    embedding_model: str | None = None,
    embedding_token_env: str | None = "AOA_COURSE_EMBEDDING_TOKEN",
    embedding_batch_size: int = 32,
    embedding_timeout_seconds: float = 30.0,
    mcp_tool_names: list[str] | set[str] | None = None,
) -> dict[str, object]:
    """Build a single read-only route audit for install, query, and live plan."""

    selected_runs = _dedupe([str(run) for run in (runs or [DEFAULT_RUN]) if str(run)])
    selected_platforms = _dedupe([str(platform) for platform in (platforms or DEFAULT_PLATFORMS) if str(platform)])
    missing_route_files = [rel for rel in REQUIRED_ROUTE_FILES if not (repo_root / rel).exists()]
    storage = storage_status(repo_root, roots)
    registry = load_registry(roots.data)
    source_summary = _source_registry_summary(roots, registry, include_disabled=include_disabled, source_ids=source_ids)
    run_statuses = [ingest_status(roots, run_id) for run_id in selected_runs]
    preflight = live_preflight(
        roots,
        platforms=selected_platforms,
        source_ids=source_ids,
        stepik_token_env=stepik_token_env,
        browser_state_file=browser_state_file,
        expect_origin_contains=expect_origin_contains,
        include_disabled=include_disabled,
    )
    plan = connected_source_plan(
        roots,
        platforms=selected_platforms,
        source_ids=source_ids,
        stepik_token_env=stepik_token_env,
        browser_state_file=browser_state_file,
        expect_origin_contains=expect_origin_contains,
        include_disabled=include_disabled,
        query=query,
        max_lessons=max_lessons,
        max_pages=max_pages,
        max_sources=max_sources,
        link_pattern=link_pattern,
        live_scope=live_scope,
        include_step_sources=include_step_sources,
    )
    semantic_preflights = [
        semantic_provider_preflight(
            roots,
            run_id=run_id,
            provider=semantic_provider,
            dimensions=dimensions,
            embedding_endpoint=embedding_endpoint,
            embedding_model=embedding_model,
            embedding_token_env=embedding_token_env,
            embedding_batch_size=embedding_batch_size,
            embedding_timeout_seconds=embedding_timeout_seconds,
        )
        for run_id in selected_runs
    ]
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
        "source_registry_configured": int(source_summary.get("selected_source_count", 0)) > 0,
        "agent_query_ready": query_ready,
        "connected_live_ready": bool(plan.get("ready")),
        "semantic_provider_ready": all(bool(item.get("ready")) for item in semantic_preflights),
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
        "connected_live_ready": bool(lanes["connected_live_ready"]),
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
        "semantic_provider_preflight": [_compact_semantic_provider_preflight(item) for item in semantic_preflights],
        "connected_run": connected_status,
        "mcp": mcp,
        "lanes": lanes,
        "next_commands": _next_commands(
            storage_exists=storage_exists,
            source_summary=source_summary,
            run_statuses=run_statuses,
            preflight=preflight,
            connected_plan=plan,
            semantic_preflights=semantic_preflights,
            connected_run=connected_status,
            mcp=mcp,
        ),
    }


def ingest_status(roots: StorageRoots, run_id: str) -> dict[str, object]:
    """Inspect one local run without reading raw private payloads."""

    data_dir = run_data_dir(roots, run_id)
    artifact_dir = run_artifact_dir(roots, run_id)
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
    normalized_ready = _artifact_status_ok(normalized)
    keyword_ready = _artifact_status_ok(keyword)
    semantic_ready = _artifact_status_ok(semantic)
    graph_ready = _artifact_status_ok(graph)
    ready = normalized_ready and keyword_ready and graph_ready
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
            "normalized_ready": normalized_ready,
            "query_ready": keyword_ready,
            "semantic_query_ready": semantic_ready,
            "graph_ready": graph_ready,
            "agent_query_ready": ready,
        },
        "next_commands": _ingest_status_next_commands(
            run_id,
            normalized_ready=normalized_ready,
            keyword_ready=keyword_ready,
            semantic_ready=semantic_ready,
            graph_ready=graph_ready,
        ),
    }


def source_registry_catalog(
    roots: StorageRoots,
    registry: dict[str, object] | None = None,
    *,
    include_disabled: bool = False,
    platforms: list[str] | None = None,
    source_ids: list[str] | None = None,
    include_source_refs: bool = True,
) -> dict[str, object]:
    """Return a read-only, secret-free catalog view of configured sources."""

    registry_data = registry or load_registry(roots.data)
    selected_platforms = _dedupe([str(platform) for platform in (platforms or []) if str(platform)])
    selected_ids = _dedupe([str(source_id) for source_id in (source_ids or []) if str(source_id)])
    sources = [source for source in registry_data.get("sources", []) if isinstance(source, dict)]
    selected_sources = [
        source
        for source in sources
        if (include_disabled or source.get("enabled", True))
        and (not selected_platforms or str(source.get("platform") or "") in selected_platforms)
        and (not selected_ids or str(source.get("source_id") or "") in selected_ids)
    ]
    available_ids = {str(source.get("source_id") or "") for source in sources}
    platform_counts = Counter(str(source.get("platform") or "unknown") for source in selected_sources)
    access_mode_counts = Counter(str(source.get("access_mode") or "unknown") for source in selected_sources)
    catalog_sources: list[dict[str, object]] = []
    for source in selected_sources:
        item = {
            "source_id": source.get("source_id"),
            "platform": source.get("platform"),
            "title": source.get("title"),
            "access_mode": source.get("access_mode"),
            "enabled": source.get("enabled", True),
            "updated_at": source.get("updated_at"),
        }
        if include_source_refs:
            item["source_ref"] = source.get("source_ref")
        catalog_sources.append(item)
    return {
        "schema": "aoa_course_source_registry_list_v1",
        "registry_schema": registry_data.get("schema"),
        "path": str(registry_path(roots.data)),
        "exists": registry_path(roots.data).exists(),
        "network_touched": False,
        "read_only": True,
        "contains_secret_values": False,
        "secret_values_logged": False,
        "source_refs_included": bool(include_source_refs),
        "include_disabled": bool(include_disabled),
        "selected_platforms": selected_platforms,
        "selected_source_ids": selected_ids,
        "missing_source_ids": [source_id for source_id in selected_ids if source_id not in available_ids],
        "source_count": len(sources),
        "enabled_source_count": len([source for source in sources if source.get("enabled", True)]),
        "selected_source_count": len(selected_sources),
        "platform_counts": dict(sorted(platform_counts.items())),
        "access_mode_counts": dict(sorted(access_mode_counts.items())),
        "sources": catalog_sources,
        "privacy": {
            "contains_secret_values": False,
            "secret_values_logged": False,
            "source_refs_included": bool(include_source_refs),
            "do_not_commit_runtime_registry": True,
        },
        "next_commands": [
            "aoa-course sources list",
            "aoa-course preflight connected-plan --live-scope bounded",
        ],
    }


def _source_registry_summary(roots: StorageRoots, registry: dict[str, object], *, include_disabled: bool, source_ids: list[str] | None = None) -> dict[str, object]:
    return source_registry_catalog(
        roots,
        registry,
        include_disabled=include_disabled,
        source_ids=source_ids,
        include_source_refs=False,
    )


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
        "schema": preflight.get("schema") or "aoa_course_semantic_provider_preflight_v1",
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
        "include_step_sources": bool(plan.get("include_step_sources")),
        "max_lessons": plan.get("max_lessons"),
        "max_pages": plan.get("max_pages"),
        "max_sources": plan.get("max_sources"),
        "link_pattern": plan.get("link_pattern", ""),
        "platforms": plan.get("platforms", []),
        "source_registry": plan.get("source_registry"),
        "platform_plans": plan.get("platform_plans", []),
        "browser_auth_plans": plan.get("browser_auth_plans", []),
        "connected_run_plan": plan.get("connected_run_plan", {}),
        "next_commands": plan.get("next_commands", []),
    }


def _compact_semantic_provider_preflight(preflight: dict[str, object]) -> dict[str, object]:
    config = preflight.get("provider_config") if isinstance(preflight.get("provider_config"), dict) else {}
    return {
        "schema": preflight.get("schema"),
        "status": preflight.get("status"),
        "ready": bool(preflight.get("ready")),
        "network_touched": bool(preflight.get("network_touched")),
        "run_id": preflight.get("run_id"),
        "provider": preflight.get("provider"),
        "normalized_path": preflight.get("storage", {}).get("normalized_path") if isinstance(preflight.get("storage"), dict) else None,
        "semantic_index_path": preflight.get("storage", {}).get("semantic_index_path") if isinstance(preflight.get("storage"), dict) else None,
        "semantic_index_exists": bool(preflight.get("storage", {}).get("semantic_index_exists")) if isinstance(preflight.get("storage"), dict) else False,
        "semantic_index_ready": bool(preflight.get("semantic_index_ready")),
        "endpoint_configured": bool(config.get("endpoint_configured")),
        "model_configured": bool(config.get("model_configured")),
        "token_env": config.get("token_env"),
        "token_env_present": bool(config.get("token_env_present")),
        "secret_values_logged": bool(config.get("secret_values_logged")),
        "next_commands": preflight.get("next_commands", []),
    }


def _next_commands(
    *,
    storage_exists: dict[str, object],
    source_summary: dict[str, object],
    run_statuses: list[dict[str, object]],
    preflight: dict[str, object],
    connected_plan: dict[str, object],
    semantic_preflights: list[dict[str, object]],
    connected_run: dict[str, object],
    mcp: dict[str, object],
) -> list[str]:
    commands: list[str] = []
    connected_run_id = str(connected_run.get("run_id") or DEFAULT_CONNECTED_RUN)
    if not all(bool(storage_exists.get(name)) for name in ["data", "cache", "auth", "artifact"]):
        commands.append("aoa-course init")
    runs_ready = not any(run_status.get("status") != "ready" for run_status in run_statuses)
    connected_run_status = str(connected_run.get("status") or "")
    if not runs_ready:
        commands.append(f"aoa-course bootstrap fixture --connected-run {connected_run_id}")
    elif connected_run_status == "missing":
        commands.append(f"aoa-course bootstrap fixture --connected-run {connected_run_id}")
    elif connected_run_status != "ok":
        commands.extend(_connected_run_repair_commands(connected_run, connected_run_id))
    connected_run_repairing = connected_run_status not in {"", "ok", "missing"}
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
    if bool(connected_plan.get("ready")):
        plan = connected_plan.get("connected_run_plan") if isinstance(connected_plan.get("connected_run_plan"), dict) else {}
        command = str(plan.get("command") or "")
        if command and not connected_run_repairing:
            commands.append(command)
    else:
        commands.extend([str(command) for command in connected_plan.get("next_commands", []) if str(command)])
    for semantic_preflight in semantic_preflights:
        storage = semantic_preflight.get("storage") if isinstance(semantic_preflight.get("storage"), dict) else {}
        semantic_index_exists = bool(storage.get("semantic_index_exists"))
        if not bool(semantic_preflight.get("ready")) or not semantic_index_exists:
            provider = str(semantic_preflight.get("provider") or LOCAL_HASHING_PROVIDER)
            run_id = str(semantic_preflight.get("run_id") or DEFAULT_RUN)
            if provider != LOCAL_HASHING_PROVIDER:
                commands = _drop_default_semantic_build_commands(commands, run_id)
            commands.extend([str(command) for command in semantic_preflight.get("next_commands", []) if str(command)])
    if not bool(mcp.get("ready")):
        commands.append("aoa-course mcp tools")
    readiness_command = "aoa-course readiness --run starter-fixture"
    if connected_run_id != DEFAULT_CONNECTED_RUN:
        readiness_command = f"{readiness_command} --connected-run {connected_run_id}"
    commands.append(readiness_command)
    return _dedupe(commands)


def _connected_run_repair_commands(connected_run: dict[str, object], connected_run_id: str) -> list[str]:
    commands: list[str] = []
    lanes = connected_run.get("repair_lanes") if isinstance(connected_run.get("repair_lanes"), list) else []
    for lane in lanes:
        if not isinstance(lane, dict):
            continue
        commands.extend([str(command) for command in lane.get("next_commands", []) if str(command)])
    if commands:
        return commands
    return [f"aoa-course calibration status --run {connected_run_id}"]


def _drop_default_semantic_build_commands(commands: list[str], run_id: str) -> list[str]:
    default_build = f"aoa-course build-semantic-index --run {run_id}"
    explicit_local_prefix = f"{default_build} --provider {LOCAL_HASHING_PROVIDER}"

    def is_default_semantic_build(command: str) -> bool:
        return (
            command == default_build
            or command == explicit_local_prefix
            or command.startswith(f"{explicit_local_prefix} ")
        )

    return [command for command in commands if not is_default_semantic_build(command)]


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
        "status": "ok",
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
    normalized_ready: bool,
    keyword_ready: bool,
    semantic_ready: bool,
    graph_ready: bool,
) -> list[str]:
    if not normalized_ready:
        if run_id == "starter-fixture":
            return [f"aoa-course materialize fixture --run {run_id}"]
        return [
            "aoa-course sources list",
            "aoa-course sync status",
            f"run an ingest, materialize, crawl, or source sync command that writes data/runs/{run_id}/normalized/course_bundle.json",
        ]
    commands: list[str] = []
    if not keyword_ready:
        commands.append(f"aoa-course build-index --run {run_id}")
    if not semantic_ready:
        commands.append(f"aoa-course build-semantic-index --run {run_id}")
    if not graph_ready:
        commands.append(f"aoa-course build-graph --run {run_id}")
    if keyword_ready:
        commands.append(f'aoa-course answer "course-specific question" --run {run_id}')
    return commands


def _artifact_status_ok(status: dict[str, object]) -> bool:
    return bool(status.get("exists")) and status.get("status") == "ok"


def _load_json_file(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"_load_error": str(exc)}


def _json_load_error(payload: object) -> bool:
    return isinstance(payload, dict) and "_load_error" in payload


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys([item for item in items if item]))
