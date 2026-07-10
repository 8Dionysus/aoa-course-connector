"""Browser-session materialization routes for hard adapters."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aoa_course_connector.adapters.browser import browser_ingest_coverage, build_crawled_snapshot, caption_resource_key, caption_text_from_resource, discover_lesson_link_inventory, is_caption_asset, parse_html_snapshot, placeholder_lesson_page, resource_looks_like_caption
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.ingest.counts import bundle_content_counts
from aoa_course_connector.normalize import write_normalized_bundle
from aoa_course_connector.normalize.browser_session import normalize_browser_snapshot
from aoa_course_connector.storage import create_storage_roots, run_data_dir


FIXTURES = {
    "getcourse": Path("connector/fixtures/browser/getcourse_starter_snapshot.json"),
    "skillspace": Path("connector/fixtures/browser/skillspace_starter_snapshot.json"),
}
CAPTION_RESOURCE_MAX_BYTES = 512_000


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


def crawl_browser_fixture(
    roots: StorageRoots,
    platform: str,
    run_id: str | None = None,
    fixture: Path | None = None,
    max_lessons: int = 20,
    link_pattern: str | None = None,
) -> dict[str, object]:
    platform = platform.casefold()
    if platform not in FIXTURES and fixture is None:
        raise ValueError(f"unsupported browser fixture platform: {platform}")
    repo_root = find_repo_root()
    create_storage_roots(roots)
    fixture_path = fixture or repo_root / FIXTURES[platform]
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    crawled = build_crawled_snapshot(raw, platform=platform, max_lessons=max_lessons, link_pattern=link_pattern)
    resolved_run = run_id or f"{platform}-browser-crawl-fixture"
    return _materialize_browser_raw(
        roots,
        run_id=resolved_run,
        source_mode=f"{platform}_browser_crawl_fixture",
        raw=crawled,
        raw_name=f"{platform}_browser_crawl_fixture.json",
        network_touched=False,
    )


def crawl_browser_snapshot(
    roots: StorageRoots,
    snapshot_path: Path,
    platform: str | None = None,
    run_id: str | None = None,
    max_lessons: int = 20,
    link_pattern: str | None = None,
) -> dict[str, object]:
    create_storage_roots(roots)
    raw_input = snapshot_path.resolve()
    raw = json.loads(raw_input.read_text(encoding="utf-8"))
    if platform:
        raw["platform"] = platform
        raw.setdefault("source", {})["platform"] = platform
    resolved_platform = str(raw.get("platform") or raw.get("source", {}).get("platform") or "browser")
    crawled = build_crawled_snapshot(raw, platform=resolved_platform, max_lessons=max_lessons, link_pattern=link_pattern)
    resolved_run = run_id or f"{resolved_platform}-browser-crawl-snapshot"
    return _materialize_browser_raw(
        roots,
        run_id=resolved_run,
        source_mode=f"{resolved_platform}_browser_crawl_snapshot",
        raw=crawled,
        raw_name=f"{raw_input.stem}_crawl.json",
        network_touched=False,
    )


def capture_browser_live(
    roots: StorageRoots,
    url: str,
    platform: str,
    run_id: str,
    state_file: Path | None = None,
    wait_until: str = "domcontentloaded",
    source: dict[str, Any] | None = None,
) -> dict[str, object]:
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
        caption_resources, caption_resource_errors = _collect_caption_resources(context, html, current_url)
        browser.close()
    captured_at = _now()
    raw = {
        "schema": "aoa_course_browser_snapshot_v1",
        "platform": platform,
        "captured_at": captured_at,
        "source": _browser_source(source, platform=platform, url=url, title=title or url, fallback_suffix="browser-live"),
        "pages": [{"page_id": "live-page", "kind": "lesson", "url": current_url, "title": title, "html": html}],
    }
    if caption_resources:
        raw["resources"] = caption_resources
    if caption_resource_errors:
        raw["caption_resource_errors"] = caption_resource_errors
    raw_path = raw_dir / f"{platform}_browser_live_snapshot.json"
    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    bundle = normalize_browser_snapshot(raw, run_id=run_id, raw_ref=str(raw_path))
    normalized_path = write_normalized_bundle(bundle, normalized_dir)
    return _write_receipt(data_dir, run_id, f"{platform}_browser_live", raw_path, normalized_path, bundle, network_touched=True)


def crawl_browser_live(
    roots: StorageRoots,
    url: str,
    platform: str,
    run_id: str,
    state_file: Path | None = None,
    wait_until: str = "domcontentloaded",
    max_lessons: int = 20,
    link_pattern: str | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, object]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError("Install the browser extra first: python -m pip install -e '.[browser]'") from exc
    create_storage_roots(roots)
    pages: list[dict[str, object]] = []
    caption_resources: list[dict[str, object]] = []
    caption_resource_errors: list[dict[str, object]] = []
    fetch_errors: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context_kwargs = {}
        if state_file:
            context_kwargs["storage_state"] = str(state_file)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        page.goto(url, wait_until=wait_until)
        index_html = page.content()
        index_title = page.title()
        index_url = page.url
        index_caption_resources, index_caption_errors = _collect_caption_resources(context, index_html, index_url)
        _extend_caption_resources(caption_resources, index_caption_resources)
        caption_resource_errors.extend(index_caption_errors)
        pages.append({"page_id": "course-index", "kind": "course_index", "url": index_url, "title": index_title, "html": index_html})
        inventory = discover_lesson_link_inventory(
            index_html,
            index_url,
            platform=platform,
            max_lessons=max_lessons,
            link_pattern=link_pattern,
        )
        links = inventory["links"]
        for order, link in enumerate(links, start=1):
            try:
                page.goto(str(link["href"]), wait_until=wait_until)
                lesson_html = page.content()
                lesson_resources, lesson_resource_errors = _collect_caption_resources(context, lesson_html, page.url)
                _extend_caption_resources(caption_resources, lesson_resources)
                caption_resource_errors.extend(lesson_resource_errors)
                pages.append(
                    {
                        "page_id": f"lesson-{order}",
                        "kind": "lesson",
                        "module_title": link.get("module") or "Browser Session Lessons",
                        "url": page.url,
                        "title": page.title() or link.get("text") or link.get("href"),
                        "order": order,
                        "html": lesson_html,
                    }
                )
            except PlaywrightError as exc:
                fetch_errors.append({"url": link.get("href"), "error": str(exc)})
                placeholder = placeholder_lesson_page(link, order)
                placeholder["freshness_state"] = "fetch_error"
                placeholder["html"] = (
                    f"<article><h1>{placeholder['title']}</h1>"
                    f"<p>Discovered from course index, but live fetch failed during this crawl.</p></article>"
                )
                pages.append(placeholder)
        browser.close()
    captured_at = _now()
    raw = {
        "schema": "aoa_course_browser_snapshot_v1",
        "platform": platform,
        "captured_at": captured_at,
        "source": _browser_source(
            source,
            platform=platform,
            url=url,
            title=str(pages[0].get("title") or url) if pages else url,
            fallback_suffix="browser-live-crawl",
        ),
        "pages": pages,
        "crawl": {
            "schema": "aoa_course_browser_crawl_v1",
            "mode": "course_tree_live",
            "max_lessons": max_lessons,
            "available_lesson_count": int(inventory["available_lesson_count"]),
            "selected_lesson_count": len(links),
            "discovered_lesson_count": len(links),
            "included_lesson_count": max(0, len(pages) - 1),
            "missing_lesson_page_count": len(fetch_errors),
            "truncated_lesson_count": int(inventory["truncated_lesson_count"]),
            "limit_reached": int(inventory["truncated_lesson_count"]) > 0,
            "link_pattern": link_pattern or "",
            "fetch_errors": fetch_errors,
            "caption_resource_count": len(caption_resources),
            "caption_resource_error_count": len(caption_resource_errors),
        },
    }
    raw["coverage"] = browser_ingest_coverage(raw["crawl"], platform=platform)
    if caption_resources:
        raw["resources"] = caption_resources
    if caption_resource_errors:
        raw["caption_resource_errors"] = caption_resource_errors
    return _materialize_browser_raw(
        roots,
        run_id=run_id,
        source_mode=f"{platform}_browser_live_crawl",
        raw=raw,
        raw_name=f"{platform}_browser_live_crawl_snapshot.json",
        network_touched=True,
    )


def _browser_source(source: dict[str, Any] | None, *, platform: str, url: str, title: str, fallback_suffix: str) -> dict[str, object]:
    if source:
        return {
            "source_id": source.get("source_id") or f"source:{platform}:{fallback_suffix}",
            "platform": source.get("platform") or platform,
            "source_ref": source.get("source_ref") or url,
            "access_mode": source.get("access_mode") or "browser_session",
            "title": source.get("title") or title or source.get("source_ref") or url,
        }
    return {
        "source_id": f"source:{platform}:{fallback_suffix}",
        "platform": platform,
        "source_ref": url,
        "access_mode": "browser_session",
        "title": title or url,
    }


def _materialize_browser_raw(
    roots: StorageRoots,
    *,
    run_id: str,
    source_mode: str,
    raw: dict[str, object],
    raw_name: str,
    network_touched: bool,
) -> dict[str, object]:
    create_storage_roots(roots)
    data_dir = run_data_dir(roots, run_id)
    raw_dir = data_dir / "raw"
    normalized_dir = data_dir / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / raw_name
    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    bundle = normalize_browser_snapshot(raw, run_id=run_id, raw_ref=str(raw_path))
    normalized_path = write_normalized_bundle(bundle, normalized_dir)
    return _write_receipt(data_dir, run_id, source_mode, raw_path, normalized_path, bundle, network_touched=network_touched)


def _write_receipt(data_dir: Path, run_id: str, source_mode: str, raw_path: Path, normalized_path: Path, bundle: dict[str, object], *, network_touched: bool) -> dict[str, object]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    counts = bundle_content_counts(bundle)
    receipt = {
        "schema": "aoa_course_browser_materialize_receipt_v1",
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
    if isinstance(raw.get("crawl"), dict):
        receipt["crawl"] = raw["crawl"]
    if isinstance(raw.get("coverage"), dict):
        receipt["coverage"] = raw["coverage"]
    resources = raw.get("resources") if isinstance(raw.get("resources"), list) else []
    caption_errors = raw.get("caption_resource_errors") if isinstance(raw.get("caption_resource_errors"), list) else []
    parse_errors = _caption_resource_parse_errors(resources)
    all_caption_errors = [*caption_errors, *parse_errors]
    receipt["caption_resource_count"] = len(resources)
    receipt["caption_resource_error_count"] = len(all_caption_errors)
    receipt["caption_resource_parse_error_count"] = len(parse_errors)
    receipt["caption_resource_error_reasons"] = sorted(
        {
            str(error.get("reason") or "unknown")
            for error in all_caption_errors
            if isinstance(error, dict)
        }
    )
    receipt_path = data_dir / "browser_materialize_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def _caption_resource_parse_errors(resources: list[object]) -> list[dict[str, object]]:
    errors: list[dict[str, object]] = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        url = str(resource.get("url") or resource.get("source_url") or "")
        content_type = str(resource.get("content_type") or "")
        if not resource_looks_like_caption(url, content_type):
            continue
        if caption_text_from_resource(resource):
            continue
        errors.append(
            {
                "url": url,
                "content_type": content_type,
                "reason": "caption resource parsed without transcript text",
            }
        )
    return errors


def _collect_caption_resources(context: Any, html: str, page_url: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    resources: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    snapshot = parse_html_snapshot(html, page_url)
    for asset in snapshot.assets:
        if not is_caption_asset(asset):
            continue
        url = str(asset.get("url") or "")
        if not url:
            continue
        try:
            response = context.request.get(url, timeout=10_000)
            content_type = str(response.headers.get("content-type", ""))
            if not response.ok:
                errors.append({"url": url, "status": response.status, "reason": "caption resource request failed"})
                continue
            if not resource_looks_like_caption(url, content_type):
                errors.append({"url": url, "content_type": content_type, "reason": "caption resource content type was not text-like"})
                continue
            body = response.body()
        except Exception as exc:  # pragma: no cover - depends on live Playwright/network behavior
            errors.append({"url": url, "reason": "caption resource request raised", "error": str(exc)})
            continue
        if len(body) > CAPTION_RESOURCE_MAX_BYTES:
            errors.append({"url": url, "bytes": len(body), "reason": "caption resource exceeded size limit"})
            continue
        resources.append(
            {
                "url": url,
                "kind": asset.get("kind") or "caption",
                "language": asset.get("language") or "",
                "content_type": content_type,
                "text": body.decode("utf-8", errors="replace"),
            }
        )
    return resources, errors


def _extend_caption_resources(target: list[dict[str, object]], resources: list[dict[str, object]]) -> None:
    seen = {caption_resource_key(str(item.get("url") or "")) for item in target}
    for resource in resources:
        key = caption_resource_key(str(resource.get("url") or ""))
        if key and key not in seen:
            target.append(resource)
            seen.add(key)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
