"""Browser-session source sync orchestration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aoa_course_connector.adapters.browser import build_crawled_snapshot
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index
from aoa_course_connector.ingest import crawl_browser_live
from aoa_course_connector.ingest.browser_session import FIXTURES
from aoa_course_connector.normalize import write_normalized_bundle
from aoa_course_connector.normalize.browser_session import normalize_browser_snapshot
from aoa_course_connector.sources import load_registry
from aoa_course_connector.storage import create_storage_roots, run_data_dir, sync_data_dir
from aoa_course_connector.sync.checkpoints import load_sync_status, make_checkpoint, upsert_checkpoint


def sync_browser_fixture_sources(
    roots: StorageRoots,
    *,
    sync_run_id: str = "browser-sync-fixture",
    platforms: list[str] | None = None,
    source_ids: list[str] | None = None,
    max_lessons: int = 20,
    link_pattern: str | None = None,
    source_limit: int | None = None,
    build_artifacts: bool = False,
) -> dict[str, object]:
    create_storage_roots(roots)
    sources = _selected_sources(roots, platforms=platforms, source_ids=source_ids, source_limit=source_limit)
    receipt = _base_receipt(sync_run_id, "browser_fixture_sync", sources, network_touched=False)
    for source in sources:
        child_run = _child_run_id(sync_run_id, source)
        try:
            materialized = _materialize_source_fixture(
                roots,
                source=source,
                run_id=child_run,
                max_lessons=max_lessons,
                link_pattern=link_pattern,
            )
            checkpoint = _checkpoint_from_materialized(roots, source, sync_run_id, child_run, materialized, build_artifacts=build_artifacts)
            receipt["synced_sources"].append(checkpoint)
        except Exception as exc:  # pragma: no cover - defensive sync accounting
            checkpoint = make_checkpoint(source=source, sync_run_id=sync_run_id, run_id=child_run, status="error", error=str(exc))
            upsert_checkpoint(roots, checkpoint)
            receipt["failed_sources"].append(checkpoint)
    return _finish_receipt(roots, receipt)


def sync_browser_live_sources(
    roots: StorageRoots,
    *,
    sync_run_id: str = "browser-live-sync",
    platforms: list[str] | None = None,
    source_ids: list[str] | None = None,
    state_file: Path | None = None,
    wait_until: str = "networkidle",
    max_lessons: int = 20,
    link_pattern: str | None = None,
    source_limit: int | None = None,
    build_artifacts: bool = False,
) -> dict[str, object]:
    create_storage_roots(roots)
    sources = _selected_sources(roots, platforms=platforms, source_ids=source_ids, source_limit=source_limit)
    receipt = _base_receipt(sync_run_id, "browser_live_sync", sources, network_touched=True)
    for source in sources:
        child_run = _child_run_id(sync_run_id, source)
        try:
            materialized = crawl_browser_live(
                roots,
                url=str(source.get("source_ref") or ""),
                platform=str(source.get("platform") or ""),
                run_id=child_run,
                state_file=state_file,
                wait_until=wait_until,
                max_lessons=max_lessons,
                link_pattern=link_pattern,
            )
            checkpoint = _checkpoint_from_materialized(roots, source, sync_run_id, child_run, materialized, build_artifacts=build_artifacts)
            receipt["synced_sources"].append(checkpoint)
        except Exception as exc:  # pragma: no cover - live route is externally variable
            checkpoint = make_checkpoint(source=source, sync_run_id=sync_run_id, run_id=child_run, status="error", error=str(exc))
            upsert_checkpoint(roots, checkpoint)
            receipt["failed_sources"].append(checkpoint)
    return _finish_receipt(roots, receipt)


def _selected_sources(roots: StorageRoots, *, platforms: list[str] | None, source_ids: list[str] | None, source_limit: int | None) -> list[dict[str, Any]]:
    registry = load_registry(roots.data)
    wanted = set(platforms or ["getcourse", "skillspace"])
    wanted_ids = {str(source_id) for source_id in source_ids or []}
    sources = [
        source
        for source in registry.get("sources", [])
        if isinstance(source, dict)
        and source.get("enabled", True)
        and source.get("platform") in wanted
        and source.get("access_mode") == "browser_session"
        and (not wanted_ids or str(source.get("source_id") or "") in wanted_ids)
    ]
    sources = sorted(sources, key=lambda item: str(item.get("source_id") or item.get("source_ref") or ""))
    return sources[:source_limit] if source_limit is not None else sources


def _materialize_source_fixture(
    roots: StorageRoots,
    *,
    source: dict[str, Any],
    run_id: str,
    max_lessons: int,
    link_pattern: str | None,
) -> dict[str, object]:
    platform = str(source.get("platform") or "").casefold()
    if platform not in FIXTURES:
        raise ValueError(f"unsupported browser fixture sync platform: {platform}")
    fixture_path = find_repo_root() / FIXTURES[platform]
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    raw["platform"] = platform
    raw["course_title"] = source.get("title") or raw.get("course_title") or source.get("source_ref")
    raw["source"] = {
        "source_id": source.get("source_id"),
        "platform": platform,
        "source_ref": source.get("source_ref"),
        "access_mode": "browser_session",
        "title": source.get("title") or source.get("source_ref"),
    }
    for page in raw.get("pages", []):
        if isinstance(page, dict) and str(page.get("kind") or "").casefold() == "course_index":
            page["url"] = source.get("source_ref") or page.get("url")
            page["title"] = source.get("title") or page.get("title")
            break
    crawled = build_crawled_snapshot(raw, platform=platform, max_lessons=max_lessons, link_pattern=link_pattern)
    data_dir = run_data_dir(roots, run_id)
    raw_dir = data_dir / "raw"
    normalized_dir = data_dir / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{platform}_source_sync_fixture.json"
    raw_path.write_text(json.dumps(crawled, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    bundle = normalize_browser_snapshot(crawled, run_id=run_id, raw_ref=str(raw_path))
    normalized_path = write_normalized_bundle(bundle, normalized_dir)
    receipt = {
        "schema": "aoa_course_browser_materialize_receipt_v1",
        "status": "ok",
        "run_id": run_id,
        "source_mode": f"{platform}_browser_source_sync_fixture",
        "raw_path": str(raw_path),
        "normalized_path": str(normalized_path),
        "course_count": len(bundle.get("courses", [])),
        "evidence_count": len(bundle.get("evidence", [])),
        "completed_at": _now(),
        "network_touched": False,
    }
    if isinstance(crawled.get("crawl"), dict):
        receipt["crawl"] = crawled["crawl"]
    receipt_path = data_dir / "browser_materialize_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


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
    graph_path = ""
    if build_artifacts:
        index_path = str(build_keyword_index(roots, run_id=child_run))
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
        graph_path=graph_path,
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


def _finish_receipt(roots: StorageRoots, receipt: dict[str, object]) -> dict[str, object]:
    synced = receipt.get("synced_sources") if isinstance(receipt.get("synced_sources"), list) else []
    failed = receipt.get("failed_sources") if isinstance(receipt.get("failed_sources"), list) else []
    receipt["synced_count"] = len(synced)
    receipt["failed_count"] = len(failed)
    receipt["completed_at"] = _now()
    if int(receipt.get("source_count") or 0) == 0:
        receipt["status"] = "error"
        receipt["error"] = "no enabled browser_session sources matched this sync"
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
