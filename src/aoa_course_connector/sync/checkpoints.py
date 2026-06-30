"""Sync checkpoint storage."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aoa_course_connector.config import StorageRoots


def checkpoint_store_path(roots: StorageRoots) -> Path:
    return roots.data / "sync" / "sync_checkpoints.json"


def load_checkpoint_store(roots: StorageRoots) -> dict[str, object]:
    path = checkpoint_store_path(roots)
    if not path.exists():
        return {"schema": "aoa_course_sync_checkpoint_store_v1", "updated_at": "", "checkpoints": []}
    return json.loads(path.read_text(encoding="utf-8"))


def upsert_checkpoint(roots: StorageRoots, checkpoint: dict[str, object]) -> dict[str, object]:
    data = load_checkpoint_store(roots)
    checkpoints = [item for item in data.get("checkpoints", []) if isinstance(item, dict)]
    checkpoint_id = str(checkpoint["checkpoint_id"])
    checkpoint_sync_run_id = str(checkpoint.get("sync_run_id") or "")
    checkpoint_source_id = str(checkpoint.get("source_id") or "")
    for index, existing in enumerate(checkpoints):
        existing_matches_checkpoint = existing.get("checkpoint_id") == checkpoint_id
        existing_matches_run_source = (
            str(existing.get("sync_run_id") or "") == checkpoint_sync_run_id
            and str(existing.get("source_id") or "") == checkpoint_source_id
        )
        if existing_matches_checkpoint or existing_matches_run_source:
            checkpoints[index] = {**existing, **checkpoint}
            break
    else:
        checkpoints.append(checkpoint)
    updated = {
        "schema": "aoa_course_sync_checkpoint_store_v1",
        "updated_at": _now(),
        "checkpoints": sorted(checkpoints, key=lambda item: str(item.get("checkpoint_id"))),
    }
    path = checkpoint_store_path(roots)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(updated, indent=2, sort_keys=True), encoding="utf-8")
    return updated


def make_checkpoint(
    *,
    source: dict[str, Any],
    sync_run_id: str,
    run_id: str,
    status: str,
    cursor: str = "",
    receipt_path: str = "",
    normalized_path: str = "",
    index_path: str = "",
    graph_path: str = "",
    error: str = "",
) -> dict[str, object]:
    source_id = str(source.get("source_id") or "")
    return {
        "schema": "aoa_course_sync_checkpoint_v1",
        "checkpoint_id": f"checkpoint:{sync_run_id}:{source_id}",
        "source_id": source_id,
        "platform": str(source.get("platform") or ""),
        "source_ref": str(source.get("source_ref") or ""),
        "title": str(source.get("title") or source.get("source_ref") or ""),
        "access_mode": str(source.get("access_mode") or ""),
        "sync_run_id": sync_run_id,
        "run_id": run_id,
        "status": status,
        "cursor": cursor,
        "receipt_path": receipt_path,
        "normalized_path": normalized_path,
        "index_path": index_path,
        "graph_path": graph_path,
        "error": error,
        "updated_at": _now(),
    }


def load_sync_status(roots: StorageRoots, *, sync_run_id: str | None = None, platform: str | None = None) -> dict[str, object]:
    store = load_checkpoint_store(roots)
    checkpoints = [item for item in store.get("checkpoints", []) if isinstance(item, dict)]
    if sync_run_id:
        checkpoints = [item for item in checkpoints if item.get("sync_run_id") == sync_run_id]
    if platform:
        checkpoints = [item for item in checkpoints if item.get("platform") == platform]
    return {
        "schema": "aoa_course_sync_status_v1",
        "checkpoint_store_path": str(checkpoint_store_path(roots)),
        "sync_run_id": sync_run_id or "",
        "platform": platform or "",
        "checkpoint_count": len(checkpoints),
        "ok_count": sum(1 for item in checkpoints if item.get("status") == "ok"),
        "error_count": sum(1 for item in checkpoints if item.get("status") == "error"),
        "checkpoints": checkpoints,
    }


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
