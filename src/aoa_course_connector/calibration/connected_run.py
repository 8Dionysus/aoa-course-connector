"""Executable connected-source calibration runs.

The connected run receipt is the bridge between the read-only launch plan and
field calibration evidence. Fixture mode proves the full contract without
network access; live mode is gated behind explicit operator approval.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aoa_course_connector.calibration import (
    build_live_calibration_intake,
    build_live_calibration_packet,
    load_json_report,
    write_live_calibration_intake,
    write_live_calibration_packet,
)
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.readiness import connected_source_plan, live_preflight, write_connected_source_runbook
from aoa_course_connector.smoke import smoke_browser_fixture, smoke_browser_live, smoke_stepik_fixture, smoke_stepik_live
from aoa_course_connector.sources import load_registry, registry_path
from aoa_course_connector.storage import create_storage_roots, run_artifact_dir
from aoa_course_connector.sync import (
    sync_browser_fixture_sources,
    sync_browser_live_sources,
    sync_stepik_fixture_sources,
    sync_stepik_live_sources,
)
from aoa_course_connector.sync.stepik import STEPIK_FIXTURE_COURSE_ID, parse_stepik_course_id


BROWSER_PLATFORMS = {"getcourse", "skillspace"}
CONNECTED_PLATFORMS = {"getcourse", "skillspace", "stepik"}
RUN_MODES = {"fixture", "live"}
LIVE_SCOPES = {"bounded", "full-course"}
CONNECTED_RECEIPT_NAME = "connected_calibration_receipt.json"


def connected_calibration_receipt_path(roots: StorageRoots, run_id: str) -> Path:
    """Return the runtime receipt path for a connected calibration run."""

    return _connected_dir(roots, run_id) / CONNECTED_RECEIPT_NAME


def load_connected_calibration_status(roots: StorageRoots, *, run_id: str) -> dict[str, object]:
    """Load a redacted status packet for a connected calibration receipt."""

    path = connected_calibration_receipt_path(roots, run_id)
    if not path.exists():
        return {
            "schema": "aoa_course_connected_calibration_run_status_v1",
            "status": "missing",
            "exists": False,
            "run_id": run_id,
            "receipt_path": str(path),
            "network_touched": False,
            "read_only": True,
        }
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "schema": "aoa_course_connected_calibration_run_status_v1",
            "status": "error",
            "exists": True,
            "run_id": run_id,
            "receipt_path": str(path),
            "error": f"invalid connected calibration receipt JSON: {exc}",
            "network_touched": False,
            "read_only": True,
        }
    artifacts = receipt.get("artifacts") if isinstance(receipt.get("artifacts"), dict) else {}
    return {
        "schema": "aoa_course_connected_calibration_run_status_v1",
        "status": receipt.get("status") or "unknown",
        "exists": True,
        "run_id": receipt.get("run_id") or run_id,
        "receipt_schema": receipt.get("schema"),
        "receipt_path": str(path),
        "mode": receipt.get("mode"),
        "platforms": receipt.get("platforms", []),
        "source_ids": receipt.get("source_ids", []),
        "live_scope": receipt.get("live_scope"),
        "include_step_sources": bool(receipt.get("include_step_sources")),
        "allow_network": bool(receipt.get("allow_network")),
        "network_touched": bool(receipt.get("network_touched")),
        "stage_count": receipt.get("stage_count"),
        "stages": receipt.get("stages", []),
        "quality": receipt.get("quality") if isinstance(receipt.get("quality"), dict) else {},
        "privacy": receipt.get("privacy") if isinstance(receipt.get("privacy"), dict) else {},
        "failures": receipt.get("failures", []),
        "next_steps": receipt.get("next_steps", []),
        "source_selection": receipt.get("source_selection", {}),
        "artifacts": {
            "plan_path": artifacts.get("plan_path"),
            "runbook_path": artifacts.get("runbook_path"),
            "preflight_report_paths": artifacts.get("preflight_report_paths", []),
            "smoke_report_paths": artifacts.get("smoke_report_paths", []),
            "packet_path": artifacts.get("packet_path"),
            "intake_path": artifacts.get("intake_path"),
            "sync_receipt_paths": artifacts.get("sync_receipt_paths", []),
        },
        "read_only": True,
    }


def run_connected_calibration(
    roots: StorageRoots,
    *,
    run_id: str = "connected-calibration",
    mode: str = "fixture",
    platforms: list[str] | None = None,
    source_ids: list[str] | None = None,
    query: str | None = None,
    live_scope: str = "bounded",
    include_step_sources: bool = False,
    allow_network: bool = False,
    stepik_token_env: str = "STEPIK_API_TOKEN",
    browser_state_file: Path | None = None,
    expect_origin_contains: str | None = None,
    max_lessons: int = 50,
    max_pages: int = 5,
    max_sources: int = 50,
    source_limit: int | None = None,
) -> dict[str, object]:
    """Run a connected-source calibration workflow and write a receipt."""

    selected_mode = _selected_mode(mode)
    selected_platforms = _selected_platforms(platforms)
    selected_live_scope = _selected_live_scope(live_scope)
    create_storage_roots(roots)
    started_at = _now()
    if selected_mode == "fixture":
        receipt = _run_fixture(
            roots,
            run_id=run_id,
            platforms=selected_platforms,
            query=query,
            max_lessons=max_lessons,
            source_limit=source_limit,
            started_at=started_at,
        )
    else:
        receipt = _run_live(
            roots,
            run_id=run_id,
            platforms=selected_platforms,
            source_ids=source_ids,
            query=query,
            live_scope=selected_live_scope,
            include_step_sources=include_step_sources,
            allow_network=allow_network,
            stepik_token_env=stepik_token_env,
            browser_state_file=browser_state_file,
            expect_origin_contains=expect_origin_contains,
            max_lessons=max_lessons,
            max_pages=max_pages,
            max_sources=max_sources,
            source_limit=source_limit,
            started_at=started_at,
        )
    receipt_path = _write_receipt(roots, run_id, receipt)
    return {**receipt, "receipt_path": str(receipt_path)}


def _run_fixture(
    roots: StorageRoots,
    *,
    run_id: str,
    platforms: list[str],
    query: str | None,
    max_lessons: int,
    source_limit: int | None,
    started_at: str,
) -> dict[str, object]:
    run_dir = _connected_dir(roots, run_id)
    stages: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    smoke_reports: list[dict[str, object]] = []
    smoke_paths: list[str] = []
    sync_receipts: list[dict[str, object]] = []
    preflight_reports: list[dict[str, object]] = []
    preflight_paths: list[str] = []

    for platform in platforms:
        if platform in BROWSER_PLATFORMS:
            smoke = _capture_action(
                "smoke",
                platform,
                lambda platform=platform: smoke_browser_fixture(
                    roots,
                    platform=platform,
                    run_id=f"{run_id}-{platform}-fixture-smoke",
                    query=query,
                    register=True,
                    build_artifacts=True,
                ),
            )
            smoke_report = smoke["payload"] if isinstance(smoke.get("payload"), dict) else {}
            smoke_path = _write_json(run_dir / f"{platform}-fixture-smoke.json", smoke_report)
            smoke["artifact_path"] = str(smoke_path)
            smoke_reports.append(smoke_report)
            smoke_paths.append(str(smoke_path))
            stages.append({"name": f"{platform}_fixture_smoke", "status": smoke["status"], "actions": [smoke]})
            _collect_action_failure(failures, smoke)

            sync = _capture_action(
                "sync",
                platform,
                lambda platform=platform: sync_browser_fixture_sources(
                    roots,
                    sync_run_id=f"{run_id}-{platform}-fixture-sync",
                    platforms=[platform],
                    max_lessons=max_lessons,
                    source_limit=source_limit,
                    build_artifacts=True,
                ),
            )
            sync_receipts.append(sync["payload"] if isinstance(sync.get("payload"), dict) else {})
            stages.append({"name": f"{platform}_fixture_sync", "status": sync["status"], "actions": [sync]})
            _collect_action_failure(failures, sync)
        elif platform == "stepik":
            smoke = _capture_action(
                "smoke",
                platform,
                lambda: smoke_stepik_fixture(
                    roots,
                    course_id=STEPIK_FIXTURE_COURSE_ID,
                    run_id=f"{run_id}-stepik-fixture-smoke",
                    query=query,
                    build_artifacts=True,
                ),
            )
            smoke_report = smoke["payload"] if isinstance(smoke.get("payload"), dict) else {}
            smoke_path = _write_json(run_dir / "stepik-fixture-smoke.json", smoke_report)
            smoke["artifact_path"] = str(smoke_path)
            smoke_reports.append(smoke_report)
            smoke_paths.append(str(smoke_path))
            stages.append({"name": "stepik_fixture_smoke", "status": smoke["status"], "actions": [smoke]})
            _collect_action_failure(failures, smoke)

            sync = _capture_action(
                "sync",
                "stepik",
                lambda: sync_stepik_fixture_sources(
                    roots,
                    sync_run_id=f"{run_id}-stepik-fixture-sync",
                    source_limit=source_limit,
                    build_artifacts=True,
                ),
            )
            sync_receipts.append(sync["payload"] if isinstance(sync.get("payload"), dict) else {})
            stages.append({"name": "stepik_fixture_sync", "status": sync["status"], "actions": [sync]})
            _collect_action_failure(failures, sync)

    preflight = live_preflight(roots, platforms=platforms)
    preflight_path = _write_json(run_dir / "fixture-preflight.json", preflight)
    preflight_reports.append(preflight)
    preflight_paths.append(str(preflight_path))
    stages.append(
        {
            "name": "read_only_preflight",
            "status": "ok" if preflight.get("status") in {"ok", "warning"} else "error",
            "actions": [
                {
                    "kind": "preflight",
                    "ready": bool(preflight.get("ready")),
                    "network_touched": False,
                    "artifact_path": str(preflight_path),
                    "payload": _payload_summary(preflight),
                }
            ],
        }
    )

    plan = connected_source_plan(roots, platforms=platforms, query=query, max_lessons=max_lessons)
    plan_path = _write_json(run_dir / "connected-source-plan.json", plan)
    runbook_path = run_dir / "connected-source-runbook.md"
    runbook = write_connected_source_runbook(plan, runbook_path)
    stages.append(
        {
            "name": "read_only_connected_plan",
            "status": "ok" if plan.get("actionable") else "partial",
            "actions": [
                {
                    "kind": "connected_plan",
                    "ready": bool(plan.get("ready")),
                    "network_touched": False,
                    "artifact_path": str(plan_path),
                    "runbook_path": runbook.get("path"),
                    "payload": _payload_summary(plan),
                }
            ],
        }
    )

    packet, packet_path, intake, intake_path = _build_packet_and_intake(
        roots,
        run_id=run_id,
        smoke_reports=smoke_reports,
        preflight_reports=preflight_reports,
    )
    stages.append(_packet_stage(packet, packet_path, intake, intake_path))
    if packet.get("status") != "ok":
        failures.append({"stage": "calibration_packet", "reason": "packet status is not ok", "status": packet.get("status")})

    return _receipt(
        roots,
        run_id=run_id,
        mode="fixture",
        platforms=platforms,
        source_ids=[],
        live_scope="bounded",
        include_step_sources=False,
        allow_network=False,
        started_at=started_at,
        stages=stages,
        failures=failures,
        smoke_paths=smoke_paths,
        preflight_paths=preflight_paths,
        packet=packet,
        packet_path=packet_path,
        intake=intake,
        intake_path=intake_path,
        plan_path=plan_path,
        runbook_path=Path(str(runbook.get("path"))),
        sync_receipts=sync_receipts,
    )


def _run_live(
    roots: StorageRoots,
    *,
    run_id: str,
    platforms: list[str],
    source_ids: list[str] | None,
    query: str | None,
    live_scope: str,
    include_step_sources: bool,
    allow_network: bool,
    stepik_token_env: str,
    browser_state_file: Path | None,
    expect_origin_contains: str | None,
    max_lessons: int,
    max_pages: int,
    max_sources: int,
    source_limit: int | None,
    started_at: str,
) -> dict[str, object]:
    run_dir = _connected_dir(roots, run_id)
    failures: list[dict[str, object]] = []
    stages: list[dict[str, object]] = []
    smoke_reports: list[dict[str, object]] = []
    smoke_paths: list[str] = []
    sync_receipts: list[dict[str, object]] = []
    preflight_reports: list[dict[str, object]] = []
    preflight_paths: list[str] = []

    plan = connected_source_plan(
        roots,
        platforms=platforms,
        stepik_token_env=stepik_token_env,
        browser_state_file=browser_state_file,
        expect_origin_contains=expect_origin_contains,
        query=query,
        max_lessons=max_lessons,
        max_pages=max_pages,
        max_sources=max_sources,
        calibration_run=run_id,
        live_scope=live_scope,
        include_step_sources=include_step_sources,
    )
    plan_path = _write_json(run_dir / "connected-source-plan.json", plan)
    runbook_path = run_dir / "connected-source-runbook.md"
    runbook = write_connected_source_runbook(plan, runbook_path)
    preflight = plan.get("preflight") if isinstance(plan.get("preflight"), dict) else live_preflight(roots, platforms=platforms)
    preflight_path = _write_json(run_dir / "live-preflight.json", preflight)
    preflight_reports.append(preflight)
    preflight_paths.append(str(preflight_path))
    stages.append(
        {
            "name": "read_only_connected_plan",
            "status": "ok" if plan.get("actionable") else "partial",
            "actions": [
                {
                    "kind": "connected_plan",
                    "ready": bool(plan.get("ready")),
                    "network_touched": False,
                    "artifact_path": str(plan_path),
                    "runbook_path": runbook.get("path"),
                    "payload": _payload_summary(plan),
                },
                {
                    "kind": "preflight",
                    "ready": bool(preflight.get("ready")),
                    "network_touched": False,
                    "artifact_path": str(preflight_path),
                    "payload": _payload_summary(preflight),
                },
            ],
        }
    )

    selected_sources = _selected_source_checks(plan, source_ids=source_ids, source_limit=source_limit)
    ready_sources = _ready_source_checks(selected_sources)
    blocked_sources = _blocked_source_checks(selected_sources)
    source_selection = _source_selection(
        requested_source_ids=source_ids or [],
        selected_sources=selected_sources,
        ready_sources=ready_sources,
        blocked_sources=blocked_sources,
        source_limit=source_limit,
    )

    if not allow_network:
        failures.append({"stage": "live_execution", "reason": "live mode requires --allow-network"})
        return _receipt(
            roots,
            run_id=run_id,
            mode="live",
            platforms=platforms,
            source_ids=source_ids or [],
            live_scope=live_scope,
            include_step_sources=include_step_sources,
            allow_network=False,
            started_at=started_at,
            stages=stages,
            failures=failures,
            smoke_paths=[],
            preflight_paths=preflight_paths,
            packet=None,
            packet_path=None,
            intake=None,
            intake_path=None,
            plan_path=plan_path,
            runbook_path=Path(str(runbook.get("path"))),
            sync_receipts=[],
            source_selection=source_selection,
        )

    for source in blocked_sources:
        failures.append(
            {
                "stage": "source_readiness",
                "platform": source.get("platform"),
                "source_id": source.get("source_id"),
                "source_ref": source.get("source_ref"),
                "reason": "source is not ready",
                "blockers": source.get("blockers", []),
            }
        )
    if not ready_sources:
        failures.append({"stage": "live_execution", "reason": "no ready sources matched this connected run"})

    sync_actions: list[dict[str, object]] = []
    for platform in [item for item in platforms if item in BROWSER_PLATFORMS]:
        ids = [str(source.get("source_id")) for source in ready_sources if source.get("platform") == platform]
        if not ids:
            continue
        state_file = _resolved_browser_state_file(roots, platform=platform, browser_state_file=browser_state_file)
        action = _capture_action(
            "sync",
            platform,
            lambda platform=platform, ids=ids: sync_browser_live_sources(
                roots,
                sync_run_id=f"{run_id}-{platform}-live-sync",
                platforms=[platform],
                source_ids=ids,
                state_file=state_file,
                max_lessons=max_lessons,
                source_limit=source_limit,
                build_artifacts=True,
            ),
            network_touched=True,
        )
        action["source_ids"] = ids
        action["state_file"] = str(state_file)
        sync_receipts.append(action["payload"] if isinstance(action.get("payload"), dict) else {})
        sync_actions.append(action)
        _collect_action_failure(failures, action)
    if any(source.get("platform") == "stepik" for source in ready_sources):
        stepik_ids = [str(source.get("source_id")) for source in ready_sources if source.get("platform") == "stepik"]
        max_sections = None if live_scope == "full-course" else 1
        max_units = None if live_scope == "full-course" else 2
        max_steps = None if live_scope == "full-course" else 5
        action = _capture_action(
            "sync",
            "stepik",
            lambda: sync_stepik_live_sources(
                roots,
                sync_run_id=f"{run_id}-stepik-live-sync",
                token_env=stepik_token_env,
                max_sections=max_sections,
                max_units_per_section=max_units,
                max_steps_per_lesson=max_steps,
                include_step_sources=include_step_sources,
                source_ids=stepik_ids,
                source_limit=source_limit,
                build_artifacts=True,
            ),
            network_touched=True,
        )
        action["source_ids"] = stepik_ids
        sync_receipts.append(action["payload"] if isinstance(action.get("payload"), dict) else {})
        sync_actions.append(action)
        _collect_action_failure(failures, action)
    stages.append({"name": "live_sync", "status": _stage_status(sync_actions), "actions": sync_actions})

    smoke_actions: list[dict[str, object]] = []
    for source in ready_sources:
        platform = str(source.get("platform") or "")
        slug = _slug(source.get("source_id") or source.get("source_ref"))
        if platform in BROWSER_PLATFORMS:
            state_file = _resolved_browser_state_file(roots, platform=platform, browser_state_file=browser_state_file)
            action = _capture_action(
                "smoke",
                platform,
                lambda source=source, platform=platform, slug=slug: smoke_browser_live(
                    roots,
                    platform=platform,
                    run_id=f"{run_id}-{platform}-live-smoke-{slug}",
                    course_url=str(source.get("source_ref") or ""),
                    state_file=state_file,
                    max_sources=max_sources,
                    max_pages=max_pages,
                    max_lessons=max_lessons,
                    query=query,
                    build_artifacts=True,
                ),
                network_touched=True,
            )
            action["state_file"] = str(state_file)
        elif platform == "stepik":
            try:
                course_id = parse_stepik_course_id(str(source.get("source_ref") or ""))
            except ValueError as exc:
                action = _error_action("smoke", platform, str(exc), network_touched=False, source=source)
            else:
                max_sections = None if live_scope == "full-course" else 1
                max_units = None if live_scope == "full-course" else 2
                max_steps = None if live_scope == "full-course" else 5
                action = _capture_action(
                    "smoke",
                    "stepik",
                    lambda source=source, course_id=course_id, slug=slug: smoke_stepik_live(
                        roots,
                        course_id=course_id,
                        run_id=f"{run_id}-stepik-live-smoke-{slug}",
                        access_mode=str(source.get("access_mode") or "public_api"),
                        token_env=stepik_token_env,
                        max_sections=max_sections,
                        max_units_per_section=max_units,
                        max_steps_per_lesson=max_steps,
                        include_step_sources=include_step_sources,
                        query=query,
                        build_artifacts=True,
                    ),
                    network_touched=True,
                )
        else:
            continue
        action["source_id"] = source.get("source_id")
        action["source_ref"] = source.get("source_ref")
        payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
        if payload:
            smoke_path = _write_json(run_dir / f"{platform}-live-smoke-{slug}.json", payload)
            action["artifact_path"] = str(smoke_path)
            smoke_reports.append(payload)
            smoke_paths.append(str(smoke_path))
        smoke_actions.append(action)
        _collect_action_failure(failures, action)
    stages.append({"name": "live_smoke", "status": _stage_status(smoke_actions), "actions": smoke_actions})

    packet = intake = None
    packet_path = intake_path = None
    if smoke_reports:
        packet, packet_path, intake, intake_path = _build_packet_and_intake(
            roots,
            run_id=run_id,
            smoke_reports=smoke_reports,
            preflight_reports=preflight_reports,
        )
        stages.append(_packet_stage(packet, packet_path, intake, intake_path))
        if packet.get("status") != "ok":
            failures.append({"stage": "calibration_packet", "reason": "packet status is not ok", "status": packet.get("status")})

    return _receipt(
        roots,
        run_id=run_id,
        mode="live",
        platforms=platforms,
        source_ids=source_ids or [],
        live_scope=live_scope,
        include_step_sources=include_step_sources,
        allow_network=True,
        started_at=started_at,
        stages=stages,
        failures=failures,
        smoke_paths=smoke_paths,
        preflight_paths=preflight_paths,
        packet=packet,
        packet_path=packet_path,
        intake=intake,
        intake_path=intake_path,
        plan_path=plan_path,
        runbook_path=Path(str(runbook.get("path"))),
        sync_receipts=sync_receipts,
        source_selection=source_selection,
    )


def _build_packet_and_intake(
    roots: StorageRoots,
    *,
    run_id: str,
    smoke_reports: list[dict[str, object]],
    preflight_reports: list[dict[str, object]],
) -> tuple[dict[str, object], Path, dict[str, object], Path]:
    packet = build_live_calibration_packet(run_id=run_id, smoke_reports=smoke_reports, preflight_reports=preflight_reports)
    packet_path = write_live_calibration_packet(roots, packet, run_id=run_id)
    saved_packet = load_json_report(packet_path)
    intake = build_live_calibration_intake(packet=saved_packet, run_id=f"{run_id}-intake")
    intake_path = write_live_calibration_intake(roots, intake, run_id=f"{run_id}-intake")
    return saved_packet, packet_path, intake, intake_path


def _packet_stage(packet: dict[str, object], packet_path: Path, intake: dict[str, object], intake_path: Path) -> dict[str, object]:
    return {
        "name": "calibration_packet_and_intake",
        "status": "ok" if packet.get("status") == "ok" and intake.get("status") in {"ok", "actionable"} else "partial",
        "actions": [
            {
                "kind": "calibration_packet",
                "status": packet.get("status"),
                "network_touched": bool(packet.get("network_touched")),
                "artifact_path": str(packet_path),
                "payload": _payload_summary(packet),
            },
            {
                "kind": "calibration_intake",
                "status": intake.get("status"),
                "network_touched": False,
                "artifact_path": str(intake_path),
                "payload": _payload_summary(intake),
            },
        ],
    }


def _receipt(
    roots: StorageRoots,
    *,
    run_id: str,
    mode: str,
    platforms: list[str],
    source_ids: list[str],
    live_scope: str,
    include_step_sources: bool,
    allow_network: bool,
    started_at: str,
    stages: list[dict[str, object]],
    failures: list[dict[str, object]],
    smoke_paths: list[str],
    preflight_paths: list[str],
    packet: dict[str, object] | None,
    packet_path: Path | None,
    intake: dict[str, object] | None,
    intake_path: Path | None,
    plan_path: Path | None,
    runbook_path: Path | None,
    sync_receipts: list[dict[str, object]],
    source_selection: dict[str, object] | None = None,
) -> dict[str, object]:
    status = _receipt_status(failures, packet=packet, stages=stages)
    registry = load_registry(roots.data)
    return {
        "schema": "aoa_course_connected_calibration_run_receipt_v1",
        "status": status,
        "run_id": run_id,
        "mode": mode,
        "platforms": platforms,
        "source_ids": source_ids,
        "live_scope": live_scope,
        "include_step_sources": include_step_sources,
        "allow_network": allow_network,
        "network_touched": any(_stage_touched_network(stage) for stage in stages),
        "started_at": started_at,
        "completed_at": _now(),
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
        },
        "source_selection": source_selection or {
            "requested_source_ids": source_ids,
            "selected_source_ids": [],
            "ready_source_ids": [],
            "blocked_source_ids": [],
            "selected_source_count": 0,
            "ready_source_count": 0,
            "blocked_source_count": 0,
            "source_limit": None,
            "sources": [],
        },
        "stage_count": len(stages),
        "stages": [_stage_without_full_payload(stage) for stage in stages],
        "artifacts": {
            "plan_path": str(plan_path) if plan_path else None,
            "runbook_path": str(runbook_path) if runbook_path else None,
            "preflight_report_paths": preflight_paths,
            "smoke_report_paths": smoke_paths,
            "packet_path": str(packet_path) if packet_path else None,
            "intake_path": str(intake_path) if intake_path else None,
            "sync_receipt_paths": [
                str(receipt.get("receipt_path"))
                for receipt in sync_receipts
                if isinstance(receipt, dict) and receipt.get("receipt_path")
            ],
        },
        "quality": packet.get("quality") if isinstance(packet, dict) else {},
        "privacy": packet.get("privacy") if isinstance(packet, dict) else {"contains_raw_payloads": False, "contains_secret_values": False},
        "failures": failures,
        "next_steps": _next_steps(status, mode, allow_network, failures, intake),
    }


def _capture_action(
    kind: str,
    platform: str,
    func: Any,
    *,
    network_touched: bool | None = None,
) -> dict[str, object]:
    try:
        payload = func()
    except Exception as exc:  # pragma: no cover - defensive receipt accounting
        return _error_action(kind, platform, str(exc), network_touched=bool(network_touched))
    status = str(payload.get("status") or "ok") if isinstance(payload, dict) else "ok"
    return {
        "kind": kind,
        "platform": platform,
        "status": status,
        "ready": status in {"ok", "warning"},
        "network_touched": bool(payload.get("network_touched")) if isinstance(payload, dict) else bool(network_touched),
        "payload": payload,
    }


def _error_action(
    kind: str,
    platform: str,
    error: str,
    *,
    network_touched: bool,
    source: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "kind": kind,
        "platform": platform,
        "status": "error",
        "ready": False,
        "network_touched": network_touched,
        "source_id": source.get("source_id") if source else None,
        "source_ref": source.get("source_ref") if source else None,
        "error": error,
        "payload": {
            "schema": "aoa_course_connected_action_error_v1",
            "status": "error",
            "platform": platform,
            "kind": kind,
            "error": error,
            "network_touched": network_touched,
        },
    }


def _collect_action_failure(failures: list[dict[str, object]], action: dict[str, object]) -> None:
    if action.get("status") in {"ok", "warning"}:
        return
    failures.append(
        {
            "stage": action.get("kind"),
            "platform": action.get("platform"),
            "reason": "action status is not ok",
            "status": action.get("status"),
            "error": action.get("error"),
        }
    )


def _selected_source_checks(plan: dict[str, object], *, source_ids: list[str] | None, source_limit: int | None) -> list[dict[str, object]]:
    wanted = {str(source_id) for source_id in source_ids or []}
    sources = [
        source
        for source in plan.get("source_plans", [])
        if isinstance(source, dict)
        and (not wanted or str(source.get("source_id") or "") in wanted)
    ]
    return sources[:source_limit] if source_limit is not None else sources


def _ready_source_checks(sources: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        source
        for source in sources
        if bool(source.get("ready"))
    ]


def _blocked_source_checks(sources: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        source
        for source in sources
        if not bool(source.get("ready"))
    ]


def _source_selection(
    *,
    requested_source_ids: list[str],
    selected_sources: list[dict[str, object]],
    ready_sources: list[dict[str, object]],
    blocked_sources: list[dict[str, object]],
    source_limit: int | None,
) -> dict[str, object]:
    return {
        "requested_source_ids": [str(source_id) for source_id in requested_source_ids],
        "selected_source_ids": _source_ids(selected_sources),
        "ready_source_ids": _source_ids(ready_sources),
        "blocked_source_ids": _source_ids(blocked_sources),
        "selected_source_count": len(selected_sources),
        "ready_source_count": len(ready_sources),
        "blocked_source_count": len(blocked_sources),
        "source_limit": source_limit,
        "sources": [_source_summary(source) for source in selected_sources],
    }


def _source_ids(sources: list[dict[str, object]]) -> list[str]:
    return [str(source.get("source_id") or "") for source in sources if source.get("source_id")]


def _source_summary(source: dict[str, object]) -> dict[str, object]:
    return {
        "platform": source.get("platform"),
        "source_id": source.get("source_id"),
        "source_ref": source.get("source_ref"),
        "title": source.get("title"),
        "access_mode": source.get("access_mode"),
        "enabled": bool(source.get("enabled", True)),
        "ready": bool(source.get("ready")),
        "blockers": source.get("blockers", []),
    }


def _resolved_browser_state_file(roots: StorageRoots, *, platform: str, browser_state_file: Path | None) -> Path:
    return (browser_state_file or roots.auth / platform / "account.storage-state.json").expanduser().resolve()


def _payload_summary(payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema": payload.get("schema"),
        "status": payload.get("status"),
        "ready": payload.get("ready"),
        "run_id": payload.get("run_id"),
        "network_touched": payload.get("network_touched"),
        "platforms": payload.get("platforms"),
        "report_count": payload.get("report_count"),
        "action_count": payload.get("action_count"),
    }


def _stage_without_full_payload(stage: dict[str, object]) -> dict[str, object]:
    actions = []
    for action in stage.get("actions", []):
        if not isinstance(action, dict):
            continue
        compact = {key: value for key, value in action.items() if key != "payload"}
        if isinstance(action.get("payload"), dict):
            compact["payload"] = _payload_summary(action["payload"])
        actions.append(compact)
    return {**stage, "actions": actions}


def _receipt_status(failures: list[dict[str, object]], *, packet: dict[str, object] | None, stages: list[dict[str, object]]) -> str:
    if any(stage.get("status") == "error" for stage in stages):
        return "error"
    if failures:
        return "partial"
    if packet is not None and packet.get("status") != "ok":
        return "partial"
    return "ok"


def _stage_status(actions: list[dict[str, object]]) -> str:
    if not actions:
        return "skipped"
    if all(action.get("status") == "ok" for action in actions):
        return "ok"
    if any(action.get("status") == "ok" for action in actions):
        return "partial"
    return "error"


def _stage_touched_network(stage: dict[str, object]) -> bool:
    return any(bool(action.get("network_touched")) for action in stage.get("actions", []) if isinstance(action, dict))


def _next_steps(
    status: str,
    mode: str,
    allow_network: bool,
    failures: list[dict[str, object]],
    intake: dict[str, object] | None,
) -> list[str]:
    if mode == "live" and not allow_network:
        return ["rerun with --allow-network after reviewing the connected-source plan and auth/source readiness"]
    if intake and isinstance(intake.get("next_steps"), list) and intake.get("next_steps"):
        return [str(item) for item in intake["next_steps"]]
    if status == "ok" and mode == "fixture":
        return ["connect operator-owned credentials, run preflight connected-plan, then rerun calibration connected-run --mode live --allow-network"]
    if status == "ok":
        return ["use the calibration packet as field evidence for selector, sync, retrieval, and eval follow-up"]
    return [str(failure.get("reason") or "inspect connected run failure") for failure in failures]


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_receipt(roots: StorageRoots, run_id: str, receipt: dict[str, object]) -> Path:
    path = connected_calibration_receipt_path(roots, run_id)
    _write_json(path, {**receipt, "receipt_path": str(path)})
    return path


def _connected_dir(roots: StorageRoots, run_id: str) -> Path:
    return run_artifact_dir(roots, run_id) / "connected"


def _selected_mode(mode: str) -> str:
    selected = str(mode or "fixture")
    if selected not in RUN_MODES:
        raise ValueError(f"unsupported connected run mode: {selected}")
    return selected


def _selected_platforms(platforms: list[str] | None) -> list[str]:
    selected = list(dict.fromkeys(platforms or ["getcourse", "skillspace", "stepik"]))
    unsupported = [platform for platform in selected if platform not in CONNECTED_PLATFORMS]
    if unsupported:
        raise ValueError(f"unsupported connected run platform: {', '.join(unsupported)}")
    return selected


def _selected_live_scope(live_scope: str) -> str:
    selected = str(live_scope or "bounded")
    if selected not in LIVE_SCOPES:
        raise ValueError(f"unsupported live scope: {selected}")
    return selected


def _slug(value: object) -> str:
    text = str(value or "").casefold()
    slug = "".join(ch if ch.isalnum() else "-" for ch in text).strip("-")
    return slug or "source"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
