"""Sync checkpoint storage."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aoa_course_connector.config import StorageRoots

IDENTITY_SCHEMA = "aoa_course_stable_identity_summary_v1"
IDENTITY_SAMPLE_LIMIT = 8
IDENTITY_BUCKETS = [
    "source_ids",
    "course_ids",
    "module_ids",
    "lesson_ids",
    "step_ids",
    "asset_ids",
    "transcript_ids",
    "assignment_ids",
    "thread_ids",
    "comment_ids",
    "evidence_ids",
]


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
    if checkpoint.get("status") == "ok" and checkpoint.get("normalized_path"):
        checkpoint["identity_continuity"] = _identity_continuity(checkpoints, checkpoint)
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
    semantic_index_path: str = "",
    graph_path: str = "",
    error: str = "",
    stable_identity: dict[str, object] | None = None,
    coverage: dict[str, object] | None = None,
) -> dict[str, object]:
    source_id = str(source.get("source_id") or "")
    checkpoint = {
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
        "semantic_index_path": semantic_index_path,
        "graph_path": graph_path,
        "error": error,
        "updated_at": _now(),
    }
    if stable_identity is not None:
        checkpoint["stable_identity"] = stable_identity
    if coverage is not None:
        checkpoint["coverage"] = coverage
    return checkpoint


def normalized_identity_summary(normalized_path: str | Path) -> dict[str, object]:
    path_text = str(normalized_path or "")
    if not path_text:
        return _identity_unavailable("missing_normalized_path")
    path = Path(path_text)
    if not path.is_file():
        return _identity_unavailable("normalized_path_missing")
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive status packet
        return _identity_unavailable("normalized_path_unreadable", error=str(exc))
    buckets = _identity_buckets(bundle)
    canonical = {bucket: sorted(values) for bucket, values in buckets.items()}
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "schema": IDENTITY_SCHEMA,
        "available": True,
        "fingerprint": f"sha256:{digest}",
        "counts": {bucket: len(values) for bucket, values in canonical.items()},
        "samples": {bucket: values[:IDENTITY_SAMPLE_LIMIT] for bucket, values in canonical.items() if values},
    }


def _identity_buckets(bundle: object) -> dict[str, set[str]]:
    buckets: dict[str, set[str]] = {name: set() for name in IDENTITY_BUCKETS}
    source = bundle.get("source") if isinstance(bundle, dict) and isinstance(bundle.get("source"), dict) else {}
    _add_id(buckets, "source_ids", source.get("source_id"))
    courses = bundle.get("courses") if isinstance(bundle, dict) and isinstance(bundle.get("courses"), list) else []
    for course in courses:
        if not isinstance(course, dict):
            continue
        _add_id(buckets, "course_ids", course.get("course_id"))
        modules = course.get("modules") if isinstance(course.get("modules"), list) else []
        for module in modules:
            if not isinstance(module, dict):
                continue
            _add_id(buckets, "module_ids", module.get("module_id"))
            lessons = module.get("lessons") if isinstance(module.get("lessons"), list) else []
            for lesson in lessons:
                if not isinstance(lesson, dict):
                    continue
                _add_lesson_ids(buckets, lesson)
    evidence = bundle.get("evidence") if isinstance(bundle, dict) and isinstance(bundle.get("evidence"), list) else []
    for item in evidence:
        if isinstance(item, dict):
            _add_id(buckets, "evidence_ids", item.get("evidence_id"))
    return buckets


def _identity_continuity(checkpoints: list[dict[str, object]], checkpoint: dict[str, object]) -> dict[str, object]:
    current_buckets = _identity_buckets_from_path(str(checkpoint.get("normalized_path") or ""))
    current_ids = _stable_ids(current_buckets)
    previous_candidates = [
        item
        for item in checkpoints
        if item.get("status") == "ok"
        and str(item.get("source_id") or "") == str(checkpoint.get("source_id") or "")
        and str(item.get("checkpoint_id") or "") != str(checkpoint.get("checkpoint_id") or "")
        and item.get("normalized_path")
    ]
    previous = sorted(previous_candidates, key=lambda item: (str(item.get("updated_at") or ""), str(item.get("checkpoint_id") or "")))[-1] if previous_candidates else None
    if previous is None:
        return {
            "schema": "aoa_course_identity_continuity_v1",
            "status": "initial",
            "previous_run_id": "",
            "stable_retention_rate": 1.0,
            "previous_id_count": 0,
            "current_id_count": len(current_ids),
            "retained_id_count": 0,
            "added_id_count": len(current_ids),
            "removed_id_count": 0,
            "history_preserved": True,
            "removal_assessment": "none",
            "bucket_deltas": {},
        }
    previous_buckets = _identity_buckets_from_path(str(previous.get("normalized_path") or ""))
    previous_ids = _stable_ids(previous_buckets)
    retained = current_ids & previous_ids
    added = current_ids - previous_ids
    removed = previous_ids - current_ids
    current_coverage = checkpoint.get("coverage") if isinstance(checkpoint.get("coverage"), dict) else {}
    complete_current = bool(current_coverage.get("complete_for_scope"))
    bucket_deltas = {
        bucket: {
            "previous_count": len(previous_buckets.get(bucket, set())),
            "current_count": len(current_buckets.get(bucket, set())),
            "added_count": len(current_buckets.get(bucket, set()) - previous_buckets.get(bucket, set())),
            "removed_count": len(previous_buckets.get(bucket, set()) - current_buckets.get(bucket, set())),
        }
        for bucket in IDENTITY_BUCKETS
        if bucket != "evidence_ids"
        and previous_buckets.get(bucket, set()) != current_buckets.get(bucket, set())
    }
    return {
        "schema": "aoa_course_identity_continuity_v1",
        "status": "stable" if not added and not removed else "changed",
        "previous_checkpoint_id": previous.get("checkpoint_id"),
        "previous_run_id": previous.get("run_id"),
        "previous_updated_at": previous.get("updated_at"),
        "stable_retention_rate": round(len(retained) / len(previous_ids), 6) if previous_ids else 1.0,
        "previous_id_count": len(previous_ids),
        "current_id_count": len(current_ids),
        "retained_id_count": len(retained),
        "added_id_count": len(added),
        "removed_id_count": len(removed),
        "history_preserved": Path(str(previous.get("normalized_path") or "")).is_file(),
        "removal_assessment": "none" if not removed else "observed_complete_ingest" if complete_current else "inconclusive_incomplete_ingest",
        "bucket_deltas": bucket_deltas,
    }


def _identity_buckets_from_path(path_text: str) -> dict[str, set[str]]:
    path = Path(path_text)
    if not path.is_file():
        return {name: set() for name in IDENTITY_BUCKETS}
    try:
        return _identity_buckets(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return {name: set() for name in IDENTITY_BUCKETS}


def _stable_ids(buckets: dict[str, set[str]]) -> set[str]:
    return {
        f"{bucket}:{item_id}"
        for bucket, values in buckets.items()
        if bucket != "evidence_ids"
        for item_id in values
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


def _add_lesson_ids(buckets: dict[str, set[str]], lesson: dict[str, object]) -> None:
    _add_id(buckets, "lesson_ids", lesson.get("lesson_id"))
    for item in lesson.get("steps") if isinstance(lesson.get("steps"), list) else []:
        if isinstance(item, dict):
            _add_id(buckets, "step_ids", item.get("step_id"))
    for item in lesson.get("assets") if isinstance(lesson.get("assets"), list) else []:
        if isinstance(item, dict):
            _add_id(buckets, "asset_ids", item.get("asset_id"))
    for item in lesson.get("transcripts") if isinstance(lesson.get("transcripts"), list) else []:
        if isinstance(item, dict):
            _add_id(buckets, "transcript_ids", item.get("transcript_id"))
    for item in lesson.get("assignments") if isinstance(lesson.get("assignments"), list) else []:
        if isinstance(item, dict):
            _add_id(buckets, "assignment_ids", item.get("assignment_id"))
    for thread in lesson.get("comment_threads") if isinstance(lesson.get("comment_threads"), list) else []:
        if not isinstance(thread, dict):
            continue
        _add_id(buckets, "thread_ids", thread.get("thread_id"))
        for comment in thread.get("comments") if isinstance(thread.get("comments"), list) else []:
            if isinstance(comment, dict):
                _add_id(buckets, "comment_ids", comment.get("comment_id"))


def _add_id(buckets: dict[str, set[str]], bucket: str, value: object) -> None:
    text = str(value or "").strip()
    if text:
        buckets[bucket].add(text)


def _identity_unavailable(reason: str, *, error: str = "") -> dict[str, object]:
    packet: dict[str, object] = {
        "schema": IDENTITY_SCHEMA,
        "available": False,
        "reason": reason,
        "fingerprint": "",
        "counts": {},
        "samples": {},
    }
    if error:
        packet["error"] = error
    return packet


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
