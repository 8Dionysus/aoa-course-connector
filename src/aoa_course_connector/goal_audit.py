"""Read-only audit of the connector goal and remaining live prerequisites."""

from __future__ import annotations

import subprocess
from pathlib import Path

from aoa_course_connector.adapters import adapter_list
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.status import DEFAULT_CONNECTED_RUN, DEFAULT_RUN, connector_readiness


REQUIRED_SCHEMA_FILES = [
    "connector/schemas/course.schema.json",
    "connector/schemas/course_source.schema.json",
    "connector/schemas/module.schema.json",
    "connector/schemas/lesson.schema.json",
    "connector/schemas/step.schema.json",
    "connector/schemas/asset.schema.json",
    "connector/schemas/transcript.schema.json",
    "connector/schemas/assignment.schema.json",
    "connector/schemas/comment_thread.schema.json",
    "connector/schemas/comment.schema.json",
    "connector/schemas/progress.schema.json",
    "connector/schemas/entity.schema.json",
    "connector/schemas/topic.schema.json",
    "connector/schemas/evidence.schema.json",
    "connector/schemas/ingest_run.schema.json",
    "connector/schemas/sync_checkpoint.schema.json",
]
REQUIRED_DOCS = [
    "README.md",
    "docs/INSTALL.md",
    "docs/ARCHITECTURE.md",
    "docs/STORAGE_CONTRACT.md",
    "docs/AUTH_SESSION.md",
    "docs/ADAPTER_GUIDE.md",
    "docs/GETCOURSE.md",
    "docs/SKILLSPACE.md",
    "docs/CLEAN_API_ADAPTERS.md",
    "docs/STEPIK.md",
    "docs/CLI_USAGE.md",
    "docs/MCP_USAGE.md",
    "docs/PRIVACY_SECURITY.md",
    "docs/TROUBLESHOOTING.md",
    "docs/STATUS.md",
]
REQUIRED_PACKAGE_PATHS = [
    "src/aoa_course_connector/core",
    "src/aoa_course_connector/adapters",
    "src/aoa_course_connector/auth",
    "src/aoa_course_connector/ingest",
    "src/aoa_course_connector/normalize",
    "src/aoa_course_connector/evidence",
    "src/aoa_course_connector/storage",
    "src/aoa_course_connector/index",
    "src/aoa_course_connector/graph",
    "src/aoa_course_connector/query",
    "src/aoa_course_connector/mcp",
]
WORKING_PLATFORMS = ["getcourse", "skillspace", "stepik"]
FUTURE_PLATFORMS = ["moodle", "canvas", "coursera", "teachable", "thinkific", "kajabi"]
LIVE_REMAINING = [
    {
        "id": "getcourse_live_calibration",
        "platform": "getcourse",
        "reason": "requires operator-owned account and local browser storage state",
        "next_commands": [
            "aoa-course auth plan-browser-state getcourse <source-url>",
            "aoa-course preflight connected-plan --platform getcourse --live-scope bounded",
        ],
    },
    {
        "id": "skillspace_live_calibration",
        "platform": "skillspace",
        "reason": "requires operator-owned account and local browser storage state",
        "next_commands": [
            "aoa-course auth plan-browser-state skillspace <source-url>",
            "aoa-course preflight connected-plan --platform skillspace --live-scope bounded",
        ],
    },
    {
        "id": "stepik_authenticated_full_course",
        "platform": "stepik",
        "reason": "requires operator-selected authenticated course/token for full-course source enrichment calibration",
        "next_commands": [
            "aoa-course preflight live --platform stepik",
            "aoa-course preflight connected-plan --platform stepik --live-scope full-course --include-step-sources",
        ],
    },
    {
        "id": "external_embedding_endpoint_live_calibration",
        "platform": "semantic",
        "reason": "requires operator-selected embedding endpoint and token env outside CI",
        "next_commands": [
            "aoa-course preflight semantic-provider --run <connected-run> --provider http_json_v1 --embedding-endpoint <url> --embedding-model <model> --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN --require-ready",
            "aoa-course build-semantic-index --run <connected-run> --provider http_json_v1 --embedding-endpoint <url> --embedding-model <model> --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN",
            "aoa-course query \"course-specific question\" --run <connected-run> --mode semantic",
        ],
    },
]


def goal_audit(
    repo_root: Path,
    roots: StorageRoots,
    *,
    runs: list[str] | None = None,
    connected_run: str = DEFAULT_CONNECTED_RUN,
    mcp_tool_names: list[str] | set[str] | None = None,
) -> dict[str, object]:
    """Return a read-only DoD-oriented audit for agents continuing the goal."""

    selected_runs = [str(run) for run in (runs or [DEFAULT_RUN]) if str(run)]
    readiness = connector_readiness(
        repo_root,
        roots,
        runs=selected_runs,
        connected_run=connected_run,
        mcp_tool_names=mcp_tool_names,
    )
    adapters = {str(adapter.get("platform")): adapter for adapter in adapter_list()}
    git_state = _git_state(repo_root)
    requirements = [
        _path_requirement(
            "public_ready_repo",
            "coherent public-ready repository surface",
            repo_root,
            ["AGENTS.md", "README.md", "CHARTER.md", "BOUNDARIES.md", "ROADMAP.md", "CHANGELOG.md", "pyproject.toml"],
            evidence_commands=["python scripts/validate_connector.py"],
        ),
        _path_requirement(
            "package_structure",
            "real package/module structure",
            repo_root,
            REQUIRED_PACKAGE_PATHS,
            evidence_commands=["PYTHONPATH=src python -m compileall -q src tests scripts"],
        ),
        _storage_requirement(repo_root),
        _path_requirement(
            "canonical_schemas",
            "canonical course knowledge schemas",
            repo_root,
            REQUIRED_SCHEMA_FILES,
            evidence_commands=["python scripts/validate_connector.py"],
        ),
        _adapter_requirement("reference_ingestion_path", adapters, ["stepik"], "working clean API/reference ingestion path"),
        _adapter_requirement("hard_adapter_scaffolding", adapters, ["getcourse", "skillspace"], "hard browser-session adapter scaffolding and strategy"),
        _runtime_requirement(
            "local_index_graph_query",
            "local normalized bundle, index, graph, query, and fixture connected-run evidence",
            readiness,
            bool(readiness.get("operational_ready"))
            and bool(isinstance(readiness.get("lanes"), dict) and readiness["lanes"].get("connected_run_receipt_ready")),
            readiness.get("next_commands", []),
            evidence_commands=[
                "aoa-course bootstrap fixture --run starter-fixture --connected-run connected-calibration",
                "aoa-course readiness --run starter-fixture --connected-run connected-calibration --require-ready",
            ],
        ),
        _runtime_requirement(
            "mcp_surface",
            "MCP tools for readiness, search, context, graph, freshness, and evidence",
            readiness,
            bool(isinstance(readiness.get("mcp"), dict) and readiness["mcp"].get("ready")),
            ["aoa-course mcp tools"],
            evidence_commands=["aoa-course mcp tools"],
        ),
        _path_requirement(
            "tests_and_evals",
            "tests and evals proving the core retrieval loop",
            repo_root,
            [
                "tests/integration/test_cli_smoke.py",
                "tests/unit/test_fixture_index_graph.py",
                "evals/suites/answer-quality.suite.md",
                "evals/suites/freshness-ranking.suite.md",
                "evals/suites/authority-ranking.suite.md",
                "evals/suites/live-calibration.suite.md",
            ],
            evidence_commands=["PYTHONPATH=src python -m pytest -q"],
        ),
        _path_requirement(
            "install_connect_ingest_query_docs",
            "docs sufficient for a fresh agent to install, connect, ingest, and query",
            repo_root,
            REQUIRED_DOCS,
            evidence_commands=["python scripts/verify_agent_install_route.py --skip-pytest"],
        ),
        _privacy_requirement(repo_root),
        _future_platform_requirement(adapters),
        _git_requirement(git_state),
    ]
    action_required = [item for item in requirements if item["status"] == "action_required"]
    blocking_action_required = [item for item in action_required if item.get("blocks_ready_for_connection", True)]
    ready_for_operator_connection = not blocking_action_required
    remaining_live = [
        {
            "status": "requires_operator_live_access",
            **item,
        }
        for item in LIVE_REMAINING
    ]
    connection_handoff = _connection_handoff(
        readiness,
        remaining_live=remaining_live,
        selected_runs=selected_runs,
        connected_run=connected_run,
    )
    return {
        "schema": "aoa_course_goal_audit_v1",
        "tool": "goal_audit",
        "status": "ready_for_operator_connection" if ready_for_operator_connection else "action_required",
        "goal_complete": False,
        "ready_for_operator_connection": ready_for_operator_connection,
        "network_touched": False,
        "read_only": True,
        "repo_root": str(repo_root),
        "runs": selected_runs,
        "connected_run": connected_run,
        "summary": {
            "requirement_count": len(requirements),
            "proved_count": len([item for item in requirements if item["status"] == "proved"]),
            "action_required_count": len(action_required),
            "blocking_action_required_count": len(blocking_action_required),
            "remaining_live_requirement_count": len(remaining_live),
        },
        "requirements": requirements,
        "remaining_live_requirements": remaining_live,
        "readiness": {
            "schema": readiness.get("schema"),
            "status": readiness.get("status"),
            "operational_ready": bool(readiness.get("operational_ready")),
            "connected_live_ready": bool(readiness.get("connected_live_ready")),
            "lanes": readiness.get("lanes", {}),
            "next_commands": readiness.get("next_commands", []),
        },
        "connection_handoff": connection_handoff,
        "git": git_state,
        "next_commands": _dedupe(
            [command for item in blocking_action_required for command in item.get("next_commands", [])]
            or [command for item in remaining_live for command in item.get("next_commands", [])]
        ),
    }


def write_connection_handoff(report: dict[str, object], path: Path) -> dict[str, object]:
    """Write the goal audit connection handoff as a redacted runtime Markdown file."""

    target = path.expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_connection_handoff(report), encoding="utf-8")
    return {
        "path": str(target),
        "written": True,
        "format": "markdown",
        "network_touched": False,
        "redacted": True,
    }


def render_connection_handoff(report: dict[str, object]) -> str:
    """Render a connection handoff without secret values or private payloads."""

    handoff = report.get("connection_handoff") if isinstance(report.get("connection_handoff"), dict) else {}
    lines = [
        "# Course Connector Connection Handoff",
        "",
        "This file is runtime operator handoff state. Keep it outside Git.",
        "",
        "## Summary",
        "",
        f"- status: `{handoff.get('status')}`",
        f"- ready_for_operator_connection: `{bool(report.get('ready_for_operator_connection'))}`",
        f"- goal_complete: `{bool(report.get('goal_complete'))}`",
        f"- network_touched: `{bool(handoff.get('network_touched'))}`",
        f"- connected_run: `{handoff.get('connected_run')}`",
    ]
    inputs = _dict_items(handoff.get("operator_inputs_needed"))
    if inputs:
        lines.extend(["", "## Operator Inputs", ""])
        for item in inputs:
            label = str(item.get("label") or item.get("kind") or "input")
            lines.append(f"- `{item.get('platform')}` {label}: {item.get('description')}")

    browser = _dict_items(handoff.get("browser_auth"))
    if browser:
        lines.extend(["", "## Browser Auth", ""])
        for item in browser:
            lines.extend(
                [
                    f"### {item.get('platform')}",
                    "",
                    f"- ready: `{bool(item.get('ready'))}`",
                    f"- state_file: `{item.get('state_file')}`",
                    f"- source_hosts: `{', '.join([str(host) for host in item.get('source_hosts', [])])}`",
                ]
            )
            blockers = [str(blocker) for blocker in item.get("blockers", [])] if isinstance(item.get("blockers"), list) else []
            if blockers:
                lines.append("- blockers:")
                lines.extend([f"  - {blocker}" for blocker in blockers])
            commands = item.get("commands") if isinstance(item.get("commands"), dict) else {}
            if commands:
                lines.extend(["", "Commands:"])
                for label in ["plan", "capture", "inspect", "recheck"]:
                    command = str(commands.get(label) or "")
                    if command:
                        lines.extend([f"- {label}:", "  ```bash", f"  {command}", "  ```"])
            candidates = _dict_items(item.get("state_file_candidates"))
            if candidates:
                lines.extend(["", "Per-host candidates:"])
                for candidate in candidates:
                    lines.append(f"- `{candidate.get('host')}` -> `{candidate.get('state_file')}`")
                    candidate_commands = candidate.get("commands") if isinstance(candidate.get("commands"), dict) else {}
                    for label in ["capture", "inspect", "recheck"]:
                        command = str(candidate_commands.get(label) or "")
                        if command:
                            lines.extend(["  ```bash", f"  {command}", "  ```"])
            lines.append("")

    for section_name, key in [("Stepik", "stepik"), ("Semantic Provider", "semantic_provider")]:
        section = handoff.get(key) if isinstance(handoff.get(key), dict) else {}
        if not section:
            continue
        lines.extend([f"## {section_name}", ""])
        for command in [str(command) for command in section.get("commands", []) if str(command)] if isinstance(section.get("commands"), list) else []:
            lines.extend(["```bash", command, "```", ""])

    mcp_commands = [str(command) for command in handoff.get("mcp_commands", [])] if isinstance(handoff.get("mcp_commands"), list) else []
    if mcp_commands:
        lines.extend(["## MCP Commands", ""])
        for command in mcp_commands:
            lines.extend(["```bash", command, "```", ""])
    return "\n".join(lines).rstrip() + "\n"


def _connection_handoff(
    readiness: dict[str, object],
    *,
    remaining_live: list[dict[str, object]],
    selected_runs: list[str],
    connected_run: str,
) -> dict[str, object]:
    connected_plan = readiness.get("connected_source_plan") if isinstance(readiness.get("connected_source_plan"), dict) else {}
    browser_auth = [
        _browser_handoff_item(item)
        for item in _dict_items(connected_plan.get("browser_auth_handoffs"))
    ]
    semantic_preflights = _dict_items(readiness.get("semantic_provider_preflight"))
    stepik_commands = _remaining_commands(remaining_live, "stepik")
    semantic_commands = _remaining_commands(remaining_live, "semantic")
    return {
        "schema": "aoa_course_connection_handoff_v1",
        "status": "operator_action_required",
        "network_touched": False,
        "read_only": True,
        "redacted": True,
        "runs": selected_runs,
        "connected_run": connected_run,
        "operator_inputs_needed": _operator_inputs_needed(remaining_live),
        "browser_auth": browser_auth,
        "stepik": {
            "commands": stepik_commands,
            "live_scope": "full-course",
            "include_step_sources": True,
            "token_env": "STEPIK_API_TOKEN",
        },
        "semantic_provider": {
            "commands": semantic_commands,
            "preflights": semantic_preflights,
            "token_env": "AOA_COURSE_EMBEDDING_TOKEN",
            "provider": "http_json_v1",
        },
        "connected_run_handoff": connected_plan.get("connected_run_handoff", {}),
        "mcp_commands": [
            'aoa-course mcp call connector_readiness \'{"runs":["starter-fixture"]}\'',
            'aoa-course mcp call connected_source_plan \'{"live_scope":"bounded"}\'',
            'aoa-course mcp call semantic_provider_preflight \'{"run":"starter-fixture"}\'',
            f'aoa-course mcp call goal_audit \'{{"runs":["starter-fixture"],"connected_run":"{connected_run}"}}\'',
        ],
        "next_commands": _dedupe(
            [
                command
                for item in browser_auth
                for command in _handoff_commands(item)
            ]
            + stepik_commands
            + semantic_commands
        ),
    }


def _browser_handoff_item(handoff: dict[str, object]) -> dict[str, object]:
    return {
        "platform": handoff.get("platform"),
        "ready": bool(handoff.get("ready")),
        "state_file": handoff.get("state_file"),
        "state_status": handoff.get("state_status"),
        "expected_origin_contains": handoff.get("expected_origin_contains"),
        "source_hosts": handoff.get("source_hosts", []),
        "blocked_source_hosts": handoff.get("blocked_source_hosts", []),
        "host_readiness": handoff.get("host_readiness", []),
        "state_file_candidates": handoff.get("state_file_candidates", []),
        "blockers": handoff.get("blockers", []),
        "commands": handoff.get("commands", {}),
    }


def _operator_inputs_needed(remaining_live: list[dict[str, object]]) -> list[dict[str, object]]:
    inputs = []
    for item in remaining_live:
        platform = str(item.get("platform") or "")
        if platform in {"getcourse", "skillspace"}:
            inputs.extend(
                [
                    {
                        "kind": "source_url",
                        "platform": platform,
                        "label": "operator-owned course URL",
                        "description": "A real course/catalog URL from the connected user's authorized account.",
                    },
                    {
                        "kind": "browser_auth_state",
                        "platform": platform,
                        "label": "browser storage state",
                        "description": "A local Playwright storage-state file captured after legitimate login.",
                    },
                ]
            )
        elif platform == "stepik":
            inputs.append(
                {
                    "kind": "token_env",
                    "platform": platform,
                    "label": "STEPIK_API_TOKEN",
                    "description": "A token/env route for authenticated full-course and source-enrichment calibration.",
                }
            )
        elif platform == "semantic":
            inputs.extend(
                [
                    {
                        "kind": "embedding_endpoint",
                        "platform": platform,
                        "label": "embedding endpoint URL",
                        "description": "Operator-selected http_json_v1 embedding endpoint.",
                    },
                    {
                        "kind": "token_env",
                        "platform": platform,
                        "label": "AOA_COURSE_EMBEDDING_TOKEN",
                        "description": "Environment variable holding the embedding endpoint token.",
                    },
                ]
            )
    return inputs


def _remaining_commands(remaining_live: list[dict[str, object]], platform: str) -> list[str]:
    for item in remaining_live:
        if item.get("platform") == platform:
            return [str(command) for command in item.get("next_commands", []) if str(command)] if isinstance(item.get("next_commands"), list) else []
    return []


def _handoff_commands(handoff: dict[str, object]) -> list[str]:
    commands: list[str] = []
    raw_commands = handoff.get("commands") if isinstance(handoff.get("commands"), dict) else {}
    commands.extend([str(command) for command in raw_commands.values() if isinstance(command, str) and command])
    inspect_hosts = raw_commands.get("inspect_source_hosts")
    if isinstance(inspect_hosts, list):
        commands.extend([str(command) for command in inspect_hosts if str(command)])
    for candidate in _dict_items(handoff.get("state_file_candidates")):
        candidate_commands = candidate.get("commands") if isinstance(candidate.get("commands"), dict) else {}
        commands.extend([str(command) for command in candidate_commands.values() if isinstance(command, str) and command])
    return commands


def _dict_items(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _path_requirement(
    requirement_id: str,
    title: str,
    repo_root: Path,
    paths: list[str],
    *,
    evidence_commands: list[str],
) -> dict[str, object]:
    missing = [path for path in paths if not (repo_root / path).exists()]
    return {
        "id": requirement_id,
        "title": title,
        "status": "proved" if not missing else "action_required",
        "evidence": [path for path in paths if path not in missing],
        "missing": missing,
        "evidence_commands": evidence_commands,
        "next_commands": evidence_commands if missing else [],
        "blocks_ready_for_connection": True,
    }


def _storage_requirement(repo_root: Path) -> dict[str, object]:
    env_vars = ["AOA_COURSE_DATA_ROOT", "AOA_COURSE_CACHE_ROOT", "AOA_COURSE_AUTH_ROOT", "AOA_COURSE_ARTIFACT_ROOT"]
    storage_doc = (repo_root / "connector" / "STORAGE_POLICY.md").read_text(encoding="utf-8") if (repo_root / "connector" / "STORAGE_POLICY.md").exists() else ""
    gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8") if (repo_root / ".gitignore").exists() else ""
    missing_vars = [var for var in env_vars if var not in storage_doc]
    gitignored = all(pattern in gitignore for pattern in [".connector-state/*", ".connector-state/data/*", ".connector-state/auth/*", "*.storage-state.json"])
    return {
        "id": "portable_storage_contract",
        "title": "portable env storage roots and gitignored heavy/private paths",
        "status": "proved" if not missing_vars and gitignored else "action_required",
        "evidence": ["connector/STORAGE_POLICY.md", ".gitignore"],
        "missing": missing_vars + ([] if gitignored else ["gitignore connector-state policy"]),
        "evidence_commands": ["aoa-course storage status"],
        "next_commands": ["update connector/STORAGE_POLICY.md and .gitignore"] if missing_vars or not gitignored else [],
        "blocks_ready_for_connection": True,
    }


def _adapter_requirement(requirement_id: str, adapters: dict[str, dict[str, object]], platforms: list[str], title: str) -> dict[str, object]:
    missing = [platform for platform in platforms if platform not in adapters]
    not_working = [platform for platform in platforms if platform in adapters and not str(adapters[platform].get("status") or "").startswith("working_")]
    return {
        "id": requirement_id,
        "title": title,
        "status": "proved" if not missing and not not_working else "action_required",
        "evidence": [adapters[platform] for platform in platforms if platform in adapters],
        "missing": missing + [f"{platform}:working_status" for platform in not_working],
        "evidence_commands": ["aoa-course adapters list"],
        "next_commands": ["aoa-course adapters list"] if missing or not_working else [],
        "blocks_ready_for_connection": True,
    }


def _runtime_requirement(
    requirement_id: str,
    title: str,
    readiness: dict[str, object],
    ready: bool,
    next_commands: object,
    *,
    evidence_commands: list[str],
) -> dict[str, object]:
    return {
        "id": requirement_id,
        "title": title,
        "status": "proved" if ready else "action_required",
        "evidence": [{"readiness_status": readiness.get("status"), "lanes": readiness.get("lanes", {})}],
        "missing": [] if ready else ["runtime readiness"],
        "evidence_commands": evidence_commands,
        "next_commands": [str(command) for command in next_commands if str(command)] if isinstance(next_commands, list) and not ready else [],
        "blocks_ready_for_connection": True,
    }


def _privacy_requirement(repo_root: Path) -> dict[str, object]:
    source_policy = repo_root / "connector" / "SOURCE_POLICY.md"
    privacy_doc = repo_root / "docs" / "PRIVACY_SECURITY.md"
    route_allowlist = repo_root / "connector" / "manifests" / "route_allowlist.yaml"
    missing = [str(path.relative_to(repo_root)) for path in [source_policy, privacy_doc, route_allowlist] if not path.exists()]
    return {
        "id": "privacy_and_secret_boundary",
        "title": "no committed secrets/private course data and explicit authorized-access boundary",
        "status": "proved" if not missing else "action_required",
        "evidence": [path for path in ["connector/SOURCE_POLICY.md", "docs/PRIVACY_SECURITY.md", "connector/manifests/route_allowlist.yaml"] if path not in missing],
        "missing": missing,
        "evidence_commands": ["python scripts/validate_connector.py"],
        "next_commands": ["python scripts/validate_connector.py"] if missing else [],
        "blocks_ready_for_connection": True,
    }


def _future_platform_requirement(adapters: dict[str, dict[str, object]]) -> dict[str, object]:
    missing = [platform for platform in WORKING_PLATFORMS + FUTURE_PLATFORMS if platform not in adapters]
    return {
        "id": "extensible_platform_topology",
        "title": "working and future platform topology remains machine-readable",
        "status": "proved" if not missing else "action_required",
        "evidence": [adapters[platform] for platform in WORKING_PLATFORMS + FUTURE_PLATFORMS if platform in adapters],
        "missing": missing,
        "evidence_commands": ["aoa-course adapters list"],
        "next_commands": ["aoa-course adapters list"] if missing else [],
        "blocks_ready_for_connection": True,
    }


def _git_requirement(git_state: dict[str, object]) -> dict[str, object]:
    clean = bool(git_state.get("clean"))
    on_main = str(git_state.get("branch") or "") == "main"
    synced = bool(git_state.get("synced_with_origin"))
    return {
        "id": "current_landing_state",
        "title": "current checkout is landed on main and synced with origin",
        "status": "proved" if clean and on_main and synced else "action_required",
        "evidence": [git_state],
        "missing": [] if clean and on_main and synced else ["clean main synced with origin"],
        "evidence_commands": ["git status --short --branch"],
        "next_commands": ["landing: commit, push, PR, checks, merge, post-merge verify"] if not (clean and on_main and synced) else [],
        "blocks_ready_for_connection": False,
    }


def _git_state(repo_root: Path) -> dict[str, object]:
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {"available": False, "error": str(exc)}
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    branch_line = lines[0] if lines else ""
    branch = branch_line.removeprefix("## ").split("...")[0].strip()
    return {
        "available": result.returncode == 0,
        "branch": branch,
        "status_line": branch_line,
        "clean": result.returncode == 0 and len(lines) == 1,
        "synced_with_origin": result.returncode == 0 and branch_line.endswith("...origin/main"),
    }


def _dedupe(commands: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for command in commands:
        if command in seen:
            continue
        seen.add(command)
        deduped.append(command)
    return deduped
