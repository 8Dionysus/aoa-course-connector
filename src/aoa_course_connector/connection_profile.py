"""Local connection-profile plan for operator-owned course sources."""

from __future__ import annotations

import json
import shlex
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from aoa_course_connector.auth import default_browser_state_path, inspect_browser_state
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.index import HTTP_JSON_PROVIDER, LOCAL_HASHING_PROVIDER
from aoa_course_connector.readiness import connected_source_plan, semantic_provider_preflight
from aoa_course_connector.sources import load_registry, upsert_source
from aoa_course_connector.stepik_options import (
    DEFAULT_MAX_STEP_SOURCES,
    DEFAULT_STEP_SOURCE_TIMEOUT,
    max_step_sources_packet,
    normalize_max_step_sources,
    normalize_step_source_timeout,
)


BROWSER_PLATFORMS = {"getcourse", "skillspace"}
CONNECTED_PLATFORMS = {"getcourse", "skillspace", "stepik"}
SEMANTIC_PROVIDERS = {LOCAL_HASHING_PROVIDER, HTTP_JSON_PROVIDER}
MCP_INSPECT_TOOL = "connection_profile_inspect"
MCP_STATUS_TOOL = "connection_profile_status"


def default_connection_profile_path(artifact_root: Path, name: str) -> Path:
    return artifact_root / "connections" / f"{_slug(name)}.connection-profile.json"


def build_connection_profile(
    roots: StorageRoots,
    *,
    name: str = "operator-connection",
    getcourse_urls: list[str] | None = None,
    skillspace_urls: list[str] | None = None,
    stepik_course_ids: list[str] | None = None,
    getcourse_state_file: Path | None = None,
    skillspace_state_file: Path | None = None,
    stepik_token_env: str = "STEPIK_API_TOKEN",
    run_id: str = "connected-calibration",
    query: str | None = None,
    live_scope: str = "bounded",
    include_step_sources: bool = False,
    max_step_sources: int | str | None = DEFAULT_MAX_STEP_SOURCES,
    step_source_timeout: float = DEFAULT_STEP_SOURCE_TIMEOUT,
    max_lessons: int = 50,
    max_pages: int = 5,
    max_sources: int = 50,
    link_pattern: str | None = None,
    semantic_provider: str = LOCAL_HASHING_PROVIDER,
    dimensions: int = 256,
    embedding_endpoint: str | None = None,
    embedding_model: str | None = None,
    embedding_token_env: str = "AOA_COURSE_EMBEDDING_TOKEN",
    embedding_batch_size: int = 32,
    embedding_timeout_seconds: float = 30.0,
) -> dict[str, object]:
    """Build a redacted local connection profile without touching the network."""

    selected_provider = _selected_semantic_provider(semantic_provider)
    selected_max_step_sources = normalize_max_step_sources(max_step_sources)
    selected_step_source_timeout = normalize_step_source_timeout(step_source_timeout)
    browser_sources = [
        *_browser_sources("getcourse", getcourse_urls or [], roots.auth, getcourse_state_file),
        *_browser_sources("skillspace", skillspace_urls or [], roots.auth, skillspace_state_file),
    ]
    stepik_sources = [
        {
            "platform": "stepik",
            "source_ref": str(course_id),
            "course_id": str(course_id),
            "title": f"Stepik course {course_id}",
            "access_mode": "api_token",
            "token_env": stepik_token_env,
            "enabled": True,
        }
        for course_id in _dedupe([str(item).strip() for item in (stepik_course_ids or []) if str(item).strip()])
    ]
    platforms = _dedupe([str(item.get("platform")) for item in [*browser_sources, *stepik_sources]])
    return {
        "schema": "aoa_course_connection_profile_v1",
        "name": name,
        "created_at": _now(),
        "network_touched": False,
        "read_only": True,
        "redacted": True,
        "secret_values_logged": False,
        "contains_operator_source_refs": bool(browser_sources or stepik_sources),
        "storage": {
            "mode": roots.mode,
            "data": str(roots.data),
            "auth": str(roots.auth),
            "artifact": str(roots.artifact),
            "cache": str(roots.cache),
        },
        "sources": [*browser_sources, *stepik_sources],
        "platforms": platforms,
        "runtime": {
            "run_id": run_id,
            "query": query or "",
            "live_scope": live_scope,
            "include_step_sources": include_step_sources,
            "max_step_sources": max_step_sources_packet(selected_max_step_sources),
            "step_source_timeout": selected_step_source_timeout,
            "max_lessons": max(1, int(max_lessons or 1)),
            "max_pages": max(1, int(max_pages or 1)),
            "max_sources": max(1, int(max_sources or 1)),
            "link_pattern": link_pattern or "",
        },
        "semantic_provider": {
            "provider": selected_provider,
            "dimensions": max(8, int(dimensions or 256)),
            "endpoint": embedding_endpoint or "",
            "model": embedding_model or "",
            "token_env": embedding_token_env,
            "batch_size": max(1, int(embedding_batch_size or 1)),
            "timeout_seconds": float(embedding_timeout_seconds or 30.0),
            "token_value_logged": False,
        },
    }


def write_connection_profile(profile: dict[str, object], path: Path) -> dict[str, object]:
    target = path.expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profile, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "schema": "aoa_course_connection_profile_write_v1",
        "status": "ok",
        "path": str(target),
        "written": True,
        "network_touched": False,
        "redacted": True,
    }


def load_connection_profile(path: Path) -> dict[str, object]:
    profile = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise ValueError("connection profile root must be a JSON object")
    if profile.get("schema") != "aoa_course_connection_profile_v1":
        raise ValueError("unsupported connection profile schema")
    return profile


def inspect_connection_profile(roots: StorageRoots, profile: dict[str, object], *, profile_path: Path | None = None) -> dict[str, object]:
    """Inspect a profile and produce the next local commands without mutation."""

    sources = _profile_sources(profile)
    runtime = profile.get("runtime") if isinstance(profile.get("runtime"), dict) else {}
    semantic = profile.get("semantic_provider") if isinstance(profile.get("semantic_provider"), dict) else {}
    registry = load_registry(roots.data)
    source_plans = [_source_plan(roots, registry, source) for source in sources]
    selected_source_ids = [
        str(item.get("source_id"))
        for item in source_plans
        if item.get("registered") and item.get("source_id")
    ]
    platforms = _dedupe([str(source.get("platform")) for source in sources if str(source.get("platform") or "") in CONNECTED_PLATFORMS])
    browser_plans = [
        _browser_plan(roots, source, source_id=_source_id_for_profile_source(source_plans, source))
        for source in sources
        if source.get("platform") in BROWSER_PLATFORMS
    ]
    connected_plans = _connected_plans(roots, source_plans, runtime)
    semantic_preflight = semantic_provider_preflight(
        roots,
        run_id=str(runtime.get("run_id") or "connected-calibration"),
        provider=str(semantic.get("provider") or LOCAL_HASHING_PROVIDER),
        dimensions=int(semantic.get("dimensions") or 256),
        embedding_endpoint=str(semantic.get("endpoint") or "") or None,
        embedding_model=str(semantic.get("model") or "") or None,
        embedding_token_env=str(semantic.get("token_env") or "AOA_COURSE_EMBEDDING_TOKEN"),
        embedding_batch_size=int(semantic.get("batch_size") or 32),
        embedding_timeout_seconds=float(semantic.get("timeout_seconds") or 30.0),
    )
    apply_command = _apply_command(profile_path)
    live_readiness = _live_readiness(
        source_plans=source_plans,
        browser_plans=browser_plans,
        connected_plans=connected_plans,
        semantic_preflight=semantic_preflight,
        apply_command=apply_command,
    )
    next_commands = _dedupe([str(command) for command in live_readiness.get("next_commands", []) if str(command)])
    return {
        "schema": "aoa_course_connection_profile_inspection_v1",
        "status": "ok",
        "profile": {
            "name": profile.get("name"),
            "path": str(profile_path) if profile_path else "",
            "source_count": len(sources),
            "platforms": platforms,
            "operator_source_refs_present": bool(profile.get("contains_operator_source_refs")),
        },
        "network_touched": False,
        "read_only": True,
        "redacted": True,
        "secret_values_logged": False,
        "source_registry": {
            "path": str(roots.data / "sources" / "course_sources.json"),
            "source_count": len([item for item in registry.get("sources", []) if isinstance(item, dict)]),
            "selected_source_ids": selected_source_ids,
            "registered_profile_source_count": len(selected_source_ids),
        },
        "sources": source_plans,
        "browser_auth": browser_plans,
        "connected_plans": connected_plans,
        "live_readiness": live_readiness,
        "semantic_provider": semantic_preflight,
        "apply_command": apply_command,
        "next_commands": next_commands,
    }


def connection_profile_status(inspection: dict[str, object]) -> dict[str, object]:
    """Return the compact profile-driven live readiness status."""

    readiness = inspection.get("live_readiness") if isinstance(inspection.get("live_readiness"), dict) else {}
    return {
        "schema": "aoa_course_connection_profile_status_v1",
        "status": readiness.get("status") or "warning",
        "profile": inspection.get("profile") if isinstance(inspection.get("profile"), dict) else {},
        "network_touched": False,
        "read_only": True,
        "redacted": True,
        "live_readiness": readiness,
        "next_commands": readiness.get("next_commands", []) if isinstance(readiness.get("next_commands"), list) else [],
    }


def connection_profile_run_plan(
    profile: dict[str, object],
    inspection: dict[str, object],
    *,
    platform: str | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, object]:
    """Plan one executable live connected-run from a connection profile."""

    runtime = profile.get("runtime") if isinstance(profile.get("runtime"), dict) else {}
    source_plans = _dict_items(inspection.get("sources"))
    selected_source_ids = {str(source_id) for source_id in source_ids or [] if str(source_id)}
    selected_platform = str(platform or "")
    connected_plans = _dict_items(inspection.get("connected_plans"))
    candidates = [
        plan
        for plan in connected_plans
        if (not selected_platform or plan.get("platform") == selected_platform)
        and (not selected_source_ids or selected_source_ids.intersection({str(item) for item in plan.get("source_ids", []) if item}))
    ]
    ready_candidates = [plan for plan in candidates if plan.get("ready")]
    blocked_by: list[str] = []
    if not candidates:
        blocked_by.append("no connected plan matched the selected profile platform/source")
    if len(ready_candidates) > 1:
        blocked_by.append("multiple ready connected plans matched; select exactly one --platform or --source-id")
    selected = ready_candidates[0] if len(ready_candidates) == 1 and not blocked_by else None
    if not selected and candidates and not blocked_by:
        blocked_by.extend(_connected_plan_blockers(candidates))
    if not selected:
        return {
            "schema": "aoa_course_connection_profile_run_plan_v1",
            "status": "blocked",
            "ready": False,
            "network_touched": False,
            "mode": "live",
            "platform": selected_platform,
            "source_ids": sorted(selected_source_ids),
            "blocked_by": _dedupe(blocked_by),
            "candidate_commands": _dedupe([_connected_run_command(plan) for plan in ready_candidates]),
        }

    selected_platform = str(selected.get("platform") or "")
    connected_run = _nested_connected_run_plan(selected)
    state_file = _profile_state_file_for_platform(source_plans, selected_platform)
    expected_origin = _expected_origin_for_platform(source_plans, selected_platform)
    include_step_sources = bool(runtime.get("include_step_sources", False)) and selected_platform == "stepik"
    return {
        "schema": "aoa_course_connection_profile_run_plan_v1",
        "status": "ready",
        "ready": True,
        "network_touched": False,
        "mode": "live",
        "run_id": str(runtime.get("run_id") or "connected-calibration"),
        "platform": selected_platform,
        "source_ids": [str(item) for item in connected_run.get("source_ids", selected.get("source_ids", [])) if item],
        "query": str(runtime.get("query") or ""),
        "live_scope": str(runtime.get("live_scope") or "bounded"),
        "include_step_sources": include_step_sources,
        "max_step_sources": connected_run.get("max_step_sources", runtime.get("max_step_sources", DEFAULT_MAX_STEP_SOURCES)) if include_step_sources else DEFAULT_MAX_STEP_SOURCES,
        "step_source_timeout": float(connected_run.get("step_source_timeout") or runtime.get("step_source_timeout") or DEFAULT_STEP_SOURCE_TIMEOUT) if include_step_sources else DEFAULT_STEP_SOURCE_TIMEOUT,
        "max_lessons": int(runtime.get("max_lessons") or 50),
        "max_pages": int(runtime.get("max_pages") or 5),
        "max_sources": int(runtime.get("max_sources") or 50),
        "link_pattern": str(runtime.get("link_pattern") or ""),
        "browser_state_file": state_file if selected_platform in BROWSER_PLATFORMS else "",
        "expect_origin_contains": expected_origin if selected_platform in BROWSER_PLATFORMS else "",
        "stepik_token_env": _profile_stepik_token_env(source_plans),
        "command": str(connected_run.get("command") or _connected_run_command(selected)),
        "artifact_path": str(connected_run.get("artifact_path") or ""),
        "blocked_by": [],
    }


def apply_connection_profile(roots: StorageRoots, profile: dict[str, object], *, profile_path: Path | None = None) -> dict[str, object]:
    """Apply the local non-secret parts of a profile to the source registry."""

    roots.data.mkdir(parents=True, exist_ok=True)
    applied: list[dict[str, object]] = []
    for source in _profile_sources(profile):
        platform = str(source.get("platform") or "")
        source_ref = str(source.get("source_ref") or "")
        if not platform or not source_ref:
            continue
        saved, path, state = upsert_source(
            roots.data,
            platform=platform,
            source_ref=source_ref,
            title=str(source.get("title") or source_ref),
            access_mode=str(source.get("access_mode") or _default_access(platform)),
            enabled=bool(source.get("enabled", True)),
        )
        applied.append({"state": state, "registry_path": str(path), "source": saved})
    inspection = inspect_connection_profile(roots, profile, profile_path=profile_path)
    return {
        "schema": "aoa_course_connection_profile_apply_v1",
        "status": "ok",
        "profile": {
            "name": profile.get("name"),
            "path": str(profile_path) if profile_path else "",
        },
        "network_touched": False,
        "mutated": ["source_registry"],
        "secret_values_logged": False,
        "applied": applied,
        "inspection": inspection,
    }


def _browser_sources(platform: str, urls: list[str], auth_root: Path, state_file: Path | None) -> list[dict[str, object]]:
    sources: list[dict[str, object]] = []
    for url in _dedupe([item.strip() for item in urls if item.strip()]):
        default_state = default_browser_state_path(auth_root, platform, url)
        selected_state = state_file or default_state
        host = _host_fragment(url)
        sources.append(
            {
                "platform": platform,
                "source_ref": url,
                "title": host or url,
                "access_mode": "browser_session",
                "enabled": True,
                "state_file": str(selected_state),
                "default_state_file": str(default_state),
                "expected_origin_contains": host or "",
            }
        )
    return sources


def _source_plan(roots: StorageRoots, registry: dict[str, object], source: dict[str, object]) -> dict[str, object]:
    platform = str(source.get("platform") or "")
    source_ref = str(source.get("source_ref") or "")
    existing = _find_existing_source(registry, platform, source_ref)
    title = str(source.get("title") or source_ref)
    command = f"aoa-course sources add {shlex.quote(source_ref)} --platform {shlex.quote(platform)} --title {shlex.quote(title)} --access-mode {shlex.quote(str(source.get('access_mode') or _default_access(platform)))}"
    return {
        "platform": platform,
        "source_ref": source_ref,
        "title": title,
        "access_mode": source.get("access_mode") or _default_access(platform),
        "state_file": str(source.get("state_file") or ""),
        "token_env": str(source.get("token_env") or ""),
        "expected_origin_contains": str(source.get("expected_origin_contains") or _host_fragment(source_ref)),
        "registered": existing is not None,
        "source_id": existing.get("source_id") if existing else "",
        "register_command": "" if existing else command,
        "registry_path": str(roots.data / "sources" / "course_sources.json"),
    }


def _browser_plan(roots: StorageRoots, source: dict[str, object], *, source_id: str = "") -> dict[str, object]:
    platform = str(source.get("platform") or "")
    source_ref = str(source.get("source_ref") or "")
    state_file = Path(str(source.get("state_file") or default_browser_state_path(roots.auth, platform, source_ref)))
    expected_origin = str(source.get("expected_origin_contains") or _host_fragment(source_ref))
    state = inspect_browser_state(state_file, expect_origin_contains=expected_origin or None, platform=platform)
    import_firefox_command = (
        f"aoa-course auth import-firefox-state {shlex.quote(platform)} {shlex.quote(source_ref)} "
        f"--state-file {shlex.quote(str(state_file))} --expect-origin-contains {shlex.quote(expected_origin)}"
        if expected_origin
        else ""
    )
    return {
        "platform": platform,
        "source_ref": source_ref,
        "source_id": source_id,
        "state_file": str(state_file),
        "expected_origin_contains": expected_origin,
        "state_status": state.get("status"),
        "state_ready": bool(state.get("usable")),
        "state": state,
        "import_firefox_command": import_firefox_command,
        "capture_command": (
            f"aoa-course auth capture-browser-state {shlex.quote(platform)} {shlex.quote(source_ref)} "
            f"--login-url <login-or-account-url> --state-file {shlex.quote(str(state_file))}"
            + (f" --expect-origin-contains {shlex.quote(expected_origin)}" if expected_origin else "")
        ),
        "inspect_command": (
            f"aoa-course auth inspect-browser-state {shlex.quote(str(state_file))} --platform {shlex.quote(platform)}"
            + (f" --expect-origin-contains {shlex.quote(expected_origin)}" if expected_origin else "")
        ),
        "preflight_command": (
            f"aoa-course preflight connected-plan --platform {shlex.quote(platform)} "
            f"--state-file {shlex.quote(str(state_file))}"
            + (f" --expect-origin {shlex.quote(expected_origin)}" if expected_origin else "")
            + (f" --source-id {shlex.quote(source_id)}" if source_id else "")
        ),
    }


def _connected_plans(roots: StorageRoots, source_plans: list[dict[str, object]], runtime: dict[str, object]) -> list[dict[str, object]]:
    plans: list[dict[str, object]] = []
    max_step_sources = normalize_max_step_sources(runtime.get("max_step_sources", DEFAULT_MAX_STEP_SOURCES))
    step_source_timeout = normalize_step_source_timeout(runtime.get("step_source_timeout", DEFAULT_STEP_SOURCE_TIMEOUT))
    for plan in source_plans:
        platform = str(plan.get("platform") or "")
        if platform not in CONNECTED_PLATFORMS:
            continue
        include_step_sources = bool(runtime.get("include_step_sources", False)) and platform == "stepik"
        source_ids = [str(plan.get("source_id"))] if plan.get("source_id") else None
        state_file = _profile_state_file_for_platform(source_plans, platform)
        stepik_token_env = _profile_stepik_token_env(source_plans)
        plan = connected_source_plan(
            roots,
            platforms=[platform],
            source_ids=source_ids,
            stepik_token_env=stepik_token_env,
            browser_state_file=Path(state_file) if state_file else None,
            query=str(runtime.get("query") or "") or None,
            max_lessons=int(runtime.get("max_lessons") or 50),
            max_pages=int(runtime.get("max_pages") or 5),
            max_sources=int(runtime.get("max_sources") or 50),
            link_pattern=str(runtime.get("link_pattern") or "") or None,
            calibration_run=str(runtime.get("run_id") or "connected-calibration"),
            live_scope=str(runtime.get("live_scope") or "bounded"),
            include_step_sources=include_step_sources,
            max_step_sources=max_step_sources,
            step_source_timeout=step_source_timeout,
        )
        command = f"aoa-course preflight connected-plan --platform {shlex.quote(platform)}"
        for source_id in source_ids or []:
            command += f" --source-id {shlex.quote(source_id)}"
        if state_file:
            command += f" --state-file {shlex.quote(state_file)}"
        if runtime.get("query"):
            command += f" --query {shlex.quote(str(runtime.get('query')))}"
        if platform == "stepik" and stepik_token_env:
            command += f" --stepik-token-env {shlex.quote(stepik_token_env)}"
        if runtime.get("link_pattern"):
            command += f" --link-pattern {shlex.quote(str(runtime.get('link_pattern')))}"
        command += f" --live-scope {shlex.quote(str(runtime.get('live_scope') or 'bounded'))}"
        if include_step_sources:
            command += " --include-step-sources"
            command += f" --max-step-sources {shlex.quote(str(max_step_sources_packet(max_step_sources)))}"
            command += f" --step-source-timeout {step_source_timeout}"
        plans.append(
            {
                "platform": platform,
                "registered": bool(source_ids),
                "source_ids": source_ids or [],
                "ready": bool(plan.get("ready")),
                "status": plan.get("status"),
                "command": command,
                "plan": plan,
            }
        )
    return plans


def _profile_state_file_for_platform(source_plans: list[dict[str, object]], platform: str) -> str:
    for plan in source_plans:
        if plan.get("platform") != platform:
            continue
        return str(plan.get("state_file") or "")
    return ""


def _expected_origin_for_platform(source_plans: list[dict[str, object]], platform: str) -> str:
    for plan in source_plans:
        if plan.get("platform") != platform:
            continue
        return str(plan.get("expected_origin_contains") or "")
    return ""


def _profile_stepik_token_env(source_plans: list[dict[str, object]]) -> str:
    for plan in source_plans:
        if plan.get("platform") == "stepik" and plan.get("token_env"):
            return str(plan.get("token_env"))
    return "STEPIK_API_TOKEN"


def _live_readiness(
    *,
    source_plans: list[dict[str, object]],
    browser_plans: list[dict[str, object]],
    connected_plans: list[dict[str, object]],
    semantic_preflight: dict[str, object],
    apply_command: str,
) -> dict[str, object]:
    source_count = len(source_plans)
    registered_sources = [source for source in source_plans if source.get("registered")]
    browser_source_count = len(browser_plans)
    browser_ready = [plan for plan in browser_plans if plan.get("state_ready")]
    ready_plans = [plan for plan in connected_plans if plan.get("ready")]
    connected_run_commands = _dedupe([_connected_run_command(plan) for plan in ready_plans])
    blocked_by = _live_readiness_blockers(
        source_plans=source_plans,
        browser_plans=browser_plans,
        connected_plans=connected_plans,
        apply_command=apply_command,
    )
    semantic_blockers = _semantic_blockers(semantic_preflight)
    ready_for_connected_run = source_count > 0 and len(registered_sources) == source_count and len(ready_plans) == len(connected_plans) and bool(connected_run_commands)
    ready_for_semantic_build = bool(semantic_preflight.get("ready"))
    next_commands = _dedupe(
        [
            *[str(source.get("register_command") or "") for source in source_plans if not source.get("registered")],
            *[str(plan.get("import_firefox_command") or "") for plan in browser_plans if not plan.get("state_ready")],
            *[str(plan.get("capture_command") or "") for plan in browser_plans if not plan.get("state_ready")],
            *[str(plan.get("inspect_command") or "") for plan in browser_plans],
            *[str(plan.get("command") or "") for plan in connected_plans],
            *connected_run_commands,
            *[str(command) for command in semantic_preflight.get("next_commands", []) if str(command)],
            apply_command if len(registered_sources) != source_count else "",
        ]
    )
    return {
        "schema": "aoa_course_connection_profile_readiness_v1",
        "status": "ok" if ready_for_connected_run else "warning",
        "network_touched": False,
        "read_only": True,
        "source_count": source_count,
        "registered_source_count": len(registered_sources),
        "browser_source_count": browser_source_count,
        "browser_auth_ready_count": len(browser_ready),
        "connected_plan_count": len(connected_plans),
        "ready_connected_plan_count": len(ready_plans),
        "ready_for_connected_run": ready_for_connected_run,
        "ready_for_semantic_build": ready_for_semantic_build,
        "connected_run_commands": connected_run_commands,
        "blocked_by": blocked_by,
        "semantic_blocked_by": semantic_blockers,
        "next_commands": next_commands,
    }


def _live_readiness_blockers(
    *,
    source_plans: list[dict[str, object]],
    browser_plans: list[dict[str, object]],
    connected_plans: list[dict[str, object]],
    apply_command: str,
) -> list[str]:
    blockers: list[str] = []
    if not source_plans:
        blockers.append("connection profile has no sources")
    for source in source_plans:
        if not source.get("registered"):
            blockers.append(f"{source.get('platform')}: source is not registered: {source.get('source_ref')}")
    for plan in browser_plans:
        if not plan.get("state_ready"):
            blockers.append(f"{plan.get('platform')}: browser state is not ready for {plan.get('source_ref')}")
    for plan in connected_plans:
        if plan.get("ready"):
            continue
        nested = plan.get("plan") if isinstance(plan.get("plan"), dict) else {}
        plan = nested.get("connected_run_plan") if isinstance(nested.get("connected_run_plan"), dict) else {}
        blocked = plan.get("blocked_by") if isinstance(plan.get("blocked_by"), list) else []
        if blocked:
            blockers.extend([f"{plan.get('platform')}: {item}" for item in blocked])
        else:
            blockers.append(f"{plan.get('platform')}: connected plan is not ready")
    if apply_command and any(not source.get("registered") for source in source_plans):
        blockers.append("run connect apply to register profile sources before live connected-run")
    return _dedupe(blockers)


def _connected_run_command(plan: dict[str, object]) -> str:
    return str(_nested_connected_run_plan(plan).get("command") or "")


def _nested_connected_run_plan(plan: dict[str, object]) -> dict[str, object]:
    nested = plan.get("plan") if isinstance(plan.get("plan"), dict) else {}
    return nested.get("connected_run_plan") if isinstance(nested.get("connected_run_plan"), dict) else {}


def _connected_plan_blockers(plans: list[dict[str, object]]) -> list[str]:
    blockers: list[str] = []
    for plan in plans:
        nested = _nested_connected_run_plan(plan)
        for blocker in nested.get("blocked_by", []) if isinstance(nested.get("blocked_by"), list) else []:
            blockers.append(f"{plan.get('platform')}: {blocker}")
        if not nested.get("blocked_by"):
            blockers.append(f"{plan.get('platform')}: connected plan is not ready")
    return _dedupe(blockers)


def _semantic_blockers(semantic_preflight: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    checks = semantic_preflight.get("checks") if isinstance(semantic_preflight.get("checks"), list) else []
    for check in checks:
        if not isinstance(check, dict) or check.get("ready"):
            continue
        blocker = str(check.get("blocker") or "")
        if blocker:
            blockers.append(blocker)
    return _dedupe(blockers)


def _profile_sources(profile: dict[str, object]) -> list[dict[str, object]]:
    return [item for item in profile.get("sources", []) if isinstance(item, dict)] if isinstance(profile.get("sources"), list) else []


def _source_id_for_profile_source(source_plans: list[dict[str, object]], source: dict[str, object]) -> str:
    platform = str(source.get("platform") or "")
    source_ref = str(source.get("source_ref") or "")
    for plan in source_plans:
        if plan.get("platform") == platform and plan.get("source_ref") == source_ref:
            return str(plan.get("source_id") or "")
    return ""


def _dict_items(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _find_existing_source(registry: dict[str, object], platform: str, source_ref: str) -> dict[str, object] | None:
    for item in registry.get("sources", []):
        if isinstance(item, dict) and item.get("platform") == platform and item.get("source_ref") == source_ref:
            return item
    return None


def _apply_command(profile_path: Path | None) -> str:
    if profile_path is None:
        return ""
    return f"aoa-course connect apply {shlex.quote(str(profile_path))}"


def _selected_semantic_provider(provider: str) -> str:
    selected = str(provider or LOCAL_HASHING_PROVIDER)
    if selected not in SEMANTIC_PROVIDERS:
        raise ValueError(f"unsupported semantic provider: {selected}")
    return selected


def _default_access(platform: str) -> str:
    if platform in BROWSER_PLATFORMS:
        return "browser_session"
    if platform == "stepik":
        return "api_token"
    return "api_token"


def _host_fragment(value: str) -> str:
    raw = value.casefold().strip().lstrip(".")
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    host = parsed.hostname or raw.split("/", 1)[0]
    return host.strip().lstrip(".")


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "connection"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys([value for value in values if value]))


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
