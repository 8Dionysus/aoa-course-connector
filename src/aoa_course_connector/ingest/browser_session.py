"""Browser-session materialization routes for hard adapters."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.normalize import write_normalized_bundle
from aoa_course_connector.normalize.browser_session import normalize_browser_snapshot
from aoa_course_connector.storage import create_storage_roots, run_data_dir


FIXTURES = {
    "getcourse": Path("connector/fixtures/browser/getcourse_starter_snapshot.json"),
    "skillspace": Path("connector/fixtures/browser/skillspace_starter_snapshot.json"),
}


def materialize_browser_fixture(roots: StorageRoots, platform: str, run_id: str | None = None, fixture: Path | None = None) -> dict[str, object]:
    platform = platform.casefold()
    if platform not in FIXTURES and fixture is None:
        raise ValueError(f"unsupported browser fixture platform: {platform}")
    repo_root = find_repo_root()
    create_storage_roots(roots)
    fixture_path = fixture or repo_root / FIXTURES[platform]
    resolved_run = run_id or f"{platform}-browser-fixture"
    data_dir = run_data_dir(roots, resolved_run)
    raw_dir = data_dir / "raw"
    normalized_dir = data_dir / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_copy = raw_dir / fixture_path.name
    shutil.copyfile(fixture_path, raw_copy)
    raw = json.loads(raw_copy.read_text(encoding="utf-8"))
    bundle = normalize_browser_snapshot(raw, run_id=resolved_run, raw_ref=str(raw_copy))
    normalized_path = write_normalized_bundle(bundle, normalized_dir)
    return _write_receipt(data_dir, resolved_run, f"{platform}_browser_fixture", raw_copy, normalized_path, bundle, network_touched=False)


def materialize_browser_snapshot(roots: StorageRoots, snapshot_path: Path, platform: str | None = None, run_id: str | None = None) -> dict[str, object]:
    create_storage_roots(roots)
    raw_input = snapshot_path.resolve()
    raw = json.loads(raw_input.read_text(encoding="utf-8"))
    if platform:
        raw["platform"] = platform
        raw.setdefault("source", {})["platform"] = platform
    resolved_platform = str(raw.get("platform") or raw.get("source", {}).get("platform") or "browser")
    resolved_run = run_id or f"{resolved_platform}-browser-snapshot"
    data_dir = run_data_dir(roots, resolved_run)
    raw_dir = data_dir / "raw"
    normalized_dir = data_dir / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_copy = raw_dir / raw_input.name
    shutil.copyfile(raw_input, raw_copy)
    bundle = normalize_browser_snapshot(raw, run_id=resolved_run, raw_ref=str(raw_copy))
    normalized_path = write_normalized_bundle(bundle, normalized_dir)
    return _write_receipt(data_dir, resolved_run, f"{resolved_platform}_browser_snapshot", raw_copy, normalized_path, bundle, network_touched=False)


def capture_browser_live(roots: StorageRoots, url: str, platform: str, run_id: str, state_file: Path | None = None, wait_until: str = "networkidle") -> dict[str, object]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError("Install the browser extra first: python -m pip install -e '.[browser]'") from exc
    create_storage_roots(roots)
    data_dir = run_data_dir(roots, run_id)
    raw_dir = data_dir / "raw"
    normalized_dir = data_dir / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context_kwargs = {}
        if state_file:
            context_kwargs["storage_state"] = str(state_file)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        page.goto(url, wait_until=wait_until)
        html = page.content()
        title = page.title()
        current_url = page.url
        browser.close()
    captured_at = _now()
    raw = {
        "schema": "aoa_course_browser_snapshot_v1",
        "platform": platform,
        "captured_at": captured_at,
        "source": {
            "source_id": f"source:{platform}:browser-live",
            "platform": platform,
            "source_ref": url,
            "access_mode": "browser_session",
            "title": title or url,
        },
        "pages": [{"page_id": "live-page", "kind": "lesson", "url": current_url, "title": title, "html": html}],
    }
    raw_path = raw_dir / f"{platform}_browser_live_snapshot.json"
    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    bundle = normalize_browser_snapshot(raw, run_id=run_id, raw_ref=str(raw_path))
    normalized_path = write_normalized_bundle(bundle, normalized_dir)
    return _write_receipt(data_dir, run_id, f"{platform}_browser_live", raw_path, normalized_path, bundle, network_touched=True)


def _write_receipt(data_dir: Path, run_id: str, source_mode: str, raw_path: Path, normalized_path: Path, bundle: dict[str, object], *, network_touched: bool) -> dict[str, object]:
    receipt = {
        "schema": "aoa_course_browser_materialize_receipt_v1",
        "status": "ok",
        "run_id": run_id,
        "source_mode": source_mode,
        "raw_path": str(raw_path),
        "normalized_path": str(normalized_path),
        "course_count": len(bundle.get("courses", [])),
        "evidence_count": len(bundle.get("evidence", [])),
        "completed_at": _now(),
        "network_touched": network_touched,
    }
    receipt_path = data_dir / "browser_materialize_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
