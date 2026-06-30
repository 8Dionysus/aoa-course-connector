"""Agent-facing query refresh cycles."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index, build_semantic_index
from aoa_course_connector.query import render_answer_packet
from aoa_course_connector.readiness import connected_source_plan
from aoa_course_connector.sources import load_registry
from aoa_course_connector.sync import sync_browser_fixture_sources, sync_browser_live_sources, sync_stepik_fixture_sources, sync_stepik_live_sources


BROWSER_PLATFORMS = {"getcourse", "skillspace"}
CONNECTED_PLATFORMS = {"getcourse", "skillspace", "stepik"}
REFRESH_STRATEGIES = {"plan", "fixture", "live"}


def refresh_query_cycle(
    roots: StorageRoots,
    query: str,
    *,
    run_id: str = "starter-fixture",
    mode: str = "hybrid",
    limit: int = 5,
    strategy: str = "plan",
    execute: bool = False,
    source_id: str | None = None,
    sync_run_id: str | None = None,
    allow_network: bool = False,
    state_file: Path | None = None,
    stepik_token_env: str = "STEPIK_API_TOKEN",
    max_lessons: int = 20,
    max_sections: int | None = 1,
    max_units_per_section: int | None = 2,
    max_steps_per_lesson: int | None = 5,
    batch_size: int = 20,
    include_step_sources: bool = False,
) -> dict[str, object]:
    """Plan or execute a query refresh cycle from current answer evidence."""

    selected_strategy = _strategy(strategy)
    current_packet = render_answer_packet(roots, query, run_id=run_id, limit=limit, mode=mode)
    result = _select_result(current_packet, source_id=source_id)
    base = _base_report(
        query=query,
        run_id=run_id,
        mode=mode,
        limit=limit,
        strategy=selected_strategy,
        execute=execute,
        allow_network=allow_network,
        current_packet=current_packet,
        selected_result=result,
    )
    if not result:
        return {**base, "status": "blocked", "blocked_by": ["no_query_results"]}

    selected_source_id = str(result.get("source_id") or "")
    platform = str(result.get("platform") or "")
    registry_source = _registry_source(roots, selected_source_id)
    hint = result.get("refresh_hint") if isinstance(result.get("refresh_hint"), dict) else {}
    base["refresh_hint"] = hint
    base["connected_plan"] = _connected_plan_for_hint(
        roots,
        platform=platform,
        query=query,
        state_file=state_file,
        stepik_token_env=stepik_token_env,
    )
    if not execute:
        return {**base, "status": "planned", "blocked_by": _plan_blockers(platform, registry_source)}
    if selected_strategy == "plan":
        return {**base, "status": "blocked", "blocked_by": ["execute_requires_fixture_or_live_strategy"]}
    if not registry_source:
        return {**base, "status": "blocked", "blocked_by": ["source_not_found_in_local_registry"]}
    if platform not in CONNECTED_PLATFORMS:
        return {**base, "status": "blocked", "blocked_by": ["unsupported_refresh_platform"]}
    if selected_strategy == "live" and not allow_network:
        return {**base, "status": "blocked", "blocked_by": ["live_refresh_requires_allow_network"]}
    if selected_strategy == "live" and not _selected_source_live_ready(
        base.get("connected_plan"),
        selected_source_id,
    ):
        return {**base, "status": "blocked", "blocked_by": ["live_refresh_requires_ready_selected_source"]}

    sync_run = sync_run_id or _default_sync_run(selected_strategy, platform, run_id)
    sync_receipt = _execute_sync(
        roots,
        source=registry_source,
        strategy=selected_strategy,
        sync_run_id=sync_run,
        allow_network=allow_network,
        state_file=state_file,
        stepik_token_env=stepik_token_env,
        max_lessons=max_lessons,
        max_sections=max_sections,
        max_units_per_section=max_units_per_section,
        max_steps_per_lesson=max_steps_per_lesson,
        batch_size=batch_size,
        include_step_sources=include_step_sources,
    )
    checkpoint = _synced_checkpoint(sync_receipt, selected_source_id)
    if not checkpoint:
        return {
            **base,
            "status": "error" if sync_receipt.get("status") == "error" else "partial",
            "sync_receipt": sync_receipt,
            "blocked_by": ["sync_did_not_produce_ok_checkpoint_for_source"],
            "network_touched": bool(sync_receipt.get("network_touched")),
        }

    refreshed_run = str(checkpoint.get("run_id") or "")
    rebuilt = _rebuild_artifacts(roots, refreshed_run, mode=mode)
    refreshed_packet = render_answer_packet(roots, query, run_id=refreshed_run, limit=limit, mode=mode)
    return {
        **base,
        "status": "ok",
        "network_touched": bool(sync_receipt.get("network_touched")),
        "sync_run_id": sync_run,
        "sync_receipt": sync_receipt,
        "checkpoint": checkpoint,
        "refreshed_run_id": refreshed_run,
        "rebuilt_artifacts": rebuilt,
        "refreshed_answer_packet": refreshed_packet,
        "comparison": _comparison(current_packet, refreshed_packet, selected_source_id),
    }


def _base_report(
    *,
    query: str,
    run_id: str,
    mode: str,
    limit: int,
    strategy: str,
    execute: bool,
    allow_network: bool,
    current_packet: dict[str, object],
    selected_result: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "schema": "aoa_course_refresh_cycle_v1",
        "generated_at": _now(),
        "query": query,
        "run_id": run_id,
        "mode": mode,
        "limit": limit,
        "strategy": strategy,
        "execute": execute,
        "allow_network": allow_network,
        "network_touched": False,
        "read_only": not execute,
        "current_answer_packet": current_packet,
        "selected_result": _result_ref(selected_result),
        "planned_commands": _planned_commands(selected_result),
    }


def _select_result(packet: dict[str, object], *, source_id: str | None) -> dict[str, object] | None:
    results = packet.get("results") if isinstance(packet.get("results"), list) else []
    typed = [result for result in results if isinstance(result, dict)]
    if source_id:
        return next((result for result in typed if str(result.get("source_id") or "") == source_id), None)
    return typed[0] if typed else None


def _result_ref(result: dict[str, object] | None) -> dict[str, object] | None:
    if not result:
        return None
    return {
        "doc_id": result.get("doc_id"),
        "source_id": result.get("source_id"),
        "source_url": result.get("source_url"),
        "platform": result.get("platform"),
        "path": result.get("path"),
        "fetched_at": result.get("fetched_at"),
        "freshness_state": result.get("freshness_state"),
        "authority_tier": result.get("authority_tier"),
        "score": result.get("score"),
        "rank_score": result.get("rank_score"),
    }


def _planned_commands(result: dict[str, object] | None) -> dict[str, object]:
    if not result:
        return {"local_rebuild_commands": [], "source_commands": []}
    hint = result.get("refresh_hint") if isinstance(result.get("refresh_hint"), dict) else {}
    source_refresh = hint.get("source_refresh") if isinstance(hint.get("source_refresh"), dict) else {}
    return {
        "local_rebuild_commands": [str(command) for command in hint.get("local_rebuild_commands", []) if command],
        "source_commands": [
            str(source_refresh.get(key))
            for key in ["preflight_command", "register_command", "sync_command", "status_command"]
            if source_refresh.get(key)
        ],
    }


def _connected_plan_for_hint(
    roots: StorageRoots,
    *,
    platform: str,
    query: str,
    state_file: Path | None,
    stepik_token_env: str,
) -> dict[str, object] | None:
    if platform not in CONNECTED_PLATFORMS:
        return None
    return connected_source_plan(
        roots,
        platforms=[platform],
        query=query,
        browser_state_file=state_file,
        stepik_token_env=stepik_token_env,
        live_scope="bounded",
    )


def _plan_blockers(platform: str, source: dict[str, object] | None) -> list[str]:
    blockers: list[str] = []
    if platform not in CONNECTED_PLATFORMS:
        blockers.append("no_connected_live_adapter")
    if not source:
        blockers.append("source_not_found_in_local_registry")
    return blockers


def _registry_source(roots: StorageRoots, source_id: str) -> dict[str, object] | None:
    if not source_id:
        return None
    registry = load_registry(roots.data)
    for source in registry.get("sources", []):
        if isinstance(source, dict) and str(source.get("source_id") or "") == source_id:
            return source
    return None


def _execute_sync(
    roots: StorageRoots,
    *,
    source: dict[str, object],
    strategy: str,
    sync_run_id: str,
    allow_network: bool,
    state_file: Path | None,
    stepik_token_env: str,
    max_lessons: int,
    max_sections: int | None,
    max_units_per_section: int | None,
    max_steps_per_lesson: int | None,
    batch_size: int,
    include_step_sources: bool,
) -> dict[str, object]:
    platform = str(source.get("platform") or "")
    source_id = str(source.get("source_id") or "")
    if strategy == "fixture" and platform in BROWSER_PLATFORMS:
        return sync_browser_fixture_sources(
            roots,
            sync_run_id=sync_run_id,
            platforms=[platform],
            source_ids=[source_id],
            max_lessons=max_lessons,
            build_artifacts=True,
        )
    if strategy == "fixture" and platform == "stepik":
        return sync_stepik_fixture_sources(
            roots,
            sync_run_id=sync_run_id,
            source_ids=[source_id],
            build_artifacts=True,
        )
    if strategy == "live" and platform in BROWSER_PLATFORMS:
        return sync_browser_live_sources(
            roots,
            sync_run_id=sync_run_id,
            platforms=[platform],
            source_ids=[source_id],
            state_file=_browser_live_state_file(roots, platform, state_file),
            max_lessons=max_lessons,
            build_artifacts=True,
        )
    if strategy == "live" and platform == "stepik":
        return sync_stepik_live_sources(
            roots,
            sync_run_id=sync_run_id,
            token_env=stepik_token_env,
            max_sections=max_sections,
            max_units_per_section=max_units_per_section,
            max_steps_per_lesson=max_steps_per_lesson,
            batch_size=batch_size,
            include_step_sources=include_step_sources,
            source_ids=[source_id],
            build_artifacts=True,
        )
    return {
        "schema": "aoa_course_sync_receipt_v1",
        "status": "error",
        "sync_run_id": sync_run_id,
        "source_count": 1,
        "synced_sources": [],
        "failed_sources": [{"source_id": source_id, "platform": platform, "status": "error", "error": f"unsupported {strategy} refresh"}],
        "network_touched": strategy == "live" and allow_network,
    }


def _synced_checkpoint(sync_receipt: dict[str, object], source_id: str) -> dict[str, object] | None:
    synced = sync_receipt.get("synced_sources") if isinstance(sync_receipt.get("synced_sources"), list) else []
    for checkpoint in synced:
        if isinstance(checkpoint, dict) and checkpoint.get("status") == "ok" and str(checkpoint.get("source_id") or "") == source_id:
            return checkpoint
    return None


def _selected_source_live_ready(plan: object, source_id: str) -> bool:
    if not isinstance(plan, dict):
        return False
    source_plans = plan.get("source_plans")
    if isinstance(source_plans, list):
        for source_plan in source_plans:
            if not isinstance(source_plan, dict):
                continue
            if str(source_plan.get("source_id") or "") == source_id:
                return bool(source_plan.get("ready")) and bool(source_plan.get("sync_command"))
    return bool(plan.get("ready"))


def _browser_live_state_file(roots: StorageRoots, platform: str, state_file: Path | None) -> Path:
    return (state_file or roots.auth / platform / "account.storage-state.json").expanduser().resolve()


def _rebuild_artifacts(roots: StorageRoots, run_id: str, *, mode: str) -> dict[str, object]:
    paths: dict[str, object] = {
        "keyword_index_path": str(build_keyword_index(roots, run_id=run_id)),
        "graph_path": str(build_graph(roots, run_id=run_id)),
    }
    if mode in {"semantic", "hybrid"}:
        paths["semantic_index_path"] = str(build_semantic_index(roots, run_id=run_id))
    return paths


def _comparison(current_packet: dict[str, object], refreshed_packet: dict[str, object], source_id: str) -> dict[str, object]:
    current_top = _result_ref(_select_result(current_packet, source_id=source_id))
    refreshed_top = _result_ref(_select_result(refreshed_packet, source_id=source_id))
    return {
        "current_result_count": current_packet.get("result_count"),
        "refreshed_result_count": refreshed_packet.get("result_count"),
        "current_top": current_top,
        "refreshed_top": refreshed_top,
        "source_id_preserved": bool(current_top and refreshed_top and current_top.get("source_id") == refreshed_top.get("source_id")),
        "refreshed_has_evidence": bool(refreshed_packet.get("evidence_chain")),
        "refreshed_freshness_states": refreshed_packet.get("freshness_report", {}).get("states") if isinstance(refreshed_packet.get("freshness_report"), dict) else [],
    }


def _strategy(strategy: str) -> str:
    selected = str(strategy or "plan")
    if selected not in REFRESH_STRATEGIES:
        raise ValueError(f"unsupported refresh strategy: {selected}")
    return selected


def _default_sync_run(strategy: str, platform: str, run_id: str) -> str:
    return f"refresh-{strategy}-{_slug(platform)}-{_slug(run_id)}"


def _slug(value: object) -> str:
    text = str(value or "").casefold()
    slug = "".join(ch if ch.isalnum() else "-" for ch in text).strip("-")
    return slug or "item"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
