"""Local connection-profile handoff for operator-owned course sources."""

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


BROWSER_PLATFORMS = {"getcourse", "skillspace"}
CONNECTED_PLATFORMS = {"getcourse", "skillspace", "stepik"}
SEMANTIC_PROVIDERS = {LOCAL_HASHING_PROVIDER, HTTP_JSON_PROVIDER}
MCP_INSPECT_TOOL = "connection_profile_inspect"


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
    source_handoffs = [_source_handoff(roots, registry, source) for source in sources]
    selected_source_ids = [
        str(item.get("source_id"))
        for item in source_handoffs
        if item.get("registered") and item.get("source_id")
    ]
    platforms = _dedupe([str(source.get("platform")) for source in sources if str(source.get("platform") or "") in CONNECTED_PLATFORMS])
    browser_handoffs = [_browser_handoff(roots, source) for source in sources if source.get("platform") in BROWSER_PLATFORMS]
    connected_plans = _connected_plans(roots, source_handoffs, runtime)
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
    next_commands = _dedupe(
        [
            *[str(item.get("register_command") or "") for item in source_handoffs if not item.get("registered")],
            *[str(item.get("capture_command") or "") for item in browser_handoffs if not item.get("state_ready")],
            *[str(item.get("inspect_command") or "") for item in browser_handoffs],
            *[str(plan.get("command") or "") for plan in connected_plans],
            *[str(command) for command in semantic_preflight.get("next_commands", []) if str(command)],
            apply_command,
        ]
    )
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
        "sources": source_handoffs,
        "browser_auth": browser_handoffs,
        "connected_plans": connected_plans,
        "semantic_provider": semantic_preflight,
        "apply_command": apply_command,
        "next_commands": next_commands,
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


def _source_handoff(roots: StorageRoots, registry: dict[str, object], source: dict[str, object]) -> dict[str, object]:
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
        "registered": existing is not None,
        "source_id": existing.get("source_id") if existing else "",
        "register_command": "" if existing else command,
        "registry_path": str(roots.data / "sources" / "course_sources.json"),
    }


def _browser_handoff(roots: StorageRoots, source: dict[str, object]) -> dict[str, object]:
    platform = str(source.get("platform") or "")
    source_ref = str(source.get("source_ref") or "")
    state_file = Path(str(source.get("state_file") or default_browser_state_path(roots.auth, platform, source_ref)))
    expected_origin = str(source.get("expected_origin_contains") or _host_fragment(source_ref))
    state = inspect_browser_state(state_file, expect_origin_contains=expected_origin or None)
    source_id = ""
    return {
        "platform": platform,
        "source_ref": source_ref,
        "state_file": str(state_file),
        "expected_origin_contains": expected_origin,
        "state_status": state.get("status"),
        "state_ready": bool(state.get("usable")),
        "state": state,
        "capture_command": (
            f"aoa-course auth capture-browser-state {shlex.quote(platform)} {shlex.quote(source_ref)} "
            f"--login-url <login-or-account-url> --state-file {shlex.quote(str(state_file))}"
            + (f" --expect-origin-contains {shlex.quote(expected_origin)}" if expected_origin else "")
        ),
        "inspect_command": (
            f"aoa-course auth inspect-browser-state {shlex.quote(str(state_file))}"
            + (f" --expect-origin-contains {shlex.quote(expected_origin)}" if expected_origin else "")
        ),
        "preflight_command": (
            f"aoa-course preflight connected-plan --platform {shlex.quote(platform)} "
            f"--state-file {shlex.quote(str(state_file))}"
            + (f" --expect-origin {shlex.quote(expected_origin)}" if expected_origin else "")
            + (f" --source-id {shlex.quote(source_id)}" if source_id else "")
        ),
    }


def _connected_plans(roots: StorageRoots, source_handoffs: list[dict[str, object]], runtime: dict[str, object]) -> list[dict[str, object]]:
    plans: list[dict[str, object]] = []
    for handoff in source_handoffs:
        platform = str(handoff.get("platform") or "")
        if platform not in CONNECTED_PLATFORMS:
            continue
        source_ids = [str(handoff.get("source_id"))] if handoff.get("source_id") else None
        state_file = _profile_state_file_for_platform(source_handoffs, platform)
        plan = connected_source_plan(
            roots,
            platforms=[platform],
            source_ids=source_ids,
            browser_state_file=Path(state_file) if state_file else None,
            query=str(runtime.get("query") or "") or None,
            max_lessons=int(runtime.get("max_lessons") or 50),
            max_pages=int(runtime.get("max_pages") or 5),
            max_sources=int(runtime.get("max_sources") or 50),
            link_pattern=str(runtime.get("link_pattern") or "") or None,
            calibration_run=str(runtime.get("run_id") or "connected-calibration"),
            live_scope=str(runtime.get("live_scope") or "bounded"),
            include_step_sources=bool(runtime.get("include_step_sources", False)),
        )
        command = f"aoa-course preflight connected-plan --platform {shlex.quote(platform)}"
        for source_id in source_ids or []:
            command += f" --source-id {shlex.quote(source_id)}"
        if state_file:
            command += f" --state-file {shlex.quote(state_file)}"
        if runtime.get("query"):
            command += f" --query {shlex.quote(str(runtime.get('query')))}"
        if runtime.get("link_pattern"):
            command += f" --link-pattern {shlex.quote(str(runtime.get('link_pattern')))}"
        command += f" --live-scope {shlex.quote(str(runtime.get('live_scope') or 'bounded'))}"
        if bool(runtime.get("include_step_sources", False)):
            command += " --include-step-sources"
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


def _profile_state_file_for_platform(source_handoffs: list[dict[str, object]], platform: str) -> str:
    for handoff in source_handoffs:
        if handoff.get("platform") != platform:
            continue
        return str(handoff.get("state_file") or "")
    return ""


def _profile_sources(profile: dict[str, object]) -> list[dict[str, object]]:
    return [item for item in profile.get("sources", []) if isinstance(item, dict)] if isinstance(profile.get("sources"), list) else []


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
