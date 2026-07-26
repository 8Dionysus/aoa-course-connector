#!/usr/bin/env python3
"""Run the fixture-safe release scenarios with named receipts."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from aoa_course_connector.adapters import ADAPTERS


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_BROWSER_COVERAGE = {"account_discovery", "course_tree", "lesson_page"}
FORBIDDEN_ARGUMENTS = {
    "--allow-network",
    "--api-token",
    "--embedding-token-env",
    "--state-file",
    "--token",
}
QUERY_BY_PLATFORM = {
    "getcourse": "GetCourse bootloader rollback evidence",
    "skillspace": "Skillspace logcat bugreport evidence",
}


@dataclass(frozen=True)
class Scenario:
    id: str
    family: str
    argv: tuple[str, ...]
    platform: str = ""


class ScenarioPlanError(ValueError):
    pass


def scenario(id: str, family: str, command: str, *, platform: str = "") -> Scenario:
    return Scenario(id, family, tuple(shlex.split(command)), platform)


FIXED_PREFIX = (
    ("core:doctor", "core", "aoa-course doctor"),
    ("starter:materialize", "starter", "aoa-course materialize fixture --run starter-fixture"),
    ("starter:build-index", "starter", "aoa-course build-index --run starter-fixture"),
    ("starter:build-graph", "starter", "aoa-course build-graph --run starter-fixture"),
    ("starter:answer", "starter", "aoa-course answer 'bootloader unlock rollback' --run starter-fixture"),
    ("starter:eval-answer-packets", "starter", "aoa-course eval answer-packets"),
    ("stepik:materialize", "stepik", "aoa-course materialize stepik-fixture --run stepik-fixture"),
    ("stepik:build-index", "stepik", "aoa-course build-index --run stepik-fixture"),
    ("stepik:build-graph", "stepik", "aoa-course build-graph --run stepik-fixture"),
    ("stepik:answer", "stepik", "aoa-course answer 'Stepik public API evidence' --run stepik-fixture"),
    ("stepik:eval-clean-api", "stepik", "aoa-course eval clean-api"),
)

FIXED_MIDDLE = (
    ("sources:list", "sources", "aoa-course sources list"),
    ("eval:install-route", "install", "aoa-course eval install-route"),
    (
        "starter:bootstrap",
        "starter",
        "aoa-course bootstrap fixture --run starter-fixture --connected-run connected-calibration",
    ),
    (
        "sources:answer-stepik",
        "sources",
        "aoa-course sources answer 'Stepik public API evidence' --platform stepik --mode hybrid",
    ),
    (
        "eval:source-registry-query",
        "sources",
        "aoa-course eval source-registry-query --query 'Stepik public API evidence' "
        "--query 'canonical course objects' --platform stepik --kind smoke --mode hybrid",
    ),
    ("eval:browser-discovery", "browser-discovery", "aoa-course eval browser-discovery"),
    (
        "browser:sync",
        "browser-sync",
        "aoa-course sync browser-fixture --run browser-sync-fixture --build-artifacts",
    ),
    ("browser:sync-status", "browser-sync", "aoa-course sync status --run browser-sync-fixture"),
    ("eval:browser-sync", "browser-sync", "aoa-course eval browser-sync"),
    (
        "mcp:sync-status",
        "browser-sync",
        "aoa-course mcp call sync_status '{\"sync_run\":\"browser-sync-fixture\"}'",
    ),
)

FIXED_BETWEEN = (
    ("eval:browser-hard-adapters", "browser-materialize", "aoa-course eval browser-hard-adapters"),
)

FIXED_SUFFIX = (
    ("eval:browser-crawl", "browser-crawl", "aoa-course eval browser-crawl"),
    ("mcp:tools", "mcp", "aoa-course mcp tools"),
    (
        "install:verify-agent-route",
        "install",
        "python scripts/verify_agent_install_route.py --skip-pytest",
    ),
)


def fixed(specs: tuple[tuple[str, str, str], ...]) -> tuple[Scenario, ...]:
    return tuple(scenario(*spec) for spec in specs)


def working_browser_platforms(
    adapters: Mapping[str, Mapping[str, object]] = ADAPTERS,
) -> tuple[str, ...]:
    selected: list[str] = []
    for name, adapter in adapters.items():
        if (
            adapter.get("status")
            == "working_browser_session_discovery_and_crawl_adapter"
            and "browser_session" in adapter.get("auth_modes", [])
            and REQUIRED_BROWSER_COVERAGE <= set(adapter.get("coverage", []))
        ):
            if adapter.get("platform") != name:
                raise ScenarioPlanError(f"{name}: adapter platform identity drifted")
            selected.append(name)
    return tuple(sorted(selected))


def browser_scenarios(platform: str) -> tuple[Scenario, ...]:
    query = QUERY_BY_PLATFORM.get(platform, f"{platform} course-specific evidence")
    items = [
        scenario(
            f"browser:{platform}:discovery",
            "browser-discovery",
            f"aoa-course discover browser-fixture --platform {platform} "
            f"--run {platform}-browser-discovery-fixture --register",
            platform=platform,
        )
    ]
    for mode in ("materialize", "crawl"):
        run_id = (
            f"{platform}-browser-fixture"
            if mode == "materialize"
            else f"{platform}-browser-crawl-fixture"
        )
        family = f"browser-{mode}"
        commands = (
            (mode, f"aoa-course {mode} browser-fixture --platform {platform} --run {run_id}"),
            ("build-index", f"aoa-course build-index --run {run_id}"),
            ("build-graph", f"aoa-course build-graph --run {run_id}"),
            ("answer", f"aoa-course answer {shlex.quote(query)} --run {run_id}"),
        )
        items.extend(
            scenario(
                f"browser:{platform}:{mode}"
                + ("" if suffix == mode else f":{suffix}"),
                family,
                command,
                platform=platform,
            )
            for suffix, command in commands
        )
    return tuple(items)


def build_scenarios(
    adapters: Mapping[str, Mapping[str, object]] = ADAPTERS,
) -> tuple[Scenario, ...]:
    platforms = working_browser_platforms(adapters)
    browser = {platform: browser_scenarios(platform) for platform in platforms}
    plan = (
        *fixed(FIXED_PREFIX),
        *(browser[platform][0] for platform in platforms),
        *fixed(FIXED_MIDDLE),
        *(item for platform in platforms for item in browser[platform][1:5]),
        *fixed(FIXED_BETWEEN),
        *(item for platform in platforms for item in browser[platform][5:]),
        *fixed(FIXED_SUFFIX),
    )
    validate_scenario_plan(plan, platforms)
    return plan


def validate_scenario_plan(
    scenarios: tuple[Scenario, ...],
    browser_platforms: tuple[str, ...],
) -> None:
    problems: list[str] = []
    ids = [item.id for item in scenarios]
    commands = [item.argv for item in scenarios]
    if len(ids) != len(set(ids)):
        problems.append("scenario IDs must be unique")
    if len(commands) != len(set(commands)):
        problems.append("scenario commands must be unique")
    if not scenarios or scenarios[-1].id != "install:verify-agent-route":
        problems.append("installed-route verification must remain final")
    for item in scenarios:
        if not item.argv or item.argv[0] not in {"aoa-course", "python"}:
            problems.append(f"{item.id}: unsupported executable")
        denied = {
            flag
            for flag in FORBIDDEN_ARGUMENTS
            if any(arg == flag or arg.startswith(f"{flag}=") for arg in item.argv)
        }
        if denied:
            problems.append(f"{item.id}: denied offline arguments {sorted(denied)}")
        if item.argv[0] == "python" and item.id != "install:verify-agent-route":
            problems.append(f"{item.id}: unreviewed direct Python command")
    for platform in browser_platforms:
        expected = {item.id for item in browser_scenarios(platform)}
        actual = {item.id for item in scenarios if item.platform == platform}
        if missing := expected - actual:
            problems.append(f"{platform}: missing browser scenarios {sorted(missing)}")
    unexpected = {
        item.platform
        for item in scenarios
        if item.platform and item.platform not in browser_platforms
    }
    if unexpected:
        problems.append(f"unexpected browser platforms {sorted(unexpected)}")
    if problems:
        raise ScenarioPlanError("; ".join(problems))


def execute_scenarios(
    scenarios: tuple[Scenario, ...],
    *,
    repo_root: Path = REPO_ROOT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> int:
    for index, item in enumerate(scenarios, 1):
        print(f"[{index:02d}/{len(scenarios):02d}] {item.id}", flush=True)
        started = time.monotonic()
        result = runner(list(item.argv), cwd=repo_root, check=False)
        receipt = {
            "schema": "aoa_course_release_scenario_receipt_v1",
            "id": item.id,
            "family": item.family,
            "platform": item.platform,
            "status": "passed" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "elapsed_seconds": round(time.monotonic() - started, 6),
        }
        print(
            json.dumps(receipt, sort_keys=True),
            file=sys.stdout if result.returncode == 0 else sys.stderr,
            flush=True,
        )
        if result.returncode:
            return result.returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without executing")
    parser.add_argument("--list-json", action="store_true", help="print the expanded plan")
    args = parser.parse_args()
    scenarios = build_scenarios()
    if args.list_json:
        print(
            json.dumps(
                {
                    "schema": "aoa_course_release_scenario_plan_v1",
                    "browser_platforms": list(working_browser_platforms()),
                    "scenario_count": len(scenarios),
                    "scenarios": [
                        {
                            "id": item.id,
                            "family": item.family,
                            "platform": item.platform,
                            "argv": list(item.argv),
                        }
                        for item in scenarios
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    return 0 if args.check else execute_scenarios(scenarios)


if __name__ == "__main__":
    raise SystemExit(main())
