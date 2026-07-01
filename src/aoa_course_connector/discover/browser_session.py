"""Browser-session source discovery routes."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aoa_course_connector.adapters.browser import build_browser_catalog_discovery
from aoa_course_connector.adapters.browser.snapshot import parse_html_snapshot
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.sources import upsert_source
from aoa_course_connector.storage import create_storage_roots, discovery_data_dir


CATALOG_FIXTURES = {
    "getcourse": Path("connector/fixtures/browser/getcourse_catalog_snapshot.json"),
    "skillspace": Path("connector/fixtures/browser/skillspace_catalog_snapshot.json"),
}


def discover_browser_fixture(
    roots: StorageRoots,
    platform: str,
    *,
    run_id: str | None = None,
    fixture: Path | None = None,
    max_sources: int = 50,
    link_pattern: str | None = None,
    register: bool = False,
) -> dict[str, object]:
    platform = platform.casefold()
    if platform not in CATALOG_FIXTURES and fixture is None:
        raise ValueError(f"unsupported browser catalog fixture platform: {platform}")
    repo_root = find_repo_root()
    fixture_path = fixture or repo_root / CATALOG_FIXTURES[platform]
    resolved_run = run_id or f"{platform}-browser-discovery-fixture"
    data_dir = discovery_data_dir(roots, resolved_run)
    raw_dir = data_dir / "raw"
    create_storage_roots(roots)
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_copy = raw_dir / fixture_path.name
    shutil.copyfile(fixture_path, raw_copy)
    raw = json.loads(raw_copy.read_text(encoding="utf-8"))
    return _receipt_from_raw(
        roots,
        run_id=resolved_run,
        platform=platform,
        source_mode=f"{platform}_browser_discovery_fixture",
        raw=raw,
        raw_path=raw_copy,
        max_sources=max_sources,
        link_pattern=link_pattern,
        register=register,
        network_touched=False,
    )


def discover_browser_snapshot(
    roots: StorageRoots,
    snapshot_path: Path,
    *,
    platform: str | None = None,
    run_id: str | None = None,
    max_sources: int = 50,
    link_pattern: str | None = None,
    register: bool = False,
) -> dict[str, object]:
    create_storage_roots(roots)
    raw_input = snapshot_path.resolve()
    raw = json.loads(raw_input.read_text(encoding="utf-8"))
    if platform:
        raw["platform"] = platform
        raw.setdefault("source", {})["platform"] = platform
    resolved_platform = str(raw.get("platform") or raw.get("source", {}).get("platform") or "browser")
    resolved_run = run_id or f"{resolved_platform}-browser-discovery-snapshot"
    data_dir = discovery_data_dir(roots, resolved_run)
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_copy = raw_dir / raw_input.name
    shutil.copyfile(raw_input, raw_copy)
    return _receipt_from_raw(
        roots,
        run_id=resolved_run,
        platform=resolved_platform,
        source_mode=f"{resolved_platform}_browser_discovery_snapshot",
        raw=raw,
        raw_path=raw_copy,
        max_sources=max_sources,
        link_pattern=link_pattern,
        register=register,
        network_touched=False,
    )


def discover_browser_live(
    roots: StorageRoots,
    url: str,
    platform: str,
    *,
    run_id: str,
    state_file: Path | None = None,
    wait_until: str = "networkidle",
    max_sources: int = 50,
    max_pages: int = 5,
    link_pattern: str | None = None,
    register: bool = False,
) -> dict[str, object]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError("Install the browser extra first: python -m pip install -e '.[browser]'") from exc
    create_storage_roots(roots)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context_kwargs = {}
        if state_file:
            context_kwargs["storage_state"] = str(state_file)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        pages = collect_live_catalog_pages(page, url, wait_until=wait_until, max_pages=max_pages)
        title = str(pages[0].get("title") or url) if pages else url
        raw = {
            "schema": "aoa_course_browser_snapshot_v1",
            "platform": platform,
            "captured_at": _now(),
            "source": {
                "source_id": f"source:{platform}:browser-live-discovery",
                "platform": platform,
                "source_ref": url,
                "access_mode": "browser_session",
                "title": title,
            },
            "pages": pages,
        }
        browser.close()
    data_dir = discovery_data_dir(roots, run_id)
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{platform}_browser_live_discovery.json"
    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    return _receipt_from_raw(
        roots,
        run_id=run_id,
        platform=platform,
        source_mode=f"{platform}_browser_live_discovery",
        raw=raw,
        raw_path=raw_path,
        max_sources=max_sources,
        link_pattern=link_pattern,
        register=register,
        network_touched=True,
    )


def collect_live_catalog_pages(page: Any, start_url: str, *, wait_until: str = "networkidle", max_pages: int = 5) -> list[dict[str, object]]:
    pages: list[dict[str, object]] = []
    seen: set[str] = set()
    next_url = start_url
    page_limit = max(1, max_pages)
    for index in range(1, page_limit + 1):
        page.goto(next_url, wait_until=wait_until)
        current_url = str(getattr(page, "url", "") or next_url)
        if current_url in seen:
            break
        seen.add(current_url)
        html = str(page.content())
        title = str(page.title() or current_url)
        pages.append(
            {
                "page_id": f"account-catalog-page-{index}",
                "kind": "account_catalog",
                "url": current_url,
                "title": title,
                "html": html,
            }
        )
        candidate = _first_unseen_pagination_url(html, current_url, seen)
        if not candidate:
            break
        next_url = candidate
    return pages


def _first_unseen_pagination_url(html: str, current_url: str, seen: set[str]) -> str | None:
    snapshot = parse_html_snapshot(html, current_url)
    for link in snapshot.pagination_links:
        href = str(link.get("href") or "")
        if href and href not in seen:
            return href
    return None


def _receipt_from_raw(
    roots: StorageRoots,
    *,
    run_id: str,
    platform: str,
    source_mode: str,
    raw: dict[str, object],
    raw_path: Path,
    max_sources: int,
    link_pattern: str | None,
    register: bool,
    network_touched: bool,
) -> dict[str, object]:
    discovery = build_browser_catalog_discovery(raw, platform=platform, max_sources=max_sources, link_pattern=link_pattern)
    registered = _register_sources(roots, discovery["courses"]) if register else []
    receipt = {
        "schema": "aoa_course_browser_discovery_receipt_v1",
        "status": "ok",
        "run_id": run_id,
        "platform": platform,
        "source_mode": source_mode,
        "raw_path": str(raw_path),
        "page_count": discovery.get("page_count", 0),
        "pagination": discovery.get("pagination", {}),
        "course_count": discovery["course_count"],
        "courses": discovery["courses"],
        "registered_sources": registered,
        "completed_at": _now(),
        "network_touched": network_touched,
    }
    data_dir = discovery_data_dir(roots, run_id)
    data_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = data_dir / "browser_discovery_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def _register_sources(roots: StorageRoots, courses: object) -> list[dict[str, object]]:
    registered: list[dict[str, object]] = []
    if not isinstance(courses, list):
        return registered
    for item in courses:
        if not isinstance(item, dict):
            continue
        source, path, state = upsert_source(
            roots.data,
            platform=str(item.get("platform") or ""),
            source_ref=str(item.get("source_ref") or ""),
            title=str(item.get("title") or item.get("source_ref") or ""),
            access_mode=str(item.get("access_mode") or "browser_session"),
            enabled=True,
        )
        registered.append({"state": state, "registry_path": str(path), "source": source})
    return registered


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
