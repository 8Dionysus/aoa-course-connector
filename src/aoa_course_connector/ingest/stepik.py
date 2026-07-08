"""Stepik materialization routes."""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aoa_course_connector.auth import browser_state_cookie_header
from aoa_course_connector.adapters.stepik import fetch_stepik_course
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.ingest.counts import bundle_content_counts
from aoa_course_connector.normalize.stepik import normalize_stepik_raw
from aoa_course_connector.normalize import write_normalized_bundle
from aoa_course_connector.storage import create_storage_roots, run_data_dir


DEFAULT_STEPIK_FIXTURE = Path("connector/fixtures/stepik/starter_stepik_course.json")


def materialize_stepik_fixture(
    roots: StorageRoots,
    run_id: str = "stepik-fixture",
    fixture: Path | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, object]:
    repo_root = find_repo_root()
    create_storage_roots(roots)
    fixture_path = fixture or repo_root / DEFAULT_STEPIK_FIXTURE
    data_dir = run_data_dir(roots, run_id)
    raw_dir = data_dir / "raw"
    normalized_dir = data_dir / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_copy = raw_dir / fixture_path.name
    shutil.copyfile(fixture_path, raw_copy)
    raw = json.loads(raw_copy.read_text(encoding="utf-8"))
    if source:
        raw["source"] = _source_payload(source)
        raw_copy.write_text(json.dumps(raw, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    bundle = normalize_stepik_raw(raw, run_id=run_id, raw_ref=str(raw_copy))
    normalized_path = write_normalized_bundle(bundle, normalized_dir)
    return _write_receipt(data_dir, run_id, "stepik_fixture", raw_copy, normalized_path, bundle, network_touched=False)


def materialize_stepik_live(
    roots: StorageRoots,
    *,
    course_id: int,
    run_id: str,
    token_env: str = "STEPIK_API_TOKEN",
    state_file: Path | None = None,
    max_sections: int | None = 1,
    max_units_per_section: int | None = 2,
    max_steps_per_lesson: int | None = 5,
    batch_size: int = 20,
    include_step_sources: bool = False,
    max_step_sources: int | None = 10,
    step_source_timeout: float = 5.0,
    source: dict[str, Any] | None = None,
) -> dict[str, object]:
    create_storage_roots(roots)
    data_dir = run_data_dir(roots, run_id)
    raw_dir = data_dir / "raw"
    normalized_dir = data_dir / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    token = os.environ.get(token_env)
    cookie_header = browser_state_cookie_header(state_file, "stepik.org") if state_file else None
    raw = fetch_stepik_course(
        course_id,
        token=token,
        cookie_header=cookie_header,
        max_sections=max_sections,
        max_units_per_section=max_units_per_section,
        max_steps_per_lesson=max_steps_per_lesson,
        batch_size=batch_size,
        include_step_sources=include_step_sources,
        max_step_sources=max_step_sources,
        step_source_timeout=step_source_timeout,
    )
    if source:
        raw["source"] = _source_payload(source)
    raw_path = raw_dir / f"stepik_course_{course_id}.json"
    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    bundle = normalize_stepik_raw(raw, run_id=run_id, raw_ref=str(raw_path))
    normalized_path = write_normalized_bundle(bundle, normalized_dir)
    return _write_receipt(data_dir, run_id, "stepik_live", raw_path, normalized_path, bundle, network_touched=True)


def _source_payload(source: dict[str, Any]) -> dict[str, object]:
    return {
        "source_id": source.get("source_id"),
        "platform": "stepik",
        "source_ref": source.get("source_ref"),
        "access_mode": source.get("access_mode"),
        "title": source.get("title") or source.get("source_ref"),
    }


def _write_receipt(data_dir: Path, run_id: str, source_mode: str, raw_path: Path, normalized_path: Path, bundle: dict[str, object], *, network_touched: bool) -> dict[str, object]:
    counts = bundle_content_counts(bundle)
    receipt = {
        "schema": "aoa_course_stepik_materialize_receipt_v1",
        "status": "ok",
        "run_id": run_id,
        "source_mode": source_mode,
        "raw_path": str(raw_path),
        "normalized_path": str(normalized_path),
        **counts,
        "content_counts": counts,
        "completed_at": _now(),
        "network_touched": network_touched,
    }
    receipt_path = data_dir / "stepik_materialize_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
