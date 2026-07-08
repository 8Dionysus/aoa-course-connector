"""Stepik source-registry sync orchestration."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index, build_semantic_index
from aoa_course_connector.ingest import materialize_stepik_fixture, materialize_stepik_live
from aoa_course_connector.sources import load_registry
from aoa_course_connector.storage import create_storage_roots, sync_data_dir
from aoa_course_connector.sync.checkpoints import load_sync_status, make_checkpoint, normalized_identity_summary, upsert_checkpoint


STEPIK_ACCESS_MODES = {"public_api", "api_token", "oauth", "browser_session"}
STEPIK_FIXTURE_COURSE_ID = 67


def sync_stepik_fixture_sources(
    roots: StorageRoots,
    *,
    sync_run_id: str = "stepik-sync-fixture",
    source_refs: list[str] | None = None,
    source_ids: list[str] | None = None,
    source_limit: int | None = None,
    build_artifacts: bool = False,
) -> dict[str, object]:
    create_storage_roots(roots)
    sources = _selected_stepik_sources(roots, source_refs=source_refs, source_ids=source_ids, source_limit=source_limit)
    receipt = _base_receipt(sync_run_id, "stepik_fixture_sync", sources, network_touched=False)
    for source in sources:
        child_run = _child_run_id(sync_run_id, source)
        try:
            course_id = _parse_stepik_course_id(str(source.get("source_ref") or ""))
            if course_id != STEPIK_FIXTURE_COURSE_ID:
                raise ValueError(
                    f"stepik-fixture sync only supports fixture course {STEPIK_FIXTURE_COURSE_ID}; "
                    f"use stepik-live sync for course {course_id}"
                )
            materialized = materialize_stepik_fixture(roots, run_id=child_run, source=source)
            checkpoint = _checkpoint_from_materialized(
                roots,
                source,
                sync_run_id,
                child_run,
                materialized,
                build_artifacts=build_artifacts,
            )
            receipt["synced_sources"].append(checkpoint)
        except Exception as exc:  # pragma: no cover - defensive sync accounting
            checkpoint = make_checkpoint(
                source=source,
                sync_run_id=sync_run_id,
                run_id=child_run,
                status="error",
                error=str(exc),
            )
            upsert_checkpoint(roots, checkpoint)
            receipt["failed_sources"].append(checkpoint)
    return _finish_receipt(roots, receipt, empty_error="no enabled stepik API sources matched this sync")


def sync_stepik_live_sources(
    roots: StorageRoots,
    *,
    sync_run_id: str = "stepik-live-sync",
    token_env: str = "STEPIK_API_TOKEN",
    state_file: Path | None = None,
    max_sections: int | None = 1,
    max_units_per_section: int | None = 2,
    max_steps_per_lesson: int | None = 5,
    batch_size: int = 20,
    include_step_sources: bool = False,
    max_step_sources: int | None = 10,
    step_source_timeout: float = 5.0,
    source_refs: list[str] | None = None,
    source_ids: list[str] | None = None,
    source_limit: int | None = None,
    build_artifacts: bool = False,
) -> dict[str, object]:
    create_storage_roots(roots)
    sources = _selected_stepik_sources(roots, source_refs=source_refs, source_ids=source_ids, source_limit=source_limit)
    receipt = _base_receipt(sync_run_id, "stepik_live_sync", sources, network_touched=True)
    for source in sources:
        child_run = _child_run_id(sync_run_id, source)
        try:
            course_id = _parse_stepik_course_id(str(source.get("source_ref") or ""))
            materialized = materialize_stepik_live(
                roots,
                course_id=course_id,
                run_id=child_run,
                token_env=token_env,
                state_file=state_file,
                max_sections=max_sections,
                max_units_per_section=max_units_per_section,
                max_steps_per_lesson=max_steps_per_lesson,
                batch_size=batch_size,
                include_step_sources=include_step_sources,
                max_step_sources=max_step_sources,
                step_source_timeout=step_source_timeout,
                source=source,
            )
            checkpoint = _checkpoint_from_materialized(
                roots,
                source,
                sync_run_id,
                child_run,
                materialized,
                build_artifacts=build_artifacts,
            )
            receipt["synced_sources"].append(checkpoint)
        except Exception as exc:  # pragma: no cover - live API is externally variable
            checkpoint = make_checkpoint(
                source=source,
                sync_run_id=sync_run_id,
                run_id=child_run,
                status="error",
                error=str(exc),
            )
            upsert_checkpoint(roots, checkpoint)
            receipt["failed_sources"].append(checkpoint)
    return _finish_receipt(roots, receipt, empty_error="no enabled stepik API sources matched this sync")


def parse_stepik_course_id(source_ref: str) -> int:
    return _parse_stepik_course_id(source_ref)


def _selected_stepik_sources(
    roots: StorageRoots,
    *,
    source_refs: list[str] | None,
    source_ids: list[str] | None,
    source_limit: int | None,
) -> list[dict[str, Any]]:
    registry = load_registry(roots.data)
    wanted_refs = {str(source_ref) for source_ref in source_refs or []}
    wanted_ids = {str(source_id) for source_id in source_ids or []}
    sources = [
        source
        for source in registry.get("sources", [])
        if isinstance(source, dict)
        and source.get("enabled", True)
        and source.get("platform") == "stepik"
        and source.get("access_mode") in STEPIK_ACCESS_MODES
        and (not wanted_refs or str(source.get("source_ref") or "") in wanted_refs)
        and (not wanted_ids or str(source.get("source_id") or "") in wanted_ids)
    ]
    sources = sorted(sources, key=lambda item: str(item.get("source_id") or item.get("source_ref") or ""))
    return sources[:source_limit] if source_limit is not None else sources


def _parse_stepik_course_id(source_ref: str) -> int:
    text = source_ref.strip()
    if text.isdigit():
        return int(text)
    match = re.search(r"(?:stepik\.org/)?course/(\d+)", text)
    if match:
        return int(match.group(1))
    raise ValueError(f"cannot parse Stepik course id from source_ref: {source_ref}")


def _checkpoint_from_materialized(
    roots: StorageRoots,
    source: dict[str, Any],
    sync_run_id: str,
    child_run: str,
    materialized: dict[str, object],
    *,
    build_artifacts: bool,
) -> dict[str, object]:
    index_path = ""
    semantic_index_path = ""
    graph_path = ""
    if build_artifacts:
        index_path = str(build_keyword_index(roots, run_id=child_run))
        semantic_index_path = str(build_semantic_index(roots, run_id=child_run))
        graph_path = str(build_graph(roots, run_id=child_run))
    checkpoint = make_checkpoint(
        source=source,
        sync_run_id=sync_run_id,
        run_id=child_run,
        status="ok",
        cursor=str(materialized.get("raw_path") or ""),
        receipt_path=str(materialized.get("receipt_path") or ""),
        normalized_path=str(materialized.get("normalized_path") or ""),
        index_path=index_path,
        semantic_index_path=semantic_index_path,
        graph_path=graph_path,
        stable_identity=normalized_identity_summary(str(materialized.get("normalized_path") or "")),
    )
    upsert_checkpoint(roots, checkpoint)
    return checkpoint


def _base_receipt(sync_run_id: str, source_mode: str, sources: list[dict[str, Any]], *, network_touched: bool) -> dict[str, object]:
    return {
        "schema": "aoa_course_sync_receipt_v1",
        "status": "ok",
        "sync_run_id": sync_run_id,
        "source_mode": source_mode,
        "source_count": len(sources),
        "synced_sources": [],
        "failed_sources": [],
        "started_at": _now(),
        "network_touched": network_touched,
    }


def _finish_receipt(roots: StorageRoots, receipt: dict[str, object], *, empty_error: str) -> dict[str, object]:
    synced = receipt.get("synced_sources") if isinstance(receipt.get("synced_sources"), list) else []
    failed = receipt.get("failed_sources") if isinstance(receipt.get("failed_sources"), list) else []
    receipt["synced_count"] = len(synced)
    receipt["failed_count"] = len(failed)
    receipt["completed_at"] = _now()
    if int(receipt.get("source_count") or 0) == 0:
        receipt["status"] = "error"
        receipt["error"] = empty_error
    elif failed and not synced:
        receipt["status"] = "error"
    elif failed:
        receipt["status"] = "partial"
    sync_run_id = str(receipt.get("sync_run_id") or "sync")
    sync_dir = sync_data_dir(roots, sync_run_id)
    sync_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = sync_dir / "sync_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    receipt["sync_status"] = load_sync_status(roots, sync_run_id=sync_run_id)
    return receipt


def _child_run_id(sync_run_id: str, source: dict[str, Any]) -> str:
    return f"{sync_run_id}-{_slug(source.get('source_id') or source.get('source_ref') or 'source')}"


def _slug(value: object) -> str:
    text = str(value or "").casefold()
    slug = "".join(ch if ch.isalnum() else "-" for ch in text).strip("-")
    return slug or "item"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
