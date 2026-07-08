"""Read-only connector status packets for humans and agents."""

from __future__ import annotations

import json
import shlex
from collections import Counter
from pathlib import Path

from aoa_course_connector.adapters import adapter_list
from aoa_course_connector.calibration.connected_run import load_connected_calibration_status
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.index import LOCAL_HASHING_PROVIDER
from aoa_course_connector.readiness import connected_source_plan, live_preflight, semantic_provider_preflight
from aoa_course_connector.sources import load_registry, registry_path
from aoa_course_connector.stepik_options import DEFAULT_MAX_STEP_SOURCES, DEFAULT_STEP_SOURCE_TIMEOUT
from aoa_course_connector.storage import run_artifact_dir, run_data_dir, storage_status
from aoa_course_connector.sync import load_sync_status
from aoa_course_connector.sync.checkpoints import checkpoint_store_path


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
    "source_answer",
    "sources_answer",
    "sources_answer_matrix",
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
    max_step_sources: int | str | None = DEFAULT_MAX_STEP_SOURCES,
    step_source_timeout: float = DEFAULT_STEP_SOURCE_TIMEOUT,
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
    source_summary = _source_registry_summary(
        roots,
        registry,
        include_disabled=include_disabled,
        platforms=selected_platforms,
        source_ids=source_ids,
    )
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
        max_step_sources=max_step_sources,
        step_source_timeout=step_source_timeout,
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
    run_query_ready = any(
        bool(status.get("readiness", {}).get("agent_query_ready"))
        for status in run_statuses
        if isinstance(status.get("readiness"), dict)
    )
    source_connected_runs = source_summary.get("connected_runs") if isinstance(source_summary.get("connected_runs"), dict) else {}
    source_query_ready_entry_count = int(source_connected_runs.get("query_ready_entry_count") or 0)
    source_answer_ready_entry_count = int(source_connected_runs.get("answer_ready_entry_count") or 0)
    source_answer_probe_missing_entry_count = int(source_connected_runs.get("answer_probe_missing_entry_count") or 0)
    source_invalid_answer_ready_entry_count = int(source_connected_runs.get("invalid_answer_ready_entry_count") or 0)
    source_query_ready = source_query_ready_entry_count > 0
    query_ready = run_query_ready or source_query_ready
    lanes = {
        "repo_route_ready": not missing_route_files,
        "data_artifact_roots_ready": bool(storage_exists.get("data")) and bool(storage_exists.get("artifact")),
        "all_storage_roots_exist": all(bool(storage_exists.get(name)) for name in ["data", "cache", "auth", "artifact"]),
        "source_registry_configured": int(source_summary.get("selected_source_count", 0)) > 0,
        "run_agent_query_ready": run_query_ready,
        "source_registry_query_ready": source_query_ready,
        "source_registry_query_ready_entry_count": source_query_ready_entry_count,
        "source_registry_query_ready_source_count": len(source_connected_runs.get("source_ids_with_query_runs", [])) if isinstance(source_connected_runs.get("source_ids_with_query_runs"), list) else 0,
        "source_registry_answer_ready_entry_count": source_answer_ready_entry_count,
        "source_registry_answer_probe_missing_entry_count": source_answer_probe_missing_entry_count,
        "source_registry_invalid_answer_ready_entry_count": source_invalid_answer_ready_entry_count,
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
    include_connected_runs: bool = False,
    connected_run_limit: int = 3,
    connected_receipt_limit: int = 50,
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
    selected_catalog_ids = [str(source.get("source_id") or "") for source in selected_sources if source.get("source_id")]
    if include_connected_runs and selected_catalog_ids:
        connected_runs = connected_query_run_catalog(
            roots,
            source_ids=selected_catalog_ids,
            platforms=selected_platforms,
            include_source_refs=include_source_refs,
            per_source_limit=connected_run_limit,
            receipt_limit=connected_receipt_limit,
        )
    else:
        connected_runs = _empty_connected_query_run_catalog(
            roots,
            included=include_connected_runs,
            per_source_limit=connected_run_limit,
            receipt_limit=connected_receipt_limit,
        )
    connected_by_source = connected_runs.get("by_source_id") if isinstance(connected_runs.get("by_source_id"), dict) else {}
    catalog_sources: list[dict[str, object]] = []
    for source in selected_sources:
        source_id = str(source.get("source_id") or "")
        latest_runs = connected_by_source.get(source_id, []) if source_id else []
        item = {
            "source_id": source.get("source_id"),
            "platform": source.get("platform"),
            "title": source.get("title"),
            "access_mode": source.get("access_mode"),
            "enabled": source.get("enabled", True),
            "updated_at": source.get("updated_at"),
            "query_ready_connected_run_count": len(latest_runs),
            "latest_connected_runs": latest_runs,
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
        "connected_runs": _connected_query_run_catalog_summary(connected_runs),
        "sources": catalog_sources,
        "privacy": {
            "contains_secret_values": False,
            "secret_values_logged": False,
            "source_refs_included": bool(include_source_refs),
            "connected_run_refs_included": bool(include_connected_runs),
            "do_not_commit_runtime_registry": True,
        },
        "next_commands": [
            "aoa-course sources list",
            "aoa-course preflight connected-plan --live-scope bounded",
        ],
    }


def _source_registry_summary(
    roots: StorageRoots,
    registry: dict[str, object],
    *,
    include_disabled: bool,
    platforms: list[str] | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, object]:
    return source_registry_catalog(
        roots,
        registry,
        include_disabled=include_disabled,
        platforms=platforms,
        source_ids=source_ids,
        include_source_refs=False,
        include_connected_runs=True,
        connected_run_limit=5,
        connected_receipt_limit=50,
    )


def connected_query_run_catalog(
    roots: StorageRoots,
    *,
    source_ids: list[str] | None = None,
    platforms: list[str] | None = None,
    include_source_refs: bool = False,
    per_source_limit: int = 3,
    receipt_limit: int = 50,
) -> dict[str, object]:
    """Index query-ready entries from connected-run receipts by source id."""

    selected_ids = _dedupe([str(source_id) for source_id in (source_ids or []) if str(source_id)])
    selected_platforms = _dedupe([str(platform) for platform in (platforms or []) if str(platform)])
    by_source: dict[str, list[dict[str, object]]] = {}
    errors: list[dict[str, object]] = []
    receipt_paths = _connected_receipt_paths(roots, limit=max(1, int(receipt_limit or 1)))
    for path in receipt_paths:
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"path": str(path), "error": str(exc), "reason": exc.__class__.__name__})
            continue
        query_plan = receipt.get("query_plan") if isinstance(receipt.get("query_plan"), dict) else {}
        entries = query_plan.get("entries") if isinstance(query_plan.get("entries"), list) else []
        for entry in entries:
            if not isinstance(entry, dict) or not bool(entry.get("query_ready")):
                continue
            source_id = str(entry.get("source_id") or "")
            platform = str(entry.get("platform") or "")
            if not source_id:
                continue
            if selected_ids and source_id not in selected_ids:
                continue
            if selected_platforms and platform not in selected_platforms:
                continue
            by_source.setdefault(source_id, []).append(_connected_query_run_ref(receipt, path, entry, include_source_refs=include_source_refs))
    try:
        sync_checkpoints = _sync_query_checkpoints(roots, source_ids=selected_ids, platforms=selected_platforms)
    except (OSError, json.JSONDecodeError) as exc:
        sync_checkpoints = []
        errors.append(
            {
                "path": str(checkpoint_store_path(roots)),
                "error": str(exc),
                "reason": exc.__class__.__name__,
                "entry_source": "sync_checkpoint",
            }
        )
    for checkpoint in sync_checkpoints:
        source_id = str(checkpoint.get("source_id") or "")
        if source_id:
            by_source.setdefault(source_id, []).append(_sync_query_run_ref(checkpoint, include_source_refs=include_source_refs))
    per_source = max(1, int(per_source_limit or 1))
    for source_id, entries in list(by_source.items()):
        by_source[source_id] = sorted(entries, key=_connected_query_run_sort_key, reverse=True)[:per_source]
    flattened_entries = [entry for entries in by_source.values() for entry in entries]
    query_ready_count = len(flattened_entries)
    answer_ready_count = sum(1 for entry in flattened_entries if _query_run_answer_ready(entry))
    invalid_answer_ready_count = sum(1 for entry in flattened_entries if _query_run_invalid_answer_ready(entry))
    answer_probe_missing_count = query_ready_count - answer_ready_count
    return {
        "schema": "aoa_course_connected_query_run_catalog_v1",
        "included": True,
        "network_touched": False,
        "read_only": True,
        "path": str(roots.artifact / "runs"),
        "receipt_limit": max(1, int(receipt_limit or 1)),
        "per_source_limit": per_source,
        "receipt_count": len(receipt_paths),
        "sync_checkpoint_count": len(sync_checkpoints),
        "selected_source_ids": selected_ids,
        "selected_platforms": selected_platforms,
        "source_ids_with_query_runs": sorted(by_source),
        "query_ready_entry_count": query_ready_count,
        "answer_ready_entry_count": answer_ready_count,
        "answer_probe_missing_entry_count": answer_probe_missing_count,
        "invalid_answer_ready_entry_count": invalid_answer_ready_count,
        "error_count": len(errors),
        "errors": errors,
        "by_source_id": by_source,
    }


def _empty_connected_query_run_catalog(roots: StorageRoots, *, included: bool, per_source_limit: int, receipt_limit: int) -> dict[str, object]:
    return {
        "schema": "aoa_course_connected_query_run_catalog_v1",
        "included": included,
        "network_touched": False,
        "read_only": True,
        "path": str(roots.artifact / "runs"),
        "receipt_limit": max(1, int(receipt_limit or 1)),
        "per_source_limit": max(1, int(per_source_limit or 1)),
        "receipt_count": 0,
        "sync_checkpoint_count": 0,
        "selected_source_ids": [],
        "selected_platforms": [],
        "source_ids_with_query_runs": [],
        "query_ready_entry_count": 0,
        "answer_ready_entry_count": 0,
        "answer_probe_missing_entry_count": 0,
        "invalid_answer_ready_entry_count": 0,
        "error_count": 0,
        "errors": [],
        "by_source_id": {},
    }


def _connected_query_run_catalog_summary(catalog: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in catalog.items()
        if key != "by_source_id"
    }


def _connected_receipt_paths(roots: StorageRoots, *, limit: int) -> list[Path]:
    runs_dir = roots.artifact / "runs"
    if not runs_dir.exists():
        return []
    paths = [path for path in runs_dir.glob("*/connected/connected_calibration_receipt.json") if path.is_file()]
    return sorted(paths, key=lambda path: path.stat().st_mtime, reverse=True)[:limit]


def _sync_query_checkpoints(roots: StorageRoots, *, source_ids: list[str], platforms: list[str]) -> list[dict[str, object]]:
    status = load_sync_status(roots)
    checkpoints = status.get("checkpoints") if isinstance(status.get("checkpoints"), list) else []
    selected_ids = set(source_ids)
    selected_platforms = set(platforms)
    ready = []
    for item in checkpoints:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "")
        platform = str(item.get("platform") or "")
        if selected_ids and source_id not in selected_ids:
            continue
        if selected_platforms and platform not in selected_platforms:
            continue
        if item.get("status") != "ok":
            continue
        if not _path_is_file(item.get("index_path")):
            continue
        ready.append(item)
    return ready


def _connected_query_run_ref(receipt: dict[str, object], path: Path, entry: dict[str, object], *, include_source_refs: bool) -> dict[str, object]:
    commands = entry.get("commands") if isinstance(entry.get("commands"), dict) else {}
    commands = dict(commands)
    mcp_commands = entry.get("mcp_commands") if isinstance(entry.get("mcp_commands"), dict) else {}
    mcp_commands = dict(mcp_commands)
    source_id = str(entry.get("source_id") or "")
    if "sources_answer" not in commands:
        commands["sources_answer"] = _sources_answer_command(
            str(entry.get("query") or "<course-specific question>"),
            source_id=source_id,
            platform=str(entry.get("platform") or ""),
            kind=str(entry.get("kind") or ""),
            mode=str(entry.get("query_mode") or "keyword"),
        )
    if source_id and "source_answer" not in mcp_commands:
        mcp_commands["source_answer"] = _mcp_call_command(
            "source_answer",
            {
                "query": str(entry.get("query") or "<course-specific question>"),
                "source_id": source_id,
                "mode": str(entry.get("query_mode") or "keyword"),
            },
        )
    answer_result_count = int(entry.get("answer_result_count") or 0)
    answer_evidence_count = int(entry.get("answer_evidence_count") or 0)
    answer_ready = bool(entry.get("answer_ready"))
    payload = {
        "connected_run_id": receipt.get("run_id") or path.parent.parent.name,
        "connected_run_status": receipt.get("status") or "unknown",
        "connected_completed_at": receipt.get("completed_at"),
        "connected_started_at": receipt.get("started_at"),
        "receipt_path": str(path),
        "mode": receipt.get("mode"),
        "network_touched": bool(receipt.get("network_touched")),
        "kind": entry.get("kind"),
        "platform": entry.get("platform"),
        "run_id": entry.get("run_id"),
        "source_id": entry.get("source_id"),
        "title": entry.get("title"),
        "query": entry.get("query"),
        "query_mode": entry.get("query_mode"),
        "query_ready": bool(entry.get("query_ready")),
        "semantic_query_ready": bool(entry.get("semantic_query_ready")),
        "graph_ready": bool(entry.get("graph_ready")),
        "answer_ready": answer_ready,
        "answer_result_count": answer_result_count,
        "answer_evidence_count": answer_evidence_count,
        "answer_readiness_source": "cached_probe" if answer_ready else "not_cached",
        "paths": entry.get("paths") if isinstance(entry.get("paths"), dict) else {},
        "commands": commands,
        "mcp_commands": mcp_commands,
    }
    if include_source_refs:
        payload["source_ref"] = entry.get("source_ref")
    stable_identity = entry.get("stable_identity")
    if isinstance(stable_identity, dict):
        payload["stable_identity"] = _compact_stable_identity(stable_identity)
    return {key: value for key, value in payload.items() if value not in (None, "")}


def _sync_query_run_ref(checkpoint: dict[str, object], *, include_source_refs: bool) -> dict[str, object]:
    source_id = str(checkpoint.get("source_id") or "")
    platform = str(checkpoint.get("platform") or "")
    run_id = str(checkpoint.get("run_id") or "")
    query = "<course-specific question>"
    graph_ready = _path_is_file(checkpoint.get("graph_path"))
    semantic_ready = _path_is_file(checkpoint.get("semantic_index_path"))
    mode = "hybrid" if semantic_ready else "keyword"
    commands = {
        "query": f"aoa-course answer {shlex.quote(query)} --run {shlex.quote(run_id)} --mode {mode}",
        "sources_answer": _sources_answer_command(query, source_id=source_id, platform=platform, kind="sync", mode=mode),
        "lesson_context": f"aoa-course lesson-context {shlex.quote(query)} --run {shlex.quote(run_id)} --mode {mode} --graph-limit 12",
        "evidence_report": f"aoa-course evidence inspect {shlex.quote(query)} --run {shlex.quote(run_id)} --mode {mode}",
    }
    mcp_commands = {
        "answer": _mcp_call_command("answer", {"query": query, "run": run_id, "mode": mode}),
        "source_answer": _mcp_call_command("source_answer", {"query": query, "source_id": source_id, "mode": mode}),
        "lesson_context": _mcp_call_command("lesson_context", {"query": query, "run": run_id, "mode": mode, "graph_limit": 12}),
        "evidence_report": _mcp_call_command("evidence_report", {"query": query, "run": run_id, "mode": mode}),
    }
    payload = {
        "entry_source": "sync_checkpoint",
        "connected_run_id": checkpoint.get("sync_run_id") or run_id,
        "sync_run_id": checkpoint.get("sync_run_id"),
        "connected_run_status": checkpoint.get("status") or "unknown",
        "connected_completed_at": checkpoint.get("updated_at"),
        "receipt_path": checkpoint.get("receipt_path"),
        "mode": "sync",
        "network_touched": False,
        "kind": "sync",
        "platform": platform,
        "run_id": run_id,
        "source_id": source_id,
        "title": checkpoint.get("title"),
        "query": query,
        "query_mode": mode,
        "query_ready": True,
        "semantic_query_ready": semantic_ready,
        "graph_ready": graph_ready,
        "answer_ready": False,
        "answer_result_count": 0,
        "answer_evidence_count": 0,
        "answer_readiness_source": "not_cached",
        "answer_readiness_reason": "sync checkpoint has local query artifacts; run sources answer to evaluate grounded answer evidence",
        "paths": {
            "normalized": checkpoint.get("normalized_path"),
            "index": checkpoint.get("index_path"),
            "semantic_index": checkpoint.get("semantic_index_path"),
            "graph": checkpoint.get("graph_path"),
        },
        "commands": commands,
        "mcp_commands": mcp_commands,
    }
    if include_source_refs:
        payload["source_ref"] = checkpoint.get("source_ref")
    stable_identity = checkpoint.get("stable_identity")
    if isinstance(stable_identity, dict):
        payload["stable_identity"] = _compact_stable_identity(stable_identity)
    return {key: value for key, value in payload.items() if value not in (None, "")}


def _query_run_answer_ready(entry: dict[str, object]) -> bool:
    return (
        bool(entry.get("answer_ready"))
        and int(entry.get("answer_result_count") or 0) > 0
        and int(entry.get("answer_evidence_count") or 0) > 0
    )


def _query_run_invalid_answer_ready(entry: dict[str, object]) -> bool:
    return bool(entry.get("answer_ready")) and not _query_run_answer_ready(entry)


def _compact_stable_identity(stable_identity: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in {
            "schema": stable_identity.get("schema"),
            "available": stable_identity.get("available"),
            "fingerprint": stable_identity.get("fingerprint"),
            "counts": stable_identity.get("counts"),
        }.items()
        if value is not None
    }


def _connected_query_run_sort_key(item: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(item.get("connected_completed_at") or ""),
        str(item.get("connected_started_at") or ""),
        str(item.get("connected_run_id") or ""),
    )


def _path_is_file(value: object) -> bool:
    text = str(value or "")
    return bool(text) and Path(text).is_file()


def _mcp_call_command(tool: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    return f"aoa-course mcp call {tool} {shlex.quote(encoded)}"


def _sources_answer_command(query: str, *, source_id: str, platform: str, kind: str, mode: str) -> str:
    parts = ["aoa-course", "sources", "answer", shlex.quote(query)]
    if source_id:
        parts.extend(["--source-id", shlex.quote(source_id)])
    elif platform:
        parts.extend(["--platform", shlex.quote(platform)])
    if kind:
        parts.extend(["--kind", shlex.quote(kind)])
    if mode:
        parts.extend(["--mode", shlex.quote(mode)])
    return " ".join(parts)


def _sources_answer_matrix_command(queries: list[str], *, source_ids: list[str], platforms: list[str]) -> str:
    parts = ["aoa-course", "sources", "answer-matrix"]
    for query in queries:
        if query:
            parts.extend(["--query", shlex.quote(query)])
    for source_id in source_ids:
        if source_id:
            parts.extend(["--source-id", shlex.quote(source_id)])
    if not source_ids:
        for platform in platforms:
            if platform:
                parts.extend(["--platform", shlex.quote(platform)])
    parts.extend(["--mode", "hybrid"])
    return " ".join(parts)


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
        "max_step_sources": plan.get("max_step_sources"),
        "step_source_timeout": plan.get("step_source_timeout"),
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
    source_query_ready = _source_summary_query_ready(source_summary)
    if not all(bool(storage_exists.get(name)) for name in ["data", "cache", "auth", "artifact"]):
        commands.append("aoa-course init")
    runs_ready = not any(run_status.get("status") != "ready" for run_status in run_statuses)
    connected_run_status = str(connected_run.get("status") or "")
    if not runs_ready and not source_query_ready:
        commands.append(f"aoa-course bootstrap fixture --connected-run {connected_run_id}")
    elif connected_run_status == "missing" and not source_query_ready:
        commands.append(f"aoa-course bootstrap fixture --connected-run {connected_run_id}")
    elif connected_run_status not in {"ok", "missing"}:
        commands.extend(_connected_run_repair_commands(connected_run, connected_run_id))
    connected_run_repairing = connected_run_status not in {"", "ok", "missing"}
    if source_query_ready:
        commands.extend(_source_registry_query_commands(source_summary))
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


def _source_summary_query_ready(source_summary: dict[str, object]) -> bool:
    connected_runs = source_summary.get("connected_runs") if isinstance(source_summary.get("connected_runs"), dict) else {}
    return int(connected_runs.get("query_ready_entry_count") or 0) > 0


def _source_registry_query_commands(source_summary: dict[str, object]) -> list[str]:
    commands = ["aoa-course sources list --no-source-refs --connected-run-limit 5"]
    sources = source_summary.get("sources") if isinstance(source_summary.get("sources"), list) else []
    query_samples: list[str] = []
    selected_source_ids: list[str] = []
    selected_platforms = (
        [str(platform) for platform in source_summary.get("selected_platforms", []) if str(platform)]
        if isinstance(source_summary.get("selected_platforms"), list)
        else []
    )
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("source_id") or "")
        latest_runs = source.get("latest_connected_runs") if isinstance(source.get("latest_connected_runs"), list) else []
        if latest_runs and source_id:
            selected_source_ids.append(source_id)
        command_added = False
        for entry in latest_runs:
            if not isinstance(entry, dict):
                continue
            query = str(entry.get("query") or "")
            if query and not query.startswith("<") and query not in query_samples:
                query_samples.append(query)
            entry_commands = entry.get("commands") if isinstance(entry.get("commands"), dict) else {}
            command = str(entry_commands.get("sources_answer") or "")
            if command and not command_added and "<course-specific question>" not in command:
                commands.append(command)
                command_added = True
    if len(query_samples) >= 2:
        commands.append(_sources_answer_matrix_command(query_samples[:2], source_ids=selected_source_ids[:5], platforms=selected_platforms))
    return commands


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
