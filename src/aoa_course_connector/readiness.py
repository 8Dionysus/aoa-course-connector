"""Read-only readiness checks for live connector work."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from urllib.parse import urlparse

from aoa_course_connector.auth import inspect_browser_state
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.sources import load_registry, registry_path


BROWSER_PLATFORMS = {"getcourse", "skillspace"}
CONNECTED_PLATFORMS = {"getcourse", "skillspace", "stepik"}
LIVE_SCOPES = {"bounded", "full-course"}
ARTIFACT_ROOT_EXPR = "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}"


def render_connected_source_runbook(plan: dict[str, object]) -> str:
    """Render a redacted Markdown runbook from a connected-source plan."""

    lines = [
        "# Connected Source Runbook",
        "",
        "This runbook is generated from `aoa_course_connected_source_plan_v1`.",
        "It is runtime operator state: keep it outside Git and do not paste it into public issues.",
        "",
        "## Summary",
        "",
        f"- status: `{plan.get('status')}`",
        f"- ready: `{bool(plan.get('ready'))}`",
        f"- network_touched: `{bool(plan.get('network_touched'))}`",
        f"- live_scope: `{plan.get('live_scope')}`",
        f"- include_step_sources: `{bool(plan.get('include_step_sources'))}`",
    ]
    source_registry = plan.get("source_registry") if isinstance(plan.get("source_registry"), dict) else {}
    if source_registry:
        lines.extend(
            [
                f"- source_registry: `{source_registry.get('path')}`",
                f"- selected_source_count: `{source_registry.get('selected_source_count')}`",
            ]
        )
    lines.extend(["", "## Platform Readiness", ""])
    for platform in _dict_items(plan.get("platform_plans")):
        lines.extend(
            [
                f"### {platform.get('platform')}",
                "",
                f"- ready: `{bool(platform.get('ready'))}`",
                f"- source_count: `{platform.get('source_count')}`",
                f"- ready_source_count: `{platform.get('ready_source_count')}`",
                f"- blocked_source_count: `{platform.get('blocked_source_count')}`",
                f"- required_workflow: `{platform.get('required_workflow')}`",
            ]
        )
        blockers = [str(item) for item in platform.get("blockers", [])] if isinstance(platform.get("blockers"), list) else []
        if blockers:
            lines.extend(["- blockers:"])
            lines.extend([f"  - {blocker}" for blocker in blockers])
        lines.append("")

    handoffs = _dict_items(plan.get("browser_auth_handoffs"))
    if handoffs:
        lines.extend(["## Browser Auth Handoffs", ""])
        for handoff in handoffs:
            lines.extend(
                [
                    f"### {handoff.get('platform')}",
                    "",
                    f"- ready: `{bool(handoff.get('ready'))}`",
                    f"- state_file: `{handoff.get('state_file')}`",
                    f"- state_status: `{handoff.get('state_status')}`",
                    f"- expected_origin_contains: `{handoff.get('expected_origin_contains')}`",
                    f"- source_hosts: `{', '.join([str(host) for host in handoff.get('source_hosts', [])])}`",
                    f"- blocked_source_hosts: `{', '.join([str(host) for host in handoff.get('blocked_source_hosts', [])])}`",
                ]
            )
            host_readiness = _dict_items(handoff.get("host_readiness"))
            if host_readiness:
                lines.extend(["", "Host readiness:"])
                for host in host_readiness:
                    lines.append(
                        f"- `{host.get('host')}`: {host.get('ready_source_count')}/{host.get('source_count')} ready, "
                        f"{host.get('blocked_source_count')} blocked"
                    )
                    blockers = [str(item) for item in host.get("blockers", [])] if isinstance(host.get("blockers"), list) else []
                    lines.extend([f"  - {blocker}" for blocker in blockers])
            commands = handoff.get("commands") if isinstance(handoff.get("commands"), dict) else {}
            if commands:
                lines.extend(["", "Commands:"])
                for label in ["plan", "capture", "inspect", "recheck"]:
                    command = str(commands.get(label) or "")
                    if command:
                        lines.extend([f"- {label}:", "  ```bash", f"  {command}", "  ```"])
                inspect_hosts = commands.get("inspect_source_hosts")
                if isinstance(inspect_hosts, list) and inspect_hosts:
                    lines.extend(["- inspect source hosts:"])
                    for command in inspect_hosts:
                        lines.extend(["  ```bash", f"  {command}", "  ```"])
            notes = [str(item) for item in handoff.get("notes", [])] if isinstance(handoff.get("notes"), list) else []
            if notes:
                lines.extend(["", "Notes:"])
                lines.extend([f"- {note}" for note in notes])
            lines.append("")

    lines.extend(["## Execution Stages", ""])
    for stage in _dict_items(plan.get("stages")):
        lines.extend(
            [
                f"### {stage.get('name')}",
                "",
                f"- ready: `{bool(stage.get('ready'))}`",
            ]
        )
        actions = _dict_items(stage.get("actions"))
        if not actions:
            lines.extend(["- actions: none", ""])
            continue
        for action in actions:
            lines.extend(
                [
                    f"- {action.get('kind')} `{action.get('platform') or ''}`".rstrip(),
                    f"  - ready: `{bool(action.get('ready'))}`",
                    f"  - network_touched: `{bool(action.get('network_touched'))}`",
                ]
            )
            blocked_by = action.get("blocked_by")
            if isinstance(blocked_by, list) and blocked_by:
                lines.extend([f"  - blocked_by: {', '.join([str(item) for item in blocked_by])}"])
            artifact_path = str(action.get("artifact_path") or "")
            if artifact_path:
                lines.append(f"  - artifact_path: `{artifact_path}`")
            command = str(action.get("command") or "")
            if command:
                lines.extend(["  ```bash", f"  {command}", "  ```"])
        lines.append("")

    next_commands = [str(item) for item in plan.get("next_commands", [])] if isinstance(plan.get("next_commands"), list) else []
    if next_commands:
        lines.extend(["## Next Commands", ""])
        for command in next_commands:
            lines.extend(["```bash", command, "```", ""])
    return "\n".join(lines).rstrip() + "\n"


def write_connected_source_runbook(plan: dict[str, object], path: Path) -> dict[str, object]:
    """Write a connected-source runbook to a runtime path."""

    target = path.expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_connected_source_runbook(plan), encoding="utf-8")
    return {
        "path": str(target),
        "written": True,
        "format": "markdown",
        "network_touched": False,
        "redacted": True,
    }


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

    required_workflows = [item for item in workflows if item.get("required_for_ready", True)]
    ready = bool(required_workflows) and all(bool(item.get("ready")) for item in required_workflows)
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


def _dict_items(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def connected_source_plan(
    roots: StorageRoots,
    *,
    platforms: list[str] | None = None,
    stepik_token_env: str = "STEPIK_API_TOKEN",
    browser_state_file: Path | None = None,
    expect_origin_contains: str | None = None,
    include_disabled: bool = False,
    query: str | None = None,
    max_lessons: int = 50,
    max_pages: int = 5,
    max_sources: int = 50,
    calibration_run: str = "connected-live-calibration",
    live_scope: str = "bounded",
    include_step_sources: bool = False,
) -> dict[str, object]:
    """Build a read-only launch plan for connected-source calibration."""

    selected_platforms = _selected_platforms(platforms)
    selected_live_scope = _selected_live_scope(live_scope)
    preflight = live_preflight(
        roots,
        platforms=selected_platforms,
        stepik_token_env=stepik_token_env,
        browser_state_file=browser_state_file,
        expect_origin_contains=expect_origin_contains,
        include_disabled=include_disabled,
    )
    source_checks = [
        check
        for check in preflight.get("checks", [])
        if isinstance(check, dict) and check.get("kind") == "source"
    ]
    workflow_by_key = {
        (str(workflow.get("name") or ""), str(workflow.get("platform") or "")): workflow
        for workflow in preflight.get("workflows", [])
        if isinstance(workflow, dict)
    }
    preflight_actions = _preflight_actions(
        selected_platforms,
        stepik_token_env=stepik_token_env,
        browser_state_file=browser_state_file,
        expect_origin_contains=expect_origin_contains,
        include_disabled=include_disabled,
    )
    setup_actions = _setup_actions(preflight)
    sync_actions = _sync_actions(
        selected_platforms,
        source_checks,
        workflow_by_key,
        stepik_token_env=stepik_token_env,
        browser_state_file=browser_state_file,
        max_lessons=max_lessons,
        live_scope=selected_live_scope,
        include_step_sources=include_step_sources,
    )
    smoke_actions = _smoke_actions(
        source_checks,
        stepik_token_env=stepik_token_env,
        browser_state_file=browser_state_file,
        query=query,
        max_lessons=max_lessons,
        max_pages=max_pages,
        max_sources=max_sources,
        live_scope=selected_live_scope,
        include_step_sources=include_step_sources,
    )
    calibration_actions = _calibration_actions(
        preflight_actions,
        smoke_actions,
        calibration_run=calibration_run,
    )
    source_plans = [_source_plan(check, sync_actions, smoke_actions) for check in source_checks]
    platform_plans = _platform_plans(selected_platforms, source_checks, workflow_by_key)
    browser_auth_handoffs = _browser_auth_handoffs(
        selected_platforms,
        preflight,
        browser_state_file=browser_state_file,
        expect_origin_contains=expect_origin_contains,
    )
    ready_platforms = [plan for plan in platform_plans if plan.get("ready")]
    blocked_smoke_actions = [action for action in smoke_actions if not action.get("ready")]
    ready = len(ready_platforms) == len(selected_platforms) and not blocked_smoke_actions
    status = "ok" if ready else "partial" if ready_platforms else "warning"
    stages = [
        {"name": "preflight_reports", "ready": True, "actions": preflight_actions},
        {"name": "setup_or_unblock", "ready": not setup_actions, "actions": setup_actions},
        {"name": "live_sync", "ready": bool(sync_actions), "actions": sync_actions},
        {"name": "live_smoke", "ready": bool(smoke_actions) and not blocked_smoke_actions, "actions": smoke_actions},
        {"name": "calibration_packet", "ready": bool(calibration_actions), "actions": calibration_actions},
    ]
    return {
        "schema": "aoa_course_connected_source_plan_v1",
        "status": status,
        "ready": ready,
        "actionable": any(stage.get("actions") for stage in stages),
        "network_touched": False,
        "read_only": True,
        "privacy": preflight.get("privacy"),
        "storage": preflight.get("storage"),
        "source_registry": preflight.get("source_registry"),
        "platforms": selected_platforms,
        "live_scope": selected_live_scope,
        "include_step_sources": include_step_sources,
        "platform_plans": platform_plans,
        "browser_auth_handoffs": browser_auth_handoffs,
        "source_plans": source_plans,
        "stages": stages,
        "next_commands": _dedupe(
            [
                str(action.get("command") or "")
                for stage in stages
                for action in stage.get("actions", [])
                if isinstance(action, dict) and action.get("command")
            ]
        ),
        "preflight": preflight,
    }


def _selected_platforms(platforms: list[str] | None) -> list[str]:
    selected = list(dict.fromkeys(platforms or ["getcourse", "skillspace", "stepik"]))
    unsupported = [platform for platform in selected if platform not in CONNECTED_PLATFORMS]
    if unsupported:
        raise ValueError(f"unsupported preflight platform: {', '.join(unsupported)}")
    return selected


def _selected_live_scope(live_scope: str) -> str:
    selected = str(live_scope or "bounded")
    if selected not in LIVE_SCOPES:
        raise ValueError(f"unsupported live scope: {selected}")
    return selected


def _preflight_actions(
    platforms: list[str],
    *,
    stepik_token_env: str,
    browser_state_file: Path | None,
    expect_origin_contains: str | None,
    include_disabled: bool,
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for platform in platforms:
        command = f"aoa-course preflight live --platform {platform}"
        if platform == "stepik":
            command += f" --stepik-token-env {shlex.quote(stepik_token_env)}"
        if platform in BROWSER_PLATFORMS:
            command += f" --state-file {_state_file_arg(platform, browser_state_file)}"
            if expect_origin_contains:
                command += f" --expect-origin {shlex.quote(expect_origin_contains)}"
        if include_disabled:
            command += " --include-disabled"
        artifact = f"{ARTIFACT_ROOT_EXPR}/{platform}-preflight.json"
        actions.append(
            {
                "kind": "preflight_report",
                "platform": platform,
                "ready": True,
                "network_touched": False,
                "artifact_path": artifact,
                "command": f'{command} > "{artifact}"',
            }
        )
    return actions


def _setup_actions(preflight: dict[str, object]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for command in preflight.get("next_commands", []):
        text = str(command or "")
        if not text:
            continue
        if " sync " in f" {text} ":
            continue
        actions.append({"kind": _setup_kind(text), "ready": True, "command": text, "network_touched": _command_touches_network(text)})
    return actions


def _setup_kind(command: str) -> str:
    if command.startswith("export "):
        return "set_token_env"
    if "capture-browser-state" in command:
        return "capture_browser_state"
    if "inspect-browser-state" in command:
        return "inspect_browser_state"
    if "plan-browser-state" in command:
        return "plan_browser_state"
    if "discover " in command:
        return "discover_sources"
    return "setup"


def _sync_actions(
    platforms: list[str],
    source_checks: list[dict[str, object]],
    workflow_by_key: dict[tuple[str, str], dict[str, object]],
    *,
    stepik_token_env: str,
    browser_state_file: Path | None,
    max_lessons: int,
    live_scope: str,
    include_step_sources: bool,
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for platform in [item for item in platforms if item in BROWSER_PLATFORMS]:
        workflow = workflow_by_key.get(("browser_live_sync", platform), {})
        if not workflow.get("ready"):
            continue
        for source in [item for item in source_checks if item.get("platform") == platform and item.get("ready")]:
            slug = _source_slug(source)
            source_id = str(source.get("source_id") or "")
            command = (
                f"aoa-course sync browser-live --run {platform}-live-sync-{slug} --platform {platform} "
                f"--source-id {shlex.quote(source_id)} --state-file {_state_file_arg(platform, browser_state_file)} "
                f"--max-lessons {max_lessons} --build-artifacts"
            )
            actions.append(
                {
                    "kind": "sync",
                    "platform": platform,
                    "source_id": source_id,
                    "source_ref": source.get("source_ref"),
                    "ready": True,
                    "network_touched": True,
                    "command": command,
                }
            )
    if "stepik" in platforms:
        workflow = workflow_by_key.get(("stepik_source_sync", "stepik"), {})
        if workflow.get("ready"):
            for source in [item for item in source_checks if item.get("platform") == "stepik" and item.get("ready")]:
                source_id = str(source.get("source_id") or "")
                command = _stepik_sync_command(
                    stepik_token_env=stepik_token_env,
                    live_scope=live_scope,
                    include_step_sources=include_step_sources,
                    source_id=source_id,
                    run_suffix=_source_slug(source),
                )
                actions.append(
                    {
                        "kind": "sync",
                        "platform": "stepik",
                        "source_id": source_id,
                        "source_ref": source.get("source_ref"),
                        "ready": True,
                        "network_touched": True,
                        "command": command,
                    }
                )
    return actions


def _smoke_actions(
    source_checks: list[dict[str, object]],
    *,
    stepik_token_env: str,
    browser_state_file: Path | None,
    query: str | None,
    max_lessons: int,
    max_pages: int,
    max_sources: int,
    live_scope: str,
    include_step_sources: bool,
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for source in source_checks:
        if not source.get("ready"):
            continue
        platform = str(source.get("platform") or "")
        source_ref = str(source.get("source_ref") or "")
        slug = _source_slug(source)
        artifact = f"{ARTIFACT_ROOT_EXPR}/{platform}-live-smoke-{slug}.json"
        if platform in BROWSER_PLATFORMS:
            command = (
                f"aoa-course smoke browser-live --platform {platform} --run {platform}-live-smoke-{slug} "
                f"--course-url {shlex.quote(source_ref)} --state-file {_state_file_arg(platform, browser_state_file)} "
                f"--max-sources {max_sources} --max-pages {max_pages} --max-lessons {max_lessons}"
            )
        elif platform == "stepik":
            course_id = _stepik_course_id(source_ref)
            if course_id is None:
                actions.append(
                    {
                        "kind": "smoke",
                        "platform": platform,
                        "source_id": source.get("source_id"),
                        "source_ref": source_ref,
                        "ready": False,
                        "network_touched": True,
                        "blocked_by": [f"cannot parse Stepik course id from source_ref: {source_ref}"],
                    }
                )
                continue
            command = _stepik_smoke_command(
                course_id,
                slug=slug,
                access_mode=str(source.get("access_mode") or "public_api"),
                stepik_token_env=stepik_token_env,
                live_scope=live_scope,
                include_step_sources=include_step_sources,
            )
        else:
            continue
        if query:
            command += f" --query {shlex.quote(query)}"
        actions.append(
            {
                "kind": "smoke",
                "platform": platform,
                "source_id": source.get("source_id"),
                "source_ref": source_ref,
                "ready": True,
                "network_touched": True,
                "artifact_path": artifact,
                "command": f'{command} > "{artifact}"',
            }
        )
    return actions


def _calibration_actions(
    preflight_actions: list[dict[str, object]],
    smoke_actions: list[dict[str, object]],
    *,
    calibration_run: str,
) -> list[dict[str, object]]:
    ready_smoke_artifacts = [str(action.get("artifact_path") or "") for action in smoke_actions if action.get("ready") and action.get("artifact_path")]
    if not ready_smoke_artifacts:
        return []
    preflight_artifacts = [str(action.get("artifact_path") or "") for action in preflight_actions if action.get("artifact_path")]
    parts = ["aoa-course calibration build", f"--run {shlex.quote(calibration_run)}"]
    for path in ready_smoke_artifacts:
        parts.append(f'--report "{path}"')
    for path in preflight_artifacts:
        parts.append(f'--preflight-report "{path}"')
    return [
        {
            "kind": "calibration",
            "ready": True,
            "network_touched": False,
            "command": " ".join(parts),
            "artifact_path": f"{ARTIFACT_ROOT_EXPR}/runs/{calibration_run}/calibration/live_calibration_packet.json",
        }
    ]


def _source_plan(source: dict[str, object], sync_actions: list[dict[str, object]], smoke_actions: list[dict[str, object]]) -> dict[str, object]:
    source_id = source.get("source_id")
    sync = next((action for action in sync_actions if action.get("source_id") == source_id), None)
    smoke = next((action for action in smoke_actions if action.get("source_id") == source_id), None)
    return {
        "platform": source.get("platform"),
        "source_id": source_id,
        "source_ref": source.get("source_ref"),
        "title": source.get("title"),
        "access_mode": source.get("access_mode"),
        "enabled": source.get("enabled"),
        "ready": source.get("ready"),
        "blockers": source.get("blockers", []),
        "sync_command": sync.get("command") if sync else None,
        "smoke_command": smoke.get("command") if smoke else None,
        "smoke_report_path": smoke.get("artifact_path") if smoke else None,
    }


def _browser_auth_handoffs(
    platforms: list[str],
    preflight: dict[str, object],
    *,
    browser_state_file: Path | None,
    expect_origin_contains: str | None,
) -> list[dict[str, object]]:
    checks = [check for check in preflight.get("checks", []) if isinstance(check, dict)]
    handoffs: list[dict[str, object]] = []
    for platform in [item for item in platforms if item in BROWSER_PLATFORMS]:
        state_check = next(
            (
                check
                for check in checks
                if check.get("kind") == "browser_state" and check.get("platform") == platform
            ),
            None,
        )
        if not state_check:
            continue
        source_checks = [
            check
            for check in checks
            if check.get("kind") == "source" and check.get("platform") == platform
        ]
        blocked_sources = [check for check in source_checks if not check.get("ready")]
        source_hosts = _dedupe([_host(str(check.get("source_ref") or "")) for check in source_checks])
        blocked_source_hosts = _dedupe([_host(str(check.get("source_ref") or "")) for check in blocked_sources])
        expected_origin = _handoff_expected_origin(
            state_check,
            source_hosts,
            expect_origin_contains=expect_origin_contains,
        )
        handoffs.append(
            {
                "platform": platform,
                "ready": bool(state_check.get("ready")) and (not source_checks or not blocked_sources),
                "state_file": state_check.get("state_file"),
                "state_status": state_check.get("status"),
                "state_exists": state_check.get("exists"),
                "state_usable": state_check.get("usable"),
                "expected_origin_contains": expected_origin,
                "source_count": len(source_checks),
                "ready_source_count": len(source_checks) - len(blocked_sources),
                "blocked_source_count": len(blocked_sources),
                "source_hosts": source_hosts,
                "blocked_source_hosts": blocked_source_hosts,
                "host_readiness": _host_readiness(source_checks),
                "blockers": _dedupe(
                    [
                        str(blocker)
                        for check in blocked_sources
                        for blocker in check.get("blockers", [])
                    ]
                ),
                "commands": _browser_auth_handoff_commands(
                    platform,
                    browser_state_file=browser_state_file,
                    source_hosts=source_hosts,
                    expected_origin_contains=expected_origin,
                ),
                "notes": [
                    "capture auth state only from the connected user's legitimate course account",
                    "inspect commands redact cookie, token, localStorage, and sessionStorage values",
                    "re-run connected-plan after capture; live sync remains blocked until every registered source host matches auth state",
                ],
            }
        )
    return handoffs


def _host_readiness(source_checks: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for source in source_checks:
        host = _host(str(source.get("source_ref") or "")) or "<unparsed>"
        groups.setdefault(host, []).append(source)
    readiness: list[dict[str, object]] = []
    for host, sources in groups.items():
        blocked = [source for source in sources if not source.get("ready")]
        readiness.append(
            {
                "host": host,
                "source_count": len(sources),
                "ready_source_count": len(sources) - len(blocked),
                "blocked_source_count": len(blocked),
                "blockers": _dedupe(
                    [
                        str(blocker)
                        for source in blocked
                        for blocker in source.get("blockers", [])
                    ]
                ),
            }
        )
    return readiness


def _handoff_expected_origin(
    state_check: dict[str, object],
    source_hosts: list[str],
    *,
    expect_origin_contains: str | None,
) -> str | None:
    if expect_origin_contains:
        return expect_origin_contains
    if len(source_hosts) == 1:
        return source_hosts[0]
    expected = str(state_check.get("expected_origin_contains") or "")
    return expected or None


def _browser_auth_handoff_commands(
    platform: str,
    *,
    browser_state_file: Path | None,
    source_hosts: list[str],
    expected_origin_contains: str | None,
) -> dict[str, object]:
    state_arg = _state_file_arg(platform, browser_state_file)
    inspect = f"aoa-course auth inspect-browser-state {state_arg}"
    recheck = f"aoa-course preflight connected-plan --platform {platform} --live-scope bounded --state-file {state_arg}"
    if expected_origin_contains:
        quoted_origin = shlex.quote(expected_origin_contains)
        inspect += f" --expect-origin-contains {quoted_origin}"
        recheck += f" --expect-origin {quoted_origin}"
    return {
        "plan": f"aoa-course auth plan-browser-state {platform} account",
        "capture": (
            f"aoa-course auth capture-browser-state {platform} account "
            f"--login-url <login-or-account-url> --state-file {state_arg}"
        ),
        "inspect": inspect,
        "inspect_source_hosts": [
            f"aoa-course auth inspect-browser-state {state_arg} --expect-origin-contains {shlex.quote(host)}"
            for host in source_hosts
        ],
        "recheck": recheck,
    }


def _platform_plans(
    platforms: list[str],
    source_checks: list[dict[str, object]],
    workflow_by_key: dict[tuple[str, str], dict[str, object]],
) -> list[dict[str, object]]:
    plans: list[dict[str, object]] = []
    for platform in platforms:
        platform_sources = [check for check in source_checks if check.get("platform") == platform]
        sync_workflow = workflow_by_key.get(("stepik_source_sync" if platform == "stepik" else "browser_live_sync", platform), {})
        blocked = [check for check in platform_sources if not check.get("ready")]
        plans.append(
            {
                "platform": platform,
                "ready": bool(sync_workflow.get("ready")),
                "source_count": len(platform_sources),
                "ready_source_count": len([check for check in platform_sources if check.get("ready")]),
                "blocked_source_count": len(blocked),
                "required_workflow": sync_workflow.get("name"),
                "required_workflow_ready": bool(sync_workflow.get("ready")),
                "blockers": _dedupe([blocker for check in blocked for blocker in check.get("blockers", [])]),
            }
        )
    return plans


def _stepik_sync_command(
    *,
    stepik_token_env: str,
    live_scope: str,
    include_step_sources: bool,
    source_id: str | None = None,
    run_suffix: str | None = None,
) -> str:
    run_id = f"stepik-live-sync-{run_suffix}" if run_suffix else "stepik-live-sync"
    command = (
        f"aoa-course sync stepik-live --run {shlex.quote(run_id)} "
        f"--token-env {shlex.quote(stepik_token_env)} --batch-size 20 "
    )
    if source_id:
        command += f"--source-id {shlex.quote(source_id)} "
    if live_scope == "full-course":
        command += "--full-course "
    else:
        command += "--max-sections 1 --max-units-per-section 2 --max-steps-per-lesson 5 "
    if include_step_sources:
        command += "--include-step-sources "
    return command + "--build-artifacts"


def _stepik_smoke_command(
    course_id: int,
    *,
    slug: str,
    access_mode: str,
    stepik_token_env: str,
    live_scope: str,
    include_step_sources: bool,
) -> str:
    command = (
        f"aoa-course smoke stepik-live {course_id} --run stepik-live-smoke-{slug} "
        f"--access-mode {shlex.quote(access_mode)} --token-env {shlex.quote(stepik_token_env)} --batch-size 20 "
    )
    if live_scope == "full-course":
        command += "--full-course "
    else:
        command += "--max-sections 1 --max-units-per-section 2 --max-steps-per-lesson 5 "
    if include_step_sources:
        command += "--include-step-sources "
    return command.rstrip()


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

    account_discovery_required = not bool(sources)
    workflows.append(
        {
            "name": "stepik_account_discovery",
            "platform": "stepik",
            "ready": token_present,
            "required_for_ready": account_discovery_required,
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
            "required_for_ready": True,
            "source_count": len(sources),
            "next_command": (
                "aoa-course sync stepik-live --run stepik-live-sync "
                "--batch-size 20 --max-sections 1 --max-units-per-section 2 "
                "--max-steps-per-lesson 5 --build-artifacts"
            ),
        }
    )
    token_blocked_sources = [
        source
        for source in sources
        if str(source.get("access_mode") or "") in {"api_token", "oauth"}
    ]
    if not token_present and (not sources or token_blocked_sources):
        next_commands.append(f"export {token_env}=<stepik-api-token>")
    if not sources:
        next_commands.append(f"aoa-course discover stepik-account --token-env {token_env} --register --max-pages 5")
    else:
        next_commands.append(
            "aoa-course sync stepik-live --run stepik-live-sync --batch-size 20 "
            "--max-sections 1 --max-units-per-section 2 --max-steps-per-lesson 5 "
            "--build-artifacts"
        )


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
    source_ready_flags: list[bool] = []
    for source in sources:
        source_host = _host(str(source.get("source_ref") or ""))
        source_state = (
            inspect_browser_state(state_file, expect_origin_contains=source_host)
            if source_host
            else state
        )
        source_state_ready = bool(source_state.get("usable"))
        blockers = []
        if not source_state_ready:
            if source_host and state_ready:
                blockers.append(f"browser storage state does not match source host {source_host}")
            else:
                blockers.append(f"browser storage state is {source_state.get('status')}")
        ready = source_state_ready and bool(source.get("enabled", True))
        source_ready_flags.append(ready)
        checks.append(_source_check(source, ready=ready, blockers=blockers))
    all_sources_ready = bool(sources) and all(source_ready_flags)

    workflows.append(
        {
            "name": "browser_live_discovery",
            "platform": platform,
            "ready": state_ready,
            "required_for_ready": True,
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
            "ready": all_sources_ready,
            "required_for_ready": True,
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
    elif all_sources_ready:
        next_commands.append(
            f"aoa-course sync browser-live --platform {platform} "
            f"--state-file {str(state_file)!r} --max-lessons 50 --build-artifacts"
        )
    else:
        next_commands.append(f"aoa-course auth inspect-browser-state {str(state_file)!r}")
        next_commands.append(f"aoa-course auth capture-browser-state {platform} account --login-url <login-or-account-url> --state-file {str(state_file)!r}")


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


def _state_file_arg(platform: str, state_file: Path | None) -> str:
    if state_file:
        return shlex.quote(str(state_file.expanduser()))
    return f'"$AOA_COURSE_AUTH_ROOT/{platform}/account.storage-state.json"'


def _command_touches_network(command: str) -> bool:
    return any(token in command for token in ["capture-browser-state", "discover ", "sync ", "smoke "])


def _source_slug(source: dict[str, object]) -> str:
    source_id = str(source.get("source_id") or "")
    seed = source_id.rsplit(":", maxsplit=1)[-1] if source_id else str(source.get("source_ref") or "source")
    slug = re.sub(r"[^a-z0-9]+", "-", seed.casefold()).strip("-")
    return slug[:48] or "source"


def _stepik_course_id(source_ref: str) -> int | None:
    text = source_ref.strip()
    if text.isdigit():
        return int(text)
    match = re.search(r"(?:stepik\.org/)?course/(\d+)", text)
    return int(match.group(1)) if match else None


def _dedupe(values: list[str]) -> list[str]:
    return [value for value in dict.fromkeys(values) if value]
