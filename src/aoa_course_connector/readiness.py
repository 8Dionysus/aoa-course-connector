"""Read-only readiness checks for live connector work."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from aoa_course_connector.auth import inspect_browser_state
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.sources import load_registry, registry_path


BROWSER_PLATFORMS = {"getcourse", "skillspace"}
CONNECTED_PLATFORMS = {"getcourse", "skillspace", "stepik"}


def live_preflight(
    roots: StorageRoots,
    *,
    platforms: list[str] | None = None,
    stepik_token_env: str = "STEPIK_API_TOKEN",
    browser_state_file: Path | None = None,
    expect_origin_contains: str | None = None,
    include_disabled: bool = False,
) -> dict[str, object]:
    selected_platforms = _selected_platforms(platforms)
    registry = load_registry(roots.data)
    sources = [
        source
        for source in registry.get("sources", [])
        if isinstance(source, dict)
        and source.get("platform") in selected_platforms
        and (include_disabled or source.get("enabled", True))
    ]
    checks: list[dict[str, object]] = []
    workflows: list[dict[str, object]] = []
    next_commands: list[str] = []

    if "stepik" in selected_platforms:
        _append_stepik_preflight(
            checks,
            workflows,
            next_commands,
            sources=[source for source in sources if source.get("platform") == "stepik"],
            token_env=stepik_token_env,
        )

    for platform in [item for item in ["getcourse", "skillspace"] if item in selected_platforms]:
        _append_browser_preflight(
            checks,
            workflows,
            next_commands,
            roots=roots,
            platform=platform,
            sources=[source for source in sources if source.get("platform") == platform],
            browser_state_file=browser_state_file,
            expect_origin_contains=expect_origin_contains,
        )

    ready = bool(workflows) and all(bool(item.get("ready")) for item in workflows)
    return {
        "schema": "aoa_course_live_preflight_v1",
        "status": "ok" if ready else "warning",
        "ready": ready,
        "network_touched": False,
        "read_only": True,
        "privacy": {
            "token_values_logged": False,
            "cookie_values_logged": False,
            "local_storage_values_logged": False,
        },
        "storage": {
            "mode": roots.mode,
            "data": str(roots.data),
            "auth": str(roots.auth),
            "artifact": str(roots.artifact),
            "cache": str(roots.cache),
        },
        "source_registry": {
            "path": str(registry_path(roots.data)),
            "source_count": len([item for item in registry.get("sources", []) if isinstance(item, dict)]),
            "selected_source_count": len(sources),
        },
        "platforms": selected_platforms,
        "checks": checks,
        "workflows": workflows,
        "next_commands": _dedupe(next_commands),
    }


def _selected_platforms(platforms: list[str] | None) -> list[str]:
    selected = list(dict.fromkeys(platforms or ["getcourse", "skillspace", "stepik"]))
    unsupported = [platform for platform in selected if platform not in CONNECTED_PLATFORMS]
    if unsupported:
        raise ValueError(f"unsupported preflight platform: {', '.join(unsupported)}")
    return selected


def _append_stepik_preflight(
    checks: list[dict[str, object]],
    workflows: list[dict[str, object]],
    next_commands: list[str],
    *,
    sources: list[dict[str, object]],
    token_env: str,
) -> None:
    token_present = bool(os.environ.get(token_env))
    checks.append(
        {
            "kind": "token",
            "platform": "stepik",
            "status": "ok" if token_present else "missing",
            "ready": token_present,
            "token_env": token_env,
            "token_present": token_present,
            "token_value_logged": False,
            "required_for": ["discover stepik-account", "stepik authenticated source enrichment"],
            "next_command": f"export {token_env}=<stepik-api-token>",
        }
    )
    for source in sources:
        access_mode = str(source.get("access_mode") or "")
        needs_token = access_mode in {"api_token", "oauth"}
        ready = bool(source.get("enabled", True)) and (token_present if needs_token else True)
        blockers = []
        if needs_token and not token_present:
            blockers.append(f"missing token env {token_env}")
        checks.append(_source_check(source, ready=ready, blockers=blockers))

    workflows.append(
        {
            "name": "stepik_account_discovery",
            "platform": "stepik",
            "ready": token_present,
            "source_count": len(sources),
            "next_command": (
                "aoa-course discover stepik-account "
                f"--token-env {token_env} --register --max-pages 5"
            ),
        }
    )
    workflows.append(
        {
            "name": "stepik_source_sync",
            "platform": "stepik",
            "ready": bool(sources) and all(bool(item.get("ready")) for item in checks if item.get("kind") == "source" and item.get("platform") == "stepik"),
            "source_count": len(sources),
            "next_command": (
                "aoa-course sync stepik-live --run stepik-live-sync "
                "--full-course --batch-size 20 --include-step-sources --build-artifacts"
            ),
        }
    )
    if not token_present:
        next_commands.append(f"export {token_env}=<stepik-api-token>")
    if not sources:
        next_commands.append(f"aoa-course discover stepik-account --token-env {token_env} --register --max-pages 5")
    else:
        next_commands.append("aoa-course sync stepik-live --run stepik-live-sync --full-course --batch-size 20 --include-step-sources --build-artifacts")


def _append_browser_preflight(
    checks: list[dict[str, object]],
    workflows: list[dict[str, object]],
    next_commands: list[str],
    *,
    roots: StorageRoots,
    platform: str,
    sources: list[dict[str, object]],
    browser_state_file: Path | None,
    expect_origin_contains: str | None,
) -> None:
    state_file = (browser_state_file or roots.auth / platform / "account.storage-state.json").expanduser().resolve()
    expected_origin = expect_origin_contains or _origin_hint(sources)
    state = inspect_browser_state(state_file, expect_origin_contains=expected_origin or None)
    state_ready = bool(state.get("usable"))
    checks.append(
        {
            "kind": "browser_state",
            "platform": platform,
            "status": state.get("status"),
            "ready": state_ready,
            "state_file": str(state_file),
            "exists": state.get("exists"),
            "usable": state.get("usable"),
            "expected_origin_contains": state.get("expect_origin_contains"),
            "expected_origin_matched": state.get("expected_origin_matched"),
            "cookie_count": state.get("cookie_count", 0),
            "origin_count": state.get("origin_count", 0),
            "local_storage_entry_count": state.get("local_storage_entry_count", 0),
            "session_storage_entry_count": state.get("session_storage_entry_count", 0),
            "secrets_redacted": True,
            "next_command": f"aoa-course auth capture-browser-state {platform} account --login-url <login-or-account-url> --state-file {str(state_file)!r}",
        }
    )
    for source in sources:
        blockers = [] if state_ready else [f"browser storage state is {state.get('status')}"]
        checks.append(_source_check(source, ready=state_ready and bool(source.get("enabled", True)), blockers=blockers))

    workflows.append(
        {
            "name": "browser_live_discovery",
            "platform": platform,
            "ready": state_ready,
            "source_count": len(sources),
            "next_command": (
                f"aoa-course discover browser-live <catalog-url> --platform {platform} "
                f"--state-file {str(state_file)!r} --register --max-sources 50 --max-pages 5"
            ),
        }
    )
    workflows.append(
        {
            "name": "browser_live_sync",
            "platform": platform,
            "ready": state_ready and bool(sources),
            "source_count": len(sources),
            "next_command": (
                f"aoa-course sync browser-live --platform {platform} "
                f"--state-file {str(state_file)!r} --max-lessons 50 --build-artifacts"
            ),
        }
    )
    if not state_ready:
        next_commands.append(f"aoa-course auth plan-browser-state {platform} account")
        next_commands.append(f"aoa-course auth capture-browser-state {platform} account --login-url <login-or-account-url> --state-file {str(state_file)!r}")
        next_commands.append(f"aoa-course auth inspect-browser-state {str(state_file)!r}")
    elif not sources:
        next_commands.append(
            f"aoa-course discover browser-live <catalog-url> --platform {platform} "
            f"--state-file {str(state_file)!r} --register --max-sources 50 --max-pages 5"
        )
    else:
        next_commands.append(
            f"aoa-course sync browser-live --platform {platform} "
            f"--state-file {str(state_file)!r} --max-lessons 50 --build-artifacts"
        )


def _source_check(source: dict[str, object], *, ready: bool, blockers: list[str]) -> dict[str, object]:
    return {
        "kind": "source",
        "platform": str(source.get("platform") or ""),
        "source_id": str(source.get("source_id") or ""),
        "source_ref": str(source.get("source_ref") or ""),
        "title": str(source.get("title") or source.get("source_ref") or ""),
        "access_mode": str(source.get("access_mode") or ""),
        "enabled": bool(source.get("enabled", True)),
        "ready": ready,
        "status": "ok" if ready else "blocked",
        "blockers": blockers,
    }


def _origin_hint(sources: list[dict[str, object]]) -> str:
    for source in sources:
        ref = str(source.get("source_ref") or "")
        host = _host(ref)
        if host:
            return host
    return ""


def _host(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"//{value}")
    return parsed.hostname or ""


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
