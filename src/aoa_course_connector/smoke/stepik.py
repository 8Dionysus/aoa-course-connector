"""Stepik smoke reports for fixture and gated live source-registry routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.index import build_semantic_index
from aoa_course_connector.query import render_answer_packet, write_answer_packet
from aoa_course_connector.smoke.answer_quality import answer_quality_failures, summarize_answer_packet
from aoa_course_connector.sources import upsert_source
from aoa_course_connector.storage import create_storage_roots
from aoa_course_connector.sync import sync_stepik_fixture_sources, sync_stepik_live_sources
from aoa_course_connector.sync.stepik import STEPIK_FIXTURE_COURSE_ID


DEFAULT_QUERY = "Python course"


def smoke_stepik_fixture(
    roots: StorageRoots,
    *,
    course_id: int,
    run_id: str,
    title: str | None = None,
    query: str | None = None,
    build_artifacts: bool = True,
) -> dict[str, object]:
    if int(course_id) != STEPIK_FIXTURE_COURSE_ID:
        expected_ref = str(STEPIK_FIXTURE_COURSE_ID)
        actual_ref = str(course_id)
        return {
            "schema": "aoa_course_stepik_smoke_report_v1",
            "status": "error",
            "run_id": run_id,
            "platform": "stepik",
            "source_mode": "stepik_fixture_smoke",
            "network_touched": False,
            "source": {
                "source_ref": actual_ref,
                "expected_fixture_source_ref": expected_ref,
                "registry_state": "not_registered",
            },
            "failures": ["stepik_fixture_course_id_mismatch"],
            "error": (
                f"stepik-fixture smoke only supports fixture course {expected_ref}; "
                f"use smoke stepik-live for course {actual_ref}"
            ),
            "sync": {"enabled": False},
            "course": {"enabled": False},
            "artifacts": {"enabled": False},
            "privacy": {
                "raw_paths": [],
                "raw_paths_are_local_runtime_state": True,
                "do_not_commit_raw_api_or_auth_state": True,
            },
        }
    source_ref = str(course_id)
    source = _register_source(roots, source_ref=source_ref, title=title, access_mode="public_api")
    sync = sync_stepik_fixture_sources(
        roots,
        sync_run_id=run_id,
        source_refs=[source_ref],
        source_limit=1,
        build_artifacts=build_artifacts,
    )
    return _report(
        roots,
        run_id=run_id,
        source=source,
        source_mode="stepik_fixture_smoke",
        sync=sync,
        query=query or DEFAULT_QUERY,
        build_artifacts=build_artifacts,
        network_touched=False,
    )


def smoke_stepik_live(
    roots: StorageRoots,
    *,
    course_id: int,
    run_id: str,
    title: str | None = None,
    access_mode: str = "public_api",
    token_env: str = "STEPIK_API_TOKEN",
    state_file: Path | None = None,
    max_sections: int | None = 1,
    max_units_per_section: int | None = 2,
    max_steps_per_lesson: int | None = 5,
    batch_size: int = 20,
    include_step_sources: bool = False,
    query: str | None = None,
    build_artifacts: bool = True,
) -> dict[str, object]:
    source_ref = str(course_id)
    source = _register_source(roots, source_ref=source_ref, title=title, access_mode=access_mode)
    sync = sync_stepik_live_sources(
        roots,
        sync_run_id=run_id,
        token_env=token_env,
        state_file=state_file,
        max_sections=max_sections,
        max_units_per_section=max_units_per_section,
        max_steps_per_lesson=max_steps_per_lesson,
        batch_size=batch_size,
        include_step_sources=include_step_sources,
        source_refs=[source_ref],
        source_limit=1,
        build_artifacts=build_artifacts,
    )
    return _report(
        roots,
        run_id=run_id,
        source=source,
        source_mode="stepik_live_smoke",
        sync=sync,
        query=query or DEFAULT_QUERY,
        build_artifacts=build_artifacts,
        network_touched=True,
    )


def _register_source(
    roots: StorageRoots,
    *,
    source_ref: str,
    title: str | None,
    access_mode: str,
) -> dict[str, object]:
    create_storage_roots(roots)
    source, path, state = upsert_source(
        roots.data,
        platform="stepik",
        source_ref=source_ref,
        title=title or f"Stepik course {source_ref}",
        access_mode=access_mode,
    )
    return {"state": state, "registry_path": str(path), **source}


def _report(
    roots: StorageRoots,
    *,
    run_id: str,
    source: dict[str, object],
    source_mode: str,
    sync: dict[str, object],
    query: str,
    build_artifacts: bool,
    network_touched: bool,
) -> dict[str, object]:
    checkpoints = sync.get("synced_sources") if isinstance(sync.get("synced_sources"), list) else []
    checkpoint = checkpoints[0] if checkpoints and isinstance(checkpoints[0], dict) else None
    course_summary = _course_summary(checkpoint)
    artifact_summary = _artifact_summary(roots, checkpoint, query, build_artifacts)
    failures = _failures(sync, checkpoint, course_summary, artifact_summary, build_artifacts)
    return {
        "schema": "aoa_course_stepik_smoke_report_v1",
        "status": "ok" if not failures else "partial",
        "run_id": run_id,
        "platform": "stepik",
        "source_mode": source_mode,
        "network_touched": network_touched,
        "source": {
            "source_id": source.get("source_id"),
            "source_ref": source.get("source_ref"),
            "title": source.get("title"),
            "access_mode": source.get("access_mode"),
            "registry_path": source.get("registry_path"),
            "registry_state": source.get("state"),
        },
        "failures": failures,
        "sync": _sync_summary(sync),
        "course": course_summary,
        "artifacts": artifact_summary,
        "privacy": {
            "raw_paths": _raw_paths(checkpoint),
            "raw_paths_are_local_runtime_state": True,
            "do_not_commit_raw_api_or_auth_state": True,
        },
    }


def _sync_summary(sync: dict[str, object]) -> dict[str, object]:
    status = sync.get("sync_status") if isinstance(sync.get("sync_status"), dict) else {}
    return {
        "status": sync.get("status"),
        "sync_run_id": sync.get("sync_run_id"),
        "source_count": sync.get("source_count", 0),
        "synced_count": sync.get("synced_count", 0),
        "failed_count": sync.get("failed_count", 0),
        "receipt_path": sync.get("receipt_path"),
        "checkpoint_count": status.get("checkpoint_count", 0),
        "ok_count": status.get("ok_count", 0),
        "error_count": status.get("error_count", 0),
    }


def _course_summary(checkpoint: dict[str, object] | None) -> dict[str, object]:
    if not checkpoint:
        return {"enabled": False}
    normalized_path = Path(str(checkpoint.get("normalized_path") or ""))
    if not normalized_path.is_file():
        return {"enabled": True, "normalized_path": str(normalized_path), "bundle_loaded": False}
    bundle = json.loads(normalized_path.read_text(encoding="utf-8"))
    counters = {
        "course_count": 0,
        "module_count": 0,
        "lesson_count": 0,
        "step_count": 0,
        "assignment_count": 0,
        "asset_count": 0,
    }
    for course in bundle.get("courses", []):
        if not isinstance(course, dict):
            continue
        counters["course_count"] += 1
        for module in course.get("modules", []):
            if not isinstance(module, dict):
                continue
            counters["module_count"] += 1
            for lesson in module.get("lessons", []):
                if not isinstance(lesson, dict):
                    continue
                counters["lesson_count"] += 1
                counters["step_count"] += len(lesson.get("steps", [])) if isinstance(lesson.get("steps"), list) else 0
                counters["assignment_count"] += len(lesson.get("assignments", [])) if isinstance(lesson.get("assignments"), list) else 0
                counters["asset_count"] += len(lesson.get("assets", [])) if isinstance(lesson.get("assets"), list) else 0
    return {
        "enabled": True,
        "status": checkpoint.get("status"),
        "run_id": checkpoint.get("run_id"),
        "normalized_path": str(normalized_path),
        "bundle_loaded": True,
        "evidence_count": len(bundle.get("evidence", [])) if isinstance(bundle.get("evidence"), list) else 0,
        **counters,
    }


def _artifact_summary(
    roots: StorageRoots,
    checkpoint: dict[str, object] | None,
    query: str,
    build_artifacts: bool,
) -> dict[str, object]:
    if not build_artifacts:
        return {"enabled": False}
    if not checkpoint:
        return {"enabled": True, "answer": {"enabled": False}}
    run_id = str(checkpoint.get("run_id") or "")
    semantic_index_path = build_semantic_index(roots, run_id=run_id) if checkpoint.get("normalized_path") else ""
    answer: dict[str, object] = {"enabled": False}
    if checkpoint.get("index_path") and query:
        packet = render_answer_packet(roots, query, run_id, 5)
        answer_path = write_answer_packet(packet, roots, run_id)
        answer = {
            "enabled": True,
            "query": query,
            "answer_path": str(answer_path),
            "result_count": packet.get("result_count", 0),
            "evidence_count": len(packet.get("evidence_chain", [])) if isinstance(packet.get("evidence_chain"), list) else 0,
            "has_source_timestamps": packet.get("freshness_report", {}).get("has_source_timestamps")
            if isinstance(packet.get("freshness_report"), dict)
            else False,
            "quality": summarize_answer_packet(packet, expected_platform="stepik"),
        }
    return {
        "enabled": True,
        "index_path": checkpoint.get("index_path", ""),
        "semantic_index_path": str(semantic_index_path),
        "graph_path": checkpoint.get("graph_path", ""),
        "answer": answer,
    }


def _failures(
    sync: dict[str, object],
    checkpoint: dict[str, object] | None,
    course_summary: dict[str, object],
    artifact_summary: dict[str, object],
    build_artifacts: bool,
) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    if sync.get("status") != "ok":
        failures.append({"surface": "sync", "reason": "sync status is not ok", "status": sync.get("status")})
    if not checkpoint:
        failures.append({"surface": "sync", "reason": "no synced checkpoint"})
    if checkpoint and checkpoint.get("status") != "ok":
        failures.append({"surface": "checkpoint", "reason": "checkpoint status is not ok", "status": checkpoint.get("status")})
    if checkpoint and not course_summary.get("bundle_loaded"):
        failures.append({"surface": "course", "reason": "normalized bundle was not loaded"})
    answer = artifact_summary.get("answer") if isinstance(artifact_summary.get("answer"), dict) else {}
    if build_artifacts and checkpoint and answer.get("enabled") and int(answer.get("result_count") or 0) < 1:
        failures.append({"surface": "answer", "reason": "query returned no results", "query": answer.get("query")})
    failures.extend(answer_quality_failures(answer))
    return failures


def _raw_paths(checkpoint: dict[str, object] | None) -> list[str]:
    if isinstance(checkpoint, dict) and checkpoint.get("cursor"):
        return [str(checkpoint["cursor"])]
    return []
