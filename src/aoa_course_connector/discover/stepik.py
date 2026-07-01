"""Stepik discovery routes."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aoa_course_connector.adapters.stepik import fetch_stepik_account_courses
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.sources import registry_path, upsert_source
from aoa_course_connector.storage import create_storage_roots, discovery_data_dir


DEFAULT_STEPIK_ACCOUNT_FIXTURE = Path("connector/fixtures/stepik/account_courses.json")


def discover_stepik_account_fixture(
    roots: StorageRoots,
    *,
    run_id: str = "stepik-account-discovery-fixture",
    fixture: Path | None = None,
    register: bool = False,
    access_mode: str = "api_token",
    source_limit: int | None = None,
) -> dict[str, object]:
    repo_root = find_repo_root()
    fixture_path = fixture or repo_root / DEFAULT_STEPIK_ACCOUNT_FIXTURE
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    return _finish_account_discovery(
        roots,
        raw,
        run_id=run_id,
        source_mode="stepik_account_fixture",
        register=register,
        access_mode=access_mode,
        source_limit=source_limit,
        network_touched=False,
        fixture=str(fixture_path),
    )


def discover_stepik_account_live(
    roots: StorageRoots,
    *,
    run_id: str = "stepik-account-discovery-live",
    token_env: str = "STEPIK_API_TOKEN",
    max_pages: int = 5,
    batch_size: int = 20,
    register: bool = False,
    access_mode: str = "api_token",
    source_limit: int | None = None,
) -> dict[str, object]:
    token = os.environ.get(token_env)
    if not token:
        raise ValueError(f"Stepik account discovery requires token env {token_env}")
    raw = fetch_stepik_account_courses(token=token, max_pages=max_pages, batch_size=batch_size)
    return _finish_account_discovery(
        roots,
        raw,
        run_id=run_id,
        source_mode="stepik_account_live",
        register=register,
        access_mode=access_mode,
        source_limit=source_limit,
        network_touched=True,
        token_env=token_env,
    )


def _finish_account_discovery(
    roots: StorageRoots,
    raw: dict[str, Any],
    *,
    run_id: str,
    source_mode: str,
    register: bool,
    access_mode: str,
    source_limit: int | None,
    network_touched: bool,
    fixture: str | None = None,
    token_env: str | None = None,
) -> dict[str, object]:
    create_storage_roots(roots)
    courses = _course_records(raw, source_limit=source_limit)
    registered_sources = []
    if register:
        for course in courses:
            source, _path, state = upsert_source(
                roots.data,
                platform="stepik",
                source_ref=str(course["source_ref"]),
                title=str(course.get("title") or course["source_ref"]),
                access_mode=access_mode,
            )
            registered_sources.append({"state": state, "source": source})
    receipt: dict[str, object] = {
        "schema": "aoa_course_stepik_account_discovery_receipt_v1",
        "status": "ok",
        "run_id": run_id,
        "source_mode": source_mode,
        "account": _account_summary(raw.get("account")),
        "course_count": len(courses),
        "courses": courses,
        "registered_sources": registered_sources,
        "registry_path": str(registry_path(roots.data)) if register else "",
        "completed_at": _now(),
        "network_touched": network_touched,
        "privacy": {
            "token_env": token_env or "",
            "token_value_logged": False,
            "do_not_commit_account_receipts": True,
        },
    }
    if fixture:
        receipt["fixture"] = fixture
    receipt_path = discovery_data_dir(roots, run_id) / "stepik_account_discovery_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def _course_records(raw: dict[str, Any], *, source_limit: int | None) -> list[dict[str, object]]:
    courses = raw.get("courses") if isinstance(raw.get("courses"), list) else []
    records = []
    for course in courses:
        if not isinstance(course, dict):
            continue
        source_ref = str(course.get("source_ref") or course.get("course_id") or course.get("id") or "")
        if not source_ref:
            continue
        records.append(
            {
                "course_id": course.get("course_id") or course.get("id"),
                "source_ref": source_ref,
                "title": course.get("title") or f"Stepik course {source_ref}",
                "canonical_url": course.get("canonical_url") or f"https://stepik.org/course/{source_ref}",
                "update_date": course.get("update_date") or "",
                "enrollment": course.get("enrollment") if isinstance(course.get("enrollment"), dict) else {},
            }
        )
    records = sorted(records, key=_course_sort_key)
    return records[:source_limit] if source_limit is not None else records


def _course_sort_key(item: dict[str, object]) -> tuple[int, object]:
    source_ref = str(item.get("source_ref") or "")
    return (0, int(source_ref)) if source_ref.isdigit() else (1, source_ref)


def _account_summary(account: object) -> dict[str, object]:
    if not isinstance(account, dict):
        return {}
    return {
        key: account.get(key)
        for key in ["user_id", "profile"]
        if key in account
    }


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
