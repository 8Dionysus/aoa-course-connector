"""Offline fixture ingestion."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.normalize import normalize_fixture, write_normalized_bundle
from aoa_course_connector.storage import create_storage_roots, run_data_dir


DEFAULT_FIXTURE = Path("connector/fixtures/course/starter_course.json")


def materialize_fixture(roots: StorageRoots, run_id: str = "starter-fixture", fixture: Path | None = None) -> dict[str, object]:
    repo_root = find_repo_root()
    create_storage_roots(roots)
    fixture_path = fixture or repo_root / DEFAULT_FIXTURE
    data_dir = run_data_dir(roots, run_id)
    raw_dir = data_dir / "raw"
    normalized_dir = data_dir / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_copy = raw_dir / fixture_path.name
    shutil.copyfile(fixture_path, raw_copy)
    bundle = normalize_fixture(raw_copy, run_id=run_id, raw_ref=str(raw_copy))
    normalized_path = write_normalized_bundle(bundle, normalized_dir)
    receipt = {
        "schema": "aoa_course_materialize_receipt_v1",
        "status": "ok",
        "run_id": run_id,
        "source": str(fixture_path),
        "raw_path": str(raw_copy),
        "normalized_path": str(normalized_path),
        "course_count": len(bundle.get("courses", [])),
        "evidence_count": len(bundle.get("evidence", [])),
        "completed_at": _now(),
        "network_touched": False,
    }
    receipt_path = data_dir / "materialize_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
