"""Executable connected-source calibration runs.

The connected run receipt is the bridge between the read-only launch plan and
field calibration evidence. Fixture mode proves the full contract without
network access; live mode is gated behind explicit operator approval.
"""

from __future__ import annotations

import json
import shlex
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
from aoa_course_connector.query import render_answer_packet, render_lesson_context_packet
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
    quality = receipt.get("quality") if isinstance(receipt.get("quality"), dict) else {}
    repair_lanes = receipt.get("repair_lanes") if isinstance(receipt.get("repair_lanes"), list) else []
    snapshot_audit = receipt.get("snapshot_audit")
    if not isinstance(snapshot_audit, dict):
        snapshot_audit = _snapshot_audit_status_from_quality(
            quality,
            packet_available=bool(artifacts.get("packet_path") or quality),
            intake=None,
            repair_lanes=[lane for lane in repair_lanes if isinstance(lane, dict)],
        )
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
        "quality": quality,
        "snapshot_audit": snapshot_audit,
        "privacy": receipt.get("privacy") if isinstance(receipt.get("privacy"), dict) else {},
        "failures": receipt.get("failures", []),
        "repair_lane_count": receipt.get("repair_lane_count", 0),
        "repair_lanes": repair_lanes,
        "next_steps": receipt.get("next_steps", []),
        "source_selection": receipt.get("source_selection", {}),
        "execution_options": receipt.get("execution_options") if isinstance(receipt.get("execution_options"), dict) else {},
        "query_plan": receipt.get("query_plan", {}),
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


def query_connected_calibration(
    roots: StorageRoots,
    *,
    run_id: str,
    query: str | None = None,
    platforms: list[str] | None = None,
    source_ids: list[str] | None = None,
    kinds: list[str] | None = None,
    limit: int = 5,
    mode: str | None = None,
    graph_limit: int = 12,
    entry_limit: int = 5,
) -> dict[str, object]:
    """Run answer/context/evidence checks against query-ready connected runs."""

    status = load_connected_calibration_status(roots, run_id=run_id)
    query_plan = status.get("query_plan") if isinstance(status.get("query_plan"), dict) else {}
    entries = query_plan.get("entries") if isinstance(query_plan.get("entries"), list) else []
    selected_entries, blocked_entries = _select_query_entries(
        entries,
        query=query,
        platforms=platforms,
        source_ids=source_ids,
        kinds=kinds,
        entry_limit=max(1, int(entry_limit or 1)),
    )
    responses: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for entry in selected_entries:
        if not isinstance(entry, dict):
            continue
        entry_query = str(query or entry.get("query") or "")
        if not entry_query or entry_query == "<course-specific question>":
            blocked_entries.append(_blocked_query_entry(entry, "missing_query", "pass --query or run calibration with a smoke query"))
            continue
        entry_run_id = str(entry.get("run_id") or "")
        if not entry_run_id:
            blocked_entries.append(_blocked_query_entry(entry, "missing_run_id", "query-plan entry has no run_id"))
            continue
        entry_mode = str(mode or entry.get("query_mode") or "keyword")
        try:
            answer_packet = render_answer_packet(roots, entry_query, entry_run_id, int(limit or 5), entry_mode)
            lesson_context = render_lesson_context_packet(roots, entry_query, entry_run_id, int(limit or 5), entry_mode, int(graph_limit or 12))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            failures.append(
                {
                    "kind": entry.get("kind"),
                    "platform": entry.get("platform"),
                    "run_id": entry_run_id,
                    "source_id": entry.get("source_id"),
                    "reason": exc.__class__.__name__,
                    "error": str(exc),
                    "next_commands": _entry_rebuild_commands(entry_run_id),
                }
            )
            continue
        graph_context = lesson_context.get("graph_context") if isinstance(lesson_context.get("graph_context"), dict) else {}
        quality = answer_packet.get("quality") if isinstance(answer_packet.get("quality"), dict) else {}
        responses.append(
            {
                "kind": entry.get("kind"),
                "platform": entry.get("platform"),
                "run_id": entry_run_id,
                "source_id": entry.get("source_id"),
                "source_ref": entry.get("source_ref"),
                "title": entry.get("title"),
                "query": entry_query,
                "mode": entry_mode,
                "query_ready": True,
                "answer_ready": bool(quality.get("ready")),
                "result_count": answer_packet.get("result_count", 0),
                "evidence_count": len(answer_packet.get("evidence_chain", [])) if isinstance(answer_packet.get("evidence_chain"), list) else 0,
                "graph_status": graph_context.get("status"),
                "graph_context_count": graph_context.get("context_count", 0),
                "quality": quality,
                "answer_packet": answer_packet,
                "lesson_context": lesson_context,
                "evidence_report": _evidence_report_from_answer(answer_packet),
                "commands": entry.get("commands", {}),
                "mcp_commands": entry.get("mcp_commands", {}),
            }
        )
    quality = _connected_query_quality(responses, blocked_entries, failures)
    packet_status = _connected_query_status(status, responses, blocked_entries, failures)
    return {
        "schema": "aoa_course_connected_run_query_packet_v1",
        "status": packet_status,
        "connected_run_id": run_id,
        "connected_run_status": status.get("status"),
        "receipt_path": status.get("receipt_path"),
        "query": query or "",
        "limit": int(limit or 5),
        "mode": mode or "",
        "graph_limit": int(graph_limit or 12),
        "entry_limit": int(entry_limit or 5),
        "entry_count": len(entries),
        "selected_entry_count": len(selected_entries),
        "response_count": len(responses),
        "blocked_entry_count": len(blocked_entries),
        "failure_count": len(failures),
        "responses": responses,
        "blocked_entries": blocked_entries,
        "failures": failures,
        "quality": quality,
        "next_commands": _connected_query_next_commands(status, blocked_entries, failures),
        "network_touched": False,
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
    link_pattern: str | None = None,
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
            link_pattern=link_pattern,
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
        execution_options=_execution_options(
            query=query,
            max_lessons=max_lessons,
            max_pages=None,
            max_sources=None,
            link_pattern=None,
            source_limit=source_limit,
            stepik_token_env=None,
            browser_state_file=None,
        ),
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
    link_pattern: str | None,
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
        source_ids=source_ids,
        stepik_token_env=stepik_token_env,
        browser_state_file=browser_state_file,
        expect_origin_contains=expect_origin_contains,
        query=query,
        max_lessons=max_lessons,
        max_pages=max_pages,
        max_sources=max_sources,
        link_pattern=link_pattern,
        calibration_run=run_id,
        live_scope=live_scope,
        include_step_sources=include_step_sources,
    )
    plan_path = _write_json(run_dir / "connected-source-plan.json", plan)
    runbook_path = run_dir / "connected-source-runbook.md"
    runbook = write_connected_source_runbook(plan, runbook_path)
    preflight = plan.get("preflight") if isinstance(plan.get("preflight"), dict) else live_preflight(roots, platforms=platforms, source_ids=source_ids)
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
            execution_options=_execution_options(
                query=query,
                max_lessons=max_lessons,
                max_pages=max_pages,
                max_sources=max_sources,
                link_pattern=link_pattern,
                source_limit=source_limit,
                stepik_token_env=stepik_token_env,
                browser_state_file=browser_state_file,
            ),
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
                link_pattern=link_pattern,
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
                    link_pattern=link_pattern,
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
        execution_options=_execution_options(
            query=query,
            max_lessons=max_lessons,
            max_pages=max_pages,
            max_sources=max_sources,
            link_pattern=link_pattern,
            source_limit=source_limit,
            stepik_token_env=stepik_token_env,
            browser_state_file=browser_state_file,
        ),
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


def _execution_options(
    *,
    query: str | None,
    max_lessons: int | None,
    max_pages: int | None,
    max_sources: int | None,
    link_pattern: str | None,
    source_limit: int | None,
    stepik_token_env: str | None,
    browser_state_file: Path | None,
) -> dict[str, object]:
    return {
        "query": query or "",
        "max_lessons": max_lessons,
        "max_pages": max_pages,
        "max_sources": max_sources,
        "link_pattern": link_pattern or "",
        "source_limit": source_limit,
        "stepik_token_env": stepik_token_env or "",
        "browser_state_file": str(browser_state_file.expanduser()) if browser_state_file else "",
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
    execution_options: dict[str, object] | None = None,
) -> dict[str, object]:
    status = _receipt_status(failures, packet=packet, stages=stages)
    query_plan = _query_plan(stages)
    registry = load_registry(roots.data)
    repair_lanes = _repair_lanes(
        failures,
        intake=intake,
        run_id=run_id,
        mode=mode,
        allow_network=allow_network,
        platforms=platforms,
        live_scope=live_scope,
        source_selection=source_selection,
        execution_options=execution_options,
        packet_path=packet_path,
    )
    snapshot_audit = _snapshot_audit_status(packet, intake=intake, repair_lanes=repair_lanes)
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
        "execution_options": execution_options or {},
        "repair_lane_count": len(repair_lanes),
        "repair_lanes": repair_lanes,
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
        "query_plan": query_plan,
        "quality": packet.get("quality") if isinstance(packet, dict) else {},
        "snapshot_audit": snapshot_audit,
        "privacy": packet.get("privacy") if isinstance(packet, dict) else {"contains_raw_payloads": False, "contains_secret_values": False},
        "failures": failures,
        "next_steps": _next_steps(status, mode, allow_network, failures, intake, repair_lanes),
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


def _query_plan(stages: list[dict[str, object]]) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for stage in stages:
        for action in stage.get("actions", []):
            if not isinstance(action, dict) or not isinstance(action.get("payload"), dict):
                continue
            payload = action["payload"]
            kind = str(action.get("kind") or "")
            if kind == "sync":
                for entry in _sync_query_plan_entries(payload, action):
                    key = (str(entry.get("kind")), str(entry.get("platform")), str(entry.get("run_id")))
                    if key not in seen:
                        entries.append(entry)
                        seen.add(key)
            elif kind == "smoke":
                entry = _smoke_query_plan_entry(payload, action)
                if entry:
                    key = (str(entry.get("kind")), str(entry.get("platform")), str(entry.get("run_id")))
                    if key not in seen:
                        entries.append(entry)
                        seen.add(key)
    return {
        "schema": "aoa_course_connected_query_plan_v1",
        "ready": any(bool(entry.get("query_ready")) for entry in entries),
        "entry_count": len(entries),
        "entries": entries,
    }


def _select_query_entries(
    entries: list[object],
    *,
    query: str | None,
    platforms: list[str] | None,
    source_ids: list[str] | None,
    kinds: list[str] | None,
    entry_limit: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    platform_set = {str(platform) for platform in platforms or []}
    source_set = {str(source_id) for source_id in source_ids or []}
    kind_set = {str(kind) for kind in kinds or []}
    selected: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    missing_query_entries: list[dict[str, object]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if platform_set and str(entry.get("platform") or "") not in platform_set:
            continue
        if source_set and str(entry.get("source_id") or "") not in source_set:
            continue
        if kind_set and str(entry.get("kind") or "") not in kind_set:
            continue
        if not bool(entry.get("query_ready")):
            blocked.append(_blocked_query_entry(entry, "query_not_ready", "query-plan entry is not query ready"))
            continue
        if not query and not str(entry.get("query") or ""):
            missing_query_entries.append(entry)
            continue
        if len(selected) < entry_limit:
            selected.append(entry)
    if not selected and missing_query_entries:
        for entry in missing_query_entries[:entry_limit]:
            blocked.append(_blocked_query_entry(entry, "missing_query", "pass --query or run calibration with a smoke query"))
    return selected, blocked


def _blocked_query_entry(entry: dict[str, object], reason: str, detail: str) -> dict[str, object]:
    run_id = str(entry.get("run_id") or "")
    payload = {
        "kind": entry.get("kind"),
        "platform": entry.get("platform"),
        "run_id": run_id,
        "source_id": entry.get("source_id"),
        "source_ref": entry.get("source_ref"),
        "reason": reason,
        "detail": detail,
        "query_ready": bool(entry.get("query_ready")),
    }
    if run_id:
        payload["next_commands"] = _entry_rebuild_commands(run_id)
    return payload


def _entry_rebuild_commands(run_id: str) -> list[str]:
    return [
        f"aoa-course build-index --run {shlex.quote(run_id)}",
        f"aoa-course build-semantic-index --run {shlex.quote(run_id)}",
        f"aoa-course build-graph --run {shlex.quote(run_id)}",
    ]


def _evidence_report_from_answer(answer_packet: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "aoa_course_connected_run_evidence_report_v1",
        "run_id": answer_packet.get("run_id"),
        "query": answer_packet.get("query"),
        "mode": answer_packet.get("mode"),
        "result_count": answer_packet.get("result_count"),
        "evidence_chain": answer_packet.get("evidence_chain", []),
        "quality": answer_packet.get("quality", {}),
        "freshness_report": answer_packet.get("freshness_report", {}),
        "authority_report": answer_packet.get("authority_report", {}),
        "refresh_report": answer_packet.get("refresh_report", {}),
        "result_refs": _compact_result_refs(answer_packet),
    }


def _compact_result_refs(answer_packet: dict[str, object]) -> list[dict[str, object]]:
    results = answer_packet.get("results") if isinstance(answer_packet.get("results"), list) else []
    refs: list[dict[str, object]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        refs.append(
            {
                key: value
                for key, value in {
                    "doc_id": result.get("doc_id"),
                    "kind": result.get("kind"),
                    "source_id": result.get("source_id"),
                    "source_url": result.get("source_url"),
                    "evidence_id": result.get("evidence_id"),
                    "snippet": result.get("snippet"),
                    "platform": result.get("platform"),
                    "path": result.get("path"),
                    "lesson_id": result.get("lesson_id"),
                    "lesson_title": result.get("lesson_title"),
                    "fetched_at": result.get("fetched_at"),
                    "freshness_state": result.get("freshness_state"),
                    "authority_tier": result.get("authority_tier"),
                    "authority_label": result.get("authority_label"),
                    "source_authority": result.get("source_authority"),
                    "score": result.get("score"),
                    "rank_score": result.get("rank_score"),
                    "rank_features": result.get("rank_features"),
                    "refresh_hint": result.get("refresh_hint"),
                }.items()
                if value is not None
            }
        )
    return refs


def _connected_query_quality(
    responses: list[dict[str, object]],
    blocked_entries: list[dict[str, object]],
    failures: list[dict[str, object]],
) -> dict[str, object]:
    answer_ready_count = sum(1 for response in responses if bool(response.get("answer_ready")))
    graph_ready_count = sum(1 for response in responses if response.get("graph_status") == "ready")
    evidence_count_total = sum(int(response.get("evidence_count") or 0) for response in responses)
    result_count_total = sum(int(response.get("result_count") or 0) for response in responses)
    return {
        "ready": bool(responses) and answer_ready_count == len(responses) and not blocked_entries and not failures,
        "response_count": len(responses),
        "answer_ready_count": answer_ready_count,
        "graph_ready_count": graph_ready_count,
        "result_count_total": result_count_total,
        "evidence_count_total": evidence_count_total,
        "blocked_entry_count": len(blocked_entries),
        "failure_count": len(failures),
        "platforms": sorted({str(response.get("platform") or "") for response in responses if response.get("platform")}),
        "run_ids": sorted({str(response.get("run_id") or "") for response in responses if response.get("run_id")}),
        "source_ids": sorted({str(response.get("source_id") or "") for response in responses if response.get("source_id")}),
        "all_responses_have_evidence": bool(responses) and all(int(response.get("evidence_count") or 0) > 0 for response in responses),
        "all_responses_have_graph_context": bool(responses) and graph_ready_count == len(responses),
    }


def _connected_query_status(
    status: dict[str, object],
    responses: list[dict[str, object]],
    blocked_entries: list[dict[str, object]],
    failures: list[dict[str, object]],
) -> str:
    if status.get("status") in {"missing", "error"}:
        return str(status.get("status"))
    if responses and all(bool(response.get("answer_ready")) for response in responses) and not blocked_entries and not failures:
        return "ok"
    if responses:
        return "partial"
    if blocked_entries or failures:
        return "blocked"
    return "empty"


def _connected_query_next_commands(
    status: dict[str, object],
    blocked_entries: list[dict[str, object]],
    failures: list[dict[str, object]],
) -> list[str]:
    commands: list[str] = []
    for item in status.get("next_steps", []):
        if isinstance(item, str) and item.startswith("aoa-course "):
            commands.append(item)
    for entry in blocked_entries:
        for command in entry.get("next_commands", []):
            if isinstance(command, str):
                commands.append(command)
    for failure in failures:
        for command in failure.get("next_commands", []):
            if isinstance(command, str):
                commands.append(command)
    return _dedupe(commands)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _sync_query_plan_entries(payload: dict[str, object], action: dict[str, object]) -> list[dict[str, object]]:
    checkpoints = payload.get("synced_sources") if isinstance(payload.get("synced_sources"), list) else []
    entries: list[dict[str, object]] = []
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, dict):
            continue
        run_id = str(checkpoint.get("run_id") or "")
        if not run_id:
            continue
        paths = {
            "normalized_path": str(checkpoint.get("normalized_path") or ""),
            "index_path": str(checkpoint.get("index_path") or ""),
            "semantic_index_path": str(checkpoint.get("semantic_index_path") or ""),
            "graph_path": str(checkpoint.get("graph_path") or ""),
            "answer_path": "",
        }
        entries.append(
            _query_plan_entry(
                kind="sync",
                platform=str(checkpoint.get("platform") or action.get("platform") or ""),
                run_id=run_id,
                status=str(checkpoint.get("status") or payload.get("status") or ""),
                source_id=str(checkpoint.get("source_id") or ""),
                source_ref=str(checkpoint.get("source_ref") or ""),
                title=str(checkpoint.get("title") or ""),
                query=None,
                result_count=0,
                evidence_count=0,
                paths=paths,
                stable_identity=checkpoint.get("stable_identity") if isinstance(checkpoint.get("stable_identity"), dict) else None,
            )
        )
    return entries


def _smoke_query_plan_entry(payload: dict[str, object], action: dict[str, object]) -> dict[str, object] | None:
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    course = payload.get("course") if isinstance(payload.get("course"), dict) else {}
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    answer = artifacts.get("answer") if isinstance(artifacts.get("answer"), dict) else {}
    run_id = str(course.get("run_id") or payload.get("run_id") or "")
    if not run_id:
        return None
    paths = {
        "normalized_path": str(course.get("normalized_path") or ""),
        "index_path": str(artifacts.get("index_path") or ""),
        "semantic_index_path": str(artifacts.get("semantic_index_path") or ""),
        "graph_path": str(artifacts.get("graph_path") or ""),
        "answer_path": str(answer.get("answer_path") or ""),
    }
    return _query_plan_entry(
        kind="smoke",
        platform=str(payload.get("platform") or action.get("platform") or ""),
        run_id=run_id,
        status=str(payload.get("status") or ""),
        source_id=str(action.get("source_id") or source.get("source_id") or ""),
        source_ref=str(action.get("source_ref") or source.get("source_ref") or ""),
        title=str(source.get("title") or ""),
        query=str(answer.get("query") or "") or None,
        result_count=int(answer.get("result_count") or 0),
        evidence_count=int(answer.get("evidence_count") or 0),
        paths=paths,
    )


def _query_plan_entry(
    *,
    kind: str,
    platform: str,
    run_id: str,
    status: str,
    source_id: str,
    source_ref: str,
    title: str,
    query: str | None,
    result_count: int,
    evidence_count: int,
    paths: dict[str, str],
    stable_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    query_text = query or "<course-specific question>"
    index_ready = bool(paths.get("index_path"))
    semantic_ready = bool(paths.get("semantic_index_path"))
    graph_ready = bool(paths.get("graph_path"))
    status_ready = status in {"ok", "ready"}
    semantic_query_ready = status_ready and semantic_ready
    query_mode = "hybrid" if semantic_query_ready else "keyword"
    answer_ready = status_ready and bool(paths.get("answer_path")) and result_count > 0 and evidence_count > 0
    entry = {
        "kind": kind,
        "platform": platform,
        "run_id": run_id,
        "status": status,
        "source_id": source_id,
        "source_ref": source_ref,
        "title": title,
        "query": query,
        "query_mode": query_mode,
        "query_ready": status_ready and index_ready,
        "semantic_query_ready": semantic_query_ready,
        "graph_ready": status_ready and graph_ready,
        "answer_ready": answer_ready,
        "answer_result_count": result_count,
        "answer_evidence_count": evidence_count,
        "paths": paths,
        "commands": {
            "query": f"aoa-course query {shlex.quote(query_text)} --run {shlex.quote(run_id)} --mode {query_mode}",
            "answer": f"aoa-course answer {shlex.quote(query_text)} --run {shlex.quote(run_id)} --mode {query_mode}",
            "lesson_context": f"aoa-course lesson-context {shlex.quote(query_text)} --run {shlex.quote(run_id)} --mode {query_mode} --graph-limit 12",
            "graph": f"aoa-course build-graph --run {shlex.quote(run_id)}",
        },
        "mcp_commands": {
            "search": _mcp_call_command("search", {"query": query_text, "run": run_id, "mode": query_mode}),
            "answer": _mcp_call_command("answer", {"query": query_text, "run": run_id, "mode": query_mode}),
            "lesson_context": _mcp_call_command("lesson_context", {"query": query_text, "run": run_id, "mode": query_mode, "graph_limit": 12}),
            "evidence_report": _mcp_call_command("evidence_report", {"query": query_text, "run": run_id, "mode": query_mode}),
        },
    }
    if stable_identity is not None:
        entry["stable_identity"] = stable_identity
    return entry


def _mcp_call_command(tool: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    return f"aoa-course mcp call {tool} {shlex.quote(encoded)}"


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


def _snapshot_audit_status(
    packet: dict[str, object] | None,
    *,
    intake: dict[str, object] | None,
    repair_lanes: list[dict[str, object]],
) -> dict[str, object]:
    quality = packet.get("quality") if isinstance(packet, dict) and isinstance(packet.get("quality"), dict) else {}
    return _snapshot_audit_status_from_quality(
        quality,
        packet_available=packet is not None,
        intake=intake,
        repair_lanes=repair_lanes,
    )


def _snapshot_audit_status_from_quality(
    quality: dict[str, object],
    *,
    packet_available: bool,
    intake: dict[str, object] | None,
    repair_lanes: list[dict[str, object]],
) -> dict[str, object]:
    browser_report_count = _int_value(quality.get("browser_report_count"))
    reports_with_audit = _int_value(quality.get("browser_reports_with_snapshot_audit"))
    audit_count = _int_value(quality.get("snapshot_audit_count_total"))
    failure_count = _int_value(quality.get("snapshot_audit_failure_count_total"))
    all_reports_have_audit = _bool_value(
        quality.get("all_browser_reports_have_snapshot_audit"),
        default=browser_report_count == 0 or reports_with_audit >= browser_report_count,
    )
    all_audits_ok = _bool_value(quality.get("all_snapshot_audits_ok"), default=failure_count == 0)
    audit_lanes = [
        lane
        for lane in repair_lanes
        if isinstance(lane, dict) and lane.get("lane") == "browser_snapshot_diagnostics"
    ]
    intake_actions = _snapshot_audit_intake_actions(intake)
    if not packet_available:
        status = "not_built"
        reason = "calibration packet was not built for this run"
    elif browser_report_count == 0:
        status = "not_applicable"
        reason = "no browser smoke reports were included"
    elif all_reports_have_audit and all_audits_ok and failure_count == 0:
        status = "ok"
        reason = "browser snapshot audits are present and healthy"
    else:
        status = "partial"
        reason = "browser snapshot audit diagnostics need inspection"
    return {
        "schema": "aoa_course_connected_snapshot_audit_status_v1",
        "status": status,
        "reason": reason,
        "packet_available": packet_available,
        "browser_report_count": browser_report_count,
        "browser_reports_with_snapshot_audit": reports_with_audit,
        "snapshot_audit_count_total": audit_count,
        "snapshot_audit_failure_count_total": failure_count,
        "all_browser_reports_have_snapshot_audit": all_reports_have_audit,
        "all_snapshot_audits_ok": all_audits_ok,
        "intake_action_count": len(intake_actions),
        "intake_actions": intake_actions,
        "repair_lane_count": len(audit_lanes),
        "repair_lanes": audit_lanes,
        "next_commands": [
            str(command)
            for lane in audit_lanes
            for command in lane.get("next_commands", [])
            if str(command)
        ],
    }


def _snapshot_audit_intake_actions(intake: dict[str, object] | None) -> list[dict[str, object]]:
    actions = intake.get("actions") if isinstance(intake, dict) and isinstance(intake.get("actions"), list) else []
    compact: list[dict[str, object]] = []
    for action in actions:
        if not isinstance(action, dict) or action.get("lane") != "browser_snapshot_diagnostics":
            continue
        compact.append(
            {
                "lane": action.get("lane"),
                "severity": action.get("severity"),
                "platform": action.get("platform"),
                "surface": action.get("surface"),
                "reason": action.get("reason"),
                "title": action.get("title"),
                "eval_hint": action.get("eval_hint"),
            }
        )
    return compact


def _int_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool_value(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return default


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


def _repair_lanes(
    failures: list[dict[str, object]],
    *,
    intake: dict[str, object] | None,
    run_id: str,
    mode: str,
    allow_network: bool,
    platforms: list[str],
    live_scope: str,
    source_selection: dict[str, object] | None,
    execution_options: dict[str, object] | None,
    packet_path: Path | None,
) -> list[dict[str, object]]:
    lanes: list[dict[str, object]] = []
    source_selection = source_selection or {}
    execution_options = execution_options or {}
    rerun_command = _connected_rerun_command(
        run_id,
        platforms=platforms,
        live_scope=live_scope,
        source_ids=[str(item) for item in source_selection.get("ready_source_ids", []) if str(item)],
        execution_options=execution_options,
    )
    ready_source_ids = [str(item) for item in source_selection.get("ready_source_ids", []) if str(item)]
    preflight_command = _connected_preflight_command(
        platforms,
        live_scope=live_scope,
        execution_options=execution_options,
        source_ids=ready_source_ids,
    )

    for failure in failures:
        reason = str(failure.get("reason") or "inspect connected run failure")
        stage = str(failure.get("stage") or "")
        platform = str(failure.get("platform") or "")
        source_id = str(failure.get("source_id") or "")
        source_ref = str(failure.get("source_ref") or "")
        if reason == "live mode requires --allow-network":
            lanes.append(
                _lane(
                    lane="network_gate",
                    severity="blocker",
                    title="Review connected-source plan before network execution",
                    reason=reason,
                    next_commands=[preflight_command, rerun_command],
                    evidence_needed=["connected-source plan", "operator approval for --allow-network"],
                    source="connected_run_failure",
                )
            )
        elif stage == "source_readiness" or reason == "source is not ready":
            lanes.append(
                _lane(
                    lane="source_auth_or_readiness",
                    severity="high",
                    title="Repair source auth or readiness before live sync",
                    reason=reason,
                    platform=platform,
                    source_id=source_id,
                    source_ref=source_ref,
                    blockers=[str(item) for item in failure.get("blockers", [])] if isinstance(failure.get("blockers"), list) else [],
                    next_commands=_source_repair_commands(
                        platform,
                        preflight_command=_connected_preflight_command(
                            [platform] if platform else platforms,
                            live_scope=live_scope,
                            execution_options=execution_options,
                            source_ids=[source_id] if source_id else ready_source_ids,
                        ),
                        execution_options=execution_options,
                    ),
                    evidence_needed=["redacted preflight report", "source registry entry", "auth-state or token readiness proof"],
                    source="connected_run_failure",
                )
            )
        elif reason == "no ready sources matched this connected run":
            lanes.append(
                _lane(
                    lane="source_selection",
                    severity="high",
                    title="Select or register at least one ready connected source",
                    reason=reason,
                    next_commands=["aoa-course sources list", preflight_command],
                    evidence_needed=["source registry with enabled sources", "read-only connected plan with ready source ids"],
                    source="connected_run_failure",
                )
            )
        elif stage == "sync":
            lanes.append(
                _lane(
                    lane="source_sync",
                    severity="high",
                    title="Repair connected-source sync action",
                    reason=reason,
                    platform=platform,
                    next_commands=[preflight_command, rerun_command],
                    evidence_needed=["sync receipt", "redacted normalized bundle path", "source checkpoint status"],
                    source="connected_run_failure",
                )
            )
        elif stage == "smoke":
            lanes.append(
                _lane(
                    lane="live_smoke_or_selector",
                    severity="high",
                    title="Repair live smoke, selector, or API smoke route",
                    reason=reason,
                    platform=platform,
                    source_id=source_id,
                    source_ref=source_ref,
                    next_commands=[rerun_command],
                    evidence_needed=["redacted smoke report", "minimal safe fixture or snapshot", "expected answer evidence"],
                    source="connected_run_failure",
                )
            )
        elif stage == "calibration_packet":
            command = _calibration_intake_command(run_id, packet_path)
            lanes.append(
                _lane(
                    lane="calibration_packet_intake",
                    severity="medium",
                    title="Run calibration intake for packet-level failures",
                    reason=reason,
                    next_commands=[command] if command else [],
                    evidence_needed=["live calibration packet", "intake report actions"],
                    source="connected_run_failure",
                )
            )
        else:
            lanes.append(
                _lane(
                    lane="connected_run_failure",
                    severity="medium",
                    title="Classify unresolved connected-run failure",
                    reason=reason,
                    platform=platform,
                    source_id=source_id,
                    source_ref=source_ref,
                    next_commands=[rerun_command],
                    evidence_needed=["connected run receipt", "stage payload summary", "redacted runtime artifacts"],
                    source="connected_run_failure",
                )
            )

    if intake and isinstance(intake.get("actions"), list):
        for action in intake["actions"]:
            if not isinstance(action, dict):
                continue
            command = _calibration_intake_command(run_id, packet_path)
            lanes.append(
                _lane(
                    lane=str(action.get("lane") or "calibration_intake"),
                    severity=str(action.get("severity") or "medium"),
                    title=str(action.get("title") or "Follow calibration intake action"),
                    reason=str(action.get("reason") or "calibration intake action"),
                    platform=str(action.get("platform") or ""),
                    next_commands=[command] if command else [],
                    evidence_needed=[
                        "redacted calibration packet",
                        "minimal safe fixture or snapshot when source behavior changed",
                        "repo-local eval intake candidate",
                    ],
                    eval_hint=str(action.get("eval_hint") or ""),
                    source="calibration_intake",
                )
            )
    return _dedupe_repair_lanes(lanes)


def _lane(
    *,
    lane: str,
    severity: str,
    title: str,
    reason: str,
    next_commands: list[str],
    evidence_needed: list[str],
    source: str,
    platform: str = "",
    source_id: str = "",
    source_ref: str = "",
    blockers: list[str] | None = None,
    eval_hint: str = "",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "lane": lane,
        "severity": severity,
        "title": title,
        "reason": reason,
        "source": source,
        "next_commands": [command for command in next_commands if command],
        "evidence_needed": evidence_needed,
    }
    if platform:
        payload["platform"] = platform
    if source_id:
        payload["source_id"] = source_id
    if source_ref:
        payload["source_ref"] = source_ref
    if blockers:
        payload["blockers"] = blockers
    if eval_hint:
        payload["eval_hint"] = eval_hint
    return payload


def _dedupe_repair_lanes(lanes: list[dict[str, object]]) -> list[dict[str, object]]:
    deduped: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for lane in lanes:
        key = (
            str(lane.get("lane") or ""),
            str(lane.get("platform") or ""),
            str(lane.get("source_id") or ""),
            str(lane.get("reason") or ""),
            str(lane.get("source") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(lane)
    return deduped


def _connected_preflight_command(
    platforms: list[str],
    *,
    live_scope: str,
    execution_options: dict[str, object],
    source_ids: list[str] | None = None,
) -> str:
    parts = ["aoa-course preflight connected-plan"]
    for platform in platforms:
        parts.append(f"--platform {shlex.quote(platform)}")
    for source_id in source_ids or []:
        parts.append(f"--source-id {shlex.quote(source_id)}")
    if live_scope:
        parts.append(f"--live-scope {shlex.quote(live_scope)}")
    if execution_options.get("query"):
        parts.append(f"--query {shlex.quote(str(execution_options.get('query')))}")
    if execution_options.get("link_pattern"):
        parts.append(f"--link-pattern {shlex.quote(str(execution_options.get('link_pattern')))}")
    if execution_options.get("stepik_token_env") and "stepik" in platforms:
        parts.append(f"--stepik-token-env {shlex.quote(str(execution_options.get('stepik_token_env')))}")
    if execution_options.get("browser_state_file") and any(platform in BROWSER_PLATFORMS for platform in platforms):
        parts.append(f"--state-file {shlex.quote(str(execution_options.get('browser_state_file')))}")
    for option, flag in [
        ("max_lessons", "--max-lessons"),
        ("max_pages", "--max-pages"),
        ("max_sources", "--max-sources"),
    ]:
        value = execution_options.get(option)
        if value is not None:
            parts.append(f"{flag} {int(value)}")
    return " ".join(parts)


def _connected_rerun_command(
    run_id: str,
    *,
    platforms: list[str],
    live_scope: str,
    source_ids: list[str],
    execution_options: dict[str, object],
) -> str:
    parts = [
        "aoa-course calibration connected-run",
        "--mode live",
        "--allow-network",
        f"--run {shlex.quote(run_id)}",
    ]
    for platform in platforms:
        parts.append(f"--platform {shlex.quote(platform)}")
    for source_id in source_ids:
        parts.append(f"--source-id {shlex.quote(source_id)}")
    if live_scope:
        parts.append(f"--live-scope {shlex.quote(live_scope)}")
    for option, flag in [
        ("query", "--query"),
        ("link_pattern", "--link-pattern"),
        ("stepik_token_env", "--stepik-token-env"),
        ("browser_state_file", "--state-file"),
    ]:
        value = execution_options.get(option)
        if value:
            parts.append(f"{flag} {shlex.quote(str(value))}")
    for option, flag in [
        ("max_lessons", "--max-lessons"),
        ("max_pages", "--max-pages"),
        ("max_sources", "--max-sources"),
        ("source_limit", "--source-limit"),
    ]:
        value = execution_options.get(option)
        if value is not None:
            parts.append(f"{flag} {int(value)}")
    return " ".join(parts)


def _source_repair_commands(platform: str, *, preflight_command: str, execution_options: dict[str, object]) -> list[str]:
    commands = [preflight_command]
    if platform in BROWSER_PLATFORMS:
        commands.insert(0, f"aoa-course auth plan-browser-state {platform} account")
    elif platform == "stepik":
        token_env = str(execution_options.get("stepik_token_env") or "STEPIK_API_TOKEN")
        commands.insert(0, f"export {token_env}=<stepik-api-token>")
    return commands


def _calibration_intake_command(run_id: str, packet_path: Path | None) -> str:
    if not packet_path:
        return ""
    return f"aoa-course calibration intake --run {shlex.quote(run_id + '-intake')} --packet {shlex.quote(str(packet_path))}"


def _next_steps(
    status: str,
    mode: str,
    allow_network: bool,
    failures: list[dict[str, object]],
    intake: dict[str, object] | None,
    repair_lanes: list[dict[str, object]],
) -> list[str]:
    if mode == "live" and not allow_network:
        return ["rerun with --allow-network after reviewing the connected-source plan and auth/source readiness"]
    if intake and isinstance(intake.get("next_steps"), list) and intake.get("next_steps"):
        return [str(item) for item in intake["next_steps"]]
    if status == "ok" and mode == "fixture":
        return ["connect operator-owned credentials, run preflight connected-plan, then rerun calibration connected-run --mode live --allow-network"]
    if status == "ok":
        return ["use the calibration packet as field evidence for selector, sync, retrieval, and eval follow-up"]
    if repair_lanes:
        return [str(command) for lane in repair_lanes for command in lane.get("next_commands", []) if str(command)]
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
