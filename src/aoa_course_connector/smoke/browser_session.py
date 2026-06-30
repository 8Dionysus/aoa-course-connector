"""Browser-session smoke reports for fixture, snapshot, and gated live routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.discover import discover_browser_fixture, discover_browser_live, discover_browser_snapshot
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index
from aoa_course_connector.ingest import crawl_browser_live, materialize_browser_fixture, materialize_browser_snapshot
from aoa_course_connector.query import render_answer_packet, write_answer_packet


DEFAULT_QUERIES = {
    "getcourse": "mentor anti-rollback vendor boot",
    "skillspace": "timestamp window reproduction step",
}


def smoke_browser_fixture(
    roots: StorageRoots,
    *,
    platform: str,
    run_id: str,
    query: str | None = None,
    register: bool = False,
    build_artifacts: bool = True,
) -> dict[str, object]:
    platform = platform.casefold()
    discovery = discover_browser_fixture(roots, platform, run_id=f"{run_id}-discovery", register=register)
    materialized = materialize_browser_fixture(roots, platform, run_id=f"{run_id}-course")
    return _report(
        roots,
        run_id=run_id,
        platform=platform,
        source_mode="browser_fixture_smoke",
        discovery=discovery,
        materialized=materialized,
        query=query or DEFAULT_QUERIES.get(platform),
        build_artifacts=build_artifacts,
        network_touched=False,
    )


def smoke_browser_snapshot(
    roots: StorageRoots,
    *,
    platform: str,
    run_id: str,
    catalog_snapshot: Path | None = None,
    course_snapshot: Path | None = None,
    query: str | None = None,
    register: bool = False,
    build_artifacts: bool = True,
) -> dict[str, object]:
    if not catalog_snapshot and not course_snapshot:
        raise ValueError("provide --catalog-snapshot, --course-snapshot, or both")
    platform = platform.casefold()
    discovery = (
        discover_browser_snapshot(roots, catalog_snapshot, platform=platform, run_id=f"{run_id}-discovery", register=register)
        if catalog_snapshot
        else None
    )
    materialized = (
        materialize_browser_snapshot(roots, course_snapshot, platform=platform, run_id=f"{run_id}-course")
        if course_snapshot
        else None
    )
    return _report(
        roots,
        run_id=run_id,
        platform=platform,
        source_mode="browser_snapshot_smoke",
        discovery=discovery,
        materialized=materialized,
        query=query,
        build_artifacts=build_artifacts,
        network_touched=False,
    )


def smoke_browser_live(
    roots: StorageRoots,
    *,
    platform: str,
    run_id: str,
    catalog_url: str | None = None,
    course_url: str | None = None,
    state_file: Path | None = None,
    wait_until: str = "networkidle",
    max_sources: int = 50,
    max_pages: int = 5,
    max_lessons: int = 20,
    link_pattern: str | None = None,
    query: str | None = None,
    register: bool = False,
    build_artifacts: bool = True,
) -> dict[str, object]:
    if not catalog_url and not course_url:
        raise ValueError("provide --catalog-url, --course-url, or both")
    platform = platform.casefold()
    discovery = (
        discover_browser_live(
            roots,
            catalog_url,
            platform,
            run_id=f"{run_id}-discovery",
            state_file=state_file,
            wait_until=wait_until,
            max_sources=max_sources,
            max_pages=max_pages,
            link_pattern=link_pattern,
            register=register,
        )
        if catalog_url
        else None
    )
    materialized = (
        crawl_browser_live(
            roots,
            course_url,
            platform,
            run_id=f"{run_id}-course",
            state_file=state_file,
            wait_until=wait_until,
            max_lessons=max_lessons,
            link_pattern=link_pattern,
        )
        if course_url
        else None
    )
    return _report(
        roots,
        run_id=run_id,
        platform=platform,
        source_mode="browser_live_smoke",
        discovery=discovery,
        materialized=materialized,
        query=query,
        build_artifacts=build_artifacts,
        network_touched=True,
    )


def _report(
    roots: StorageRoots,
    *,
    run_id: str,
    platform: str,
    source_mode: str,
    discovery: dict[str, object] | None,
    materialized: dict[str, object] | None,
    query: str | None,
    build_artifacts: bool,
    network_touched: bool,
) -> dict[str, object]:
    run_for_artifacts = str(materialized.get("run_id")) if materialized else ""
    course_summary = _course_summary(materialized)
    artifact_summary = _artifact_summary(roots, run_for_artifacts, query, build_artifacts) if materialized else {}
    failures = _failures(discovery, materialized, course_summary, artifact_summary, build_artifacts)
    raw_paths = _raw_paths(discovery, materialized)
    return {
        "schema": "aoa_course_browser_smoke_report_v1",
        "status": "ok" if not failures else "partial",
        "run_id": run_id,
        "platform": platform,
        "source_mode": source_mode,
        "network_touched": network_touched,
        "failures": failures,
        "discovery": _discovery_summary(discovery),
        "course": course_summary,
        "artifacts": artifact_summary,
        "privacy": {
            "raw_paths": raw_paths,
            "raw_paths_are_local_runtime_state": True,
            "do_not_commit_raw_html_or_auth_state": True,
        },
    }


def _discovery_summary(receipt: dict[str, object] | None) -> dict[str, object]:
    if not receipt:
        return {"enabled": False}
    pagination = receipt.get("pagination") if isinstance(receipt.get("pagination"), dict) else {}
    return {
        "enabled": True,
        "status": receipt.get("status"),
        "run_id": receipt.get("run_id"),
        "course_count": receipt.get("course_count", 0),
        "page_count": receipt.get("page_count", 0),
        "next_link_count": pagination.get("next_link_count", 0),
        "registered_source_count": len(receipt.get("registered_sources", [])) if isinstance(receipt.get("registered_sources"), list) else 0,
        "receipt_path": receipt.get("receipt_path"),
        "raw_path": receipt.get("raw_path"),
    }


def _course_summary(receipt: dict[str, object] | None) -> dict[str, object]:
    if not receipt:
        return {"enabled": False}
    normalized_path = Path(str(receipt.get("normalized_path") or ""))
    if not normalized_path.is_file():
        return {"enabled": True, "status": receipt.get("status"), "normalized_path": str(normalized_path), "bundle_loaded": False}
    bundle = json.loads(normalized_path.read_text(encoding="utf-8"))
    counters = {
        "course_count": 0,
        "module_count": 0,
        "lesson_count": 0,
        "asset_count": 0,
        "assignment_count": 0,
        "comment_count": 0,
        "progress_detected_count": 0,
    }
    progress_states: list[str] = []
    for course in bundle.get("courses", []):
        if not isinstance(course, dict):
            continue
        counters["course_count"] += 1
        progress = course.get("progress")
        if isinstance(progress, dict) and (progress.get("state") or progress.get("percent") or progress.get("label")):
            counters["progress_detected_count"] += 1
            progress_states.append(str(progress.get("state") or "unknown"))
        for module in course.get("modules", []):
            if not isinstance(module, dict):
                continue
            counters["module_count"] += 1
            for lesson in module.get("lessons", []):
                if not isinstance(lesson, dict):
                    continue
                counters["lesson_count"] += 1
                counters["asset_count"] += len(lesson.get("assets", [])) if isinstance(lesson.get("assets"), list) else 0
                counters["assignment_count"] += len(lesson.get("assignments", [])) if isinstance(lesson.get("assignments"), list) else 0
                for thread in lesson.get("comment_threads", []):
                    if isinstance(thread, dict) and isinstance(thread.get("comments"), list):
                        counters["comment_count"] += len(thread["comments"])
    return {
        "enabled": True,
        "status": receipt.get("status"),
        "run_id": receipt.get("run_id"),
        "normalized_path": str(normalized_path),
        "bundle_loaded": True,
        "evidence_count": len(bundle.get("evidence", [])) if isinstance(bundle.get("evidence"), list) else 0,
        "progress_states": sorted(set(progress_states)),
        **counters,
    }


def _artifact_summary(roots: StorageRoots, run_id: str, query: str | None, build_artifacts: bool) -> dict[str, object]:
    if not build_artifacts:
        return {"enabled": False}
    index_path = build_keyword_index(roots, run_id=run_id)
    graph_path = build_graph(roots, run_id=run_id)
    answer: dict[str, object] = {"enabled": False}
    if query:
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
        }
    return {"enabled": True, "index_path": str(index_path), "graph_path": str(graph_path), "answer": answer}


def _failures(
    discovery: dict[str, object] | None,
    materialized: dict[str, object] | None,
    course_summary: dict[str, object],
    artifact_summary: dict[str, object],
    build_artifacts: bool,
) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    if discovery and discovery.get("status") != "ok":
        failures.append({"surface": "discovery", "reason": "discovery status is not ok", "status": discovery.get("status")})
    if materialized and materialized.get("status") != "ok":
        failures.append({"surface": "course", "reason": "materialization status is not ok", "status": materialized.get("status")})
    if materialized and not course_summary.get("bundle_loaded"):
        failures.append({"surface": "course", "reason": "normalized bundle was not loaded"})
    answer = artifact_summary.get("answer") if isinstance(artifact_summary.get("answer"), dict) else {}
    if build_artifacts and materialized and answer.get("enabled") and int(answer.get("result_count") or 0) < 1:
        failures.append({"surface": "answer", "reason": "query returned no results", "query": answer.get("query")})
    return failures


def _raw_paths(discovery: dict[str, object] | None, materialized: dict[str, object] | None) -> list[str]:
    paths = []
    for receipt in [discovery, materialized]:
        if isinstance(receipt, dict) and receipt.get("raw_path"):
            paths.append(str(receipt["raw_path"]))
    return paths
