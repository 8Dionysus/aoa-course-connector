"""Privacy-safe diagnostics for browser-session snapshots."""

from __future__ import annotations

import json
import shlex
from collections import Counter
from pathlib import Path
from typing import Any

from aoa_course_connector.adapters.browser.captions import caption_resource_key, caption_text_from_resource, is_caption_asset, resource_looks_like_caption
from aoa_course_connector.adapters.browser.crawl import discover_lesson_links
from aoa_course_connector.adapters.browser.discovery import discover_course_links
from aoa_course_connector.adapters.browser.snapshot import parse_html_snapshot


def audit_browser_snapshot_file(
    snapshot_path: Path,
    *,
    platform: str | None = None,
    max_sources: int = 50,
    max_lessons: int = 50,
    link_pattern: str | None = None,
) -> dict[str, object]:
    raw_path = snapshot_path.expanduser().resolve()
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    return audit_browser_snapshot(
        raw,
        snapshot_path=raw_path,
        platform=platform,
        max_sources=max_sources,
        max_lessons=max_lessons,
        link_pattern=link_pattern,
    )


def audit_browser_snapshot(
    raw: dict[str, Any],
    *,
    snapshot_path: Path | None = None,
    platform: str | None = None,
    max_sources: int = 50,
    max_lessons: int = 50,
    link_pattern: str | None = None,
) -> dict[str, object]:
    resolved_platform = str(platform or raw.get("platform") or raw.get("source", {}).get("platform") or "browser")
    source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    pages = [page for page in raw.get("pages", []) if isinstance(page, dict)]
    resources = _snapshot_resources(raw, pages)
    resource_urls = _resource_urls(resources)
    counts: Counter[str] = Counter()
    page_kind_counts: Counter[str] = Counter()
    page_reports: list[dict[str, object]] = []
    missing_caption_resources: list[dict[str, object]] = []

    for index, page in enumerate(pages, start=1):
        page_url = str(page.get("url") or source.get("source_ref") or "")
        html = str(page.get("html") or "")
        kind = _page_kind(page)
        page_kind_counts[kind] += 1
        if not html.strip():
            counts["empty_html_page_count"] += 1
        snapshot = parse_html_snapshot(html, page_url)
        course_links = discover_course_links(
            html,
            page_url,
            platform=resolved_platform,
            max_sources=max_sources,
            link_pattern=link_pattern,
        )
        lesson_links = discover_lesson_links(
            html,
            page_url,
            platform=resolved_platform,
            max_lessons=max_lessons,
            link_pattern=link_pattern,
        )
        caption_assets = [asset for asset in snapshot.assets if is_caption_asset(asset)]
        for asset in caption_assets:
            asset_url = str(asset.get("url") or "")
            if asset_url and caption_resource_key(asset_url) not in resource_urls:
                missing_caption_resources.append(
                    {
                        "page_id": str(page.get("page_id") or f"page-{index}"),
                        "url": asset_url,
                        "kind": str(asset.get("kind") or ""),
                        "reason": "visible caption sidecar has no matching resources[] payload",
                    }
                )
        page_report = {
            "page_id": str(page.get("page_id") or f"page-{index}"),
            "kind": kind,
            "url": page_url,
            "title": str(page.get("title") or snapshot.title or ""),
            "text_length": len(snapshot.text),
            "heading_count": len(snapshot.headings),
            "link_count": len(snapshot.links),
            "course_link_count": len(course_links),
            "lesson_link_count": len(lesson_links),
            "asset_count": len(snapshot.assets),
            "caption_asset_count": len(caption_assets),
            "transcript_count": len(snapshot.transcripts),
            "comment_count": len(snapshot.comments),
            "has_progress": bool(snapshot.progress),
            "pagination_link_count": len(snapshot.pagination_links),
        }
        page_reports.append(page_report)
        counts.update(
            {
                "course_link_count": len(course_links),
                "lesson_link_count": len(lesson_links),
                "asset_count": len(snapshot.assets),
                "caption_asset_count": len(caption_assets),
                "transcript_count": len(snapshot.transcripts),
                "comment_count": len(snapshot.comments),
                "pagination_link_count": len(snapshot.pagination_links),
            }
        )
        if snapshot.progress:
            counts["progress_page_count"] += 1
        if kind == "lesson":
            counts["lesson_page_count"] += 1
        if kind == "course_index":
            counts["course_index_page_count"] += 1
        if kind not in {"account_catalog", "catalog", "catalog_page"}:
            counts["crawl_lesson_link_count"] += len(lesson_links)

    caption_resource_errors = _caption_resource_parse_errors(resources)
    caption_resource_count = len([resource for resource in resources if _is_caption_resource(resource)])
    counts["page_count"] = len(pages)
    counts["caption_resource_count"] = caption_resource_count
    counts["caption_resource_parse_error_count"] = len(caption_resource_errors)
    counts["caption_resource_missing_payload_count"] = len(missing_caption_resources)

    readiness = _readiness(counts)
    coverage_gaps = _coverage_gaps(counts)
    failures = _failures(counts, missing_caption_resources, caption_resource_errors, readiness)
    repair_lanes = _repair_lanes(failures, coverage_gaps, snapshot_path, resolved_platform)
    next_commands = _next_commands(snapshot_path, resolved_platform, readiness, link_pattern)
    status = "ok" if not failures else "partial"

    return {
        "schema": "aoa_course_browser_snapshot_audit_v1",
        "status": status,
        "platform": resolved_platform,
        "source_ref": str(source.get("source_ref") or ""),
        "captured_at": str(raw.get("captured_at") or ""),
        "snapshot_path": str(snapshot_path) if snapshot_path else "",
        "network_touched": False,
        "read_only": True,
        "privacy": {
            "raw_html_included": False,
            "raw_caption_text_included": False,
            "safe_to_store_as_runtime_report": True,
            "do_not_commit_operator_snapshots": True,
        },
        "readiness": readiness,
        "counts": dict(sorted(counts.items())),
        "page_kind_counts": dict(sorted(page_kind_counts.items())),
        "pages": page_reports,
        "coverage_gaps": coverage_gaps,
        "failures": failures,
        "repair_lanes": repair_lanes,
        "caption_resource_errors": caption_resource_errors,
        "missing_caption_resources": missing_caption_resources,
        "next_commands": next_commands,
    }


def _readiness(counts: Counter[str]) -> dict[str, bool]:
    ready_for_discovery = counts["course_link_count"] > 0
    ready_for_crawl = counts["crawl_lesson_link_count"] > 0 or counts["course_index_page_count"] > 0
    ready_for_materialize = counts["lesson_page_count"] > 0 or ready_for_crawl
    ready_for_smoke = ready_for_materialize
    return {
        "ready_for_discovery": ready_for_discovery,
        "ready_for_crawl": ready_for_crawl,
        "ready_for_materialize": ready_for_materialize,
        "ready_for_smoke": ready_for_smoke,
    }


def _coverage_gaps(counts: Counter[str]) -> list[dict[str, object]]:
    gaps: list[dict[str, object]] = []
    if counts["progress_page_count"] < 1:
        gaps.append({"surface": "progress", "reason": "no visible progress/status signal found"})
    if counts["comment_count"] < 1:
        gaps.append({"surface": "comments", "reason": "no visible discussion/comment signal found"})
    if counts["transcript_count"] < 1 and counts["caption_asset_count"] < 1 and counts["caption_resource_count"] < 1:
        gaps.append({"surface": "transcripts", "reason": "no visible transcript/caption/sidecar signal found"})
    if counts["pagination_link_count"] < 1:
        gaps.append({"surface": "pagination", "reason": "no visible next-page/catalog pagination signal found"})
    return gaps


def _failures(
    counts: Counter[str],
    missing_caption_resources: list[dict[str, object]],
    caption_resource_errors: list[dict[str, object]],
    readiness: dict[str, bool],
) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    if counts["page_count"] < 1:
        failures.append({"surface": "snapshot", "reason": "snapshot has no pages"})
    if counts["empty_html_page_count"]:
        failures.append(
            {
                "surface": "capture",
                "reason": "one or more pages have empty html",
                "count": counts["empty_html_page_count"],
            }
        )
    if not readiness["ready_for_discovery"] and not readiness["ready_for_materialize"]:
        failures.append(
            {
                "surface": "source_selection",
                "reason": "snapshot has neither course discovery links nor course/lesson materialization signals",
            }
        )
    if missing_caption_resources:
        failures.append(
            {
                "surface": "caption_sidecar",
                "reason": "visible caption sidecar assets have no matching resources[] payload",
                "count": len(missing_caption_resources),
            }
        )
    if caption_resource_errors:
        failures.append(
            {
                "surface": "caption_sidecar",
                "reason": "caption resources were present but did not parse into transcript text",
                "count": len(caption_resource_errors),
            }
        )
    return failures


def _repair_lanes(
    failures: list[dict[str, object]],
    coverage_gaps: list[dict[str, object]],
    snapshot_path: Path | None,
    platform: str,
) -> list[dict[str, object]]:
    lanes: list[dict[str, object]] = []
    failure_surfaces = {str(item.get("surface") or "") for item in failures}
    gap_surfaces = {str(item.get("surface") or "") for item in coverage_gaps}
    path = shlex.quote(str(snapshot_path)) if snapshot_path else "/path/to/browser-snapshot.json"
    platform_arg = shlex.quote(platform)
    if "source_selection" in failure_surfaces or "snapshot" in failure_surfaces:
        lanes.append(
            {
                "lane": "source_selection",
                "reason": "capture a catalog page with course links or a course page with lesson links/content",
                "commands": [
                    f"aoa-course discover browser-snapshot {path} --platform {platform_arg} --max-sources 50",
                    f"aoa-course crawl browser-snapshot {path} --platform {platform_arg} --max-lessons 50",
                ],
            }
        )
    if "capture" in failure_surfaces:
        lanes.append(
            {
                "lane": "content_capture",
                "reason": "recapture after login and wait for the course page content to render",
                "commands": [f"aoa-course smoke browser-snapshot --platform {platform_arg} --course-snapshot {path} --query \"course-specific question\""],
            }
        )
    if "caption_sidecar" in failure_surfaces:
        lanes.append(
            {
                "lane": "caption_sidecar",
                "reason": "collect matching caption sidecar text into resources[] or record protected-resource errors",
                "commands": [f"aoa-course inspect browser-snapshot {path} --platform {platform_arg}"],
            }
        )
    if "transcripts" in gap_surfaces:
        lanes.append(
            {
                "lane": "transcript_coverage",
                "reason": "look for visible transcript/caption blocks or sidecar tracks on lesson pages",
                "commands": [f"aoa-course crawl browser-snapshot {path} --platform {platform_arg} --max-lessons 50"],
            }
        )
    if "comments" in gap_surfaces:
        lanes.append(
            {
                "lane": "discussion_coverage",
                "reason": "inspect whether comments are hidden, lazy-loaded, or rendered with unusual markup",
                "commands": [f"aoa-course smoke browser-snapshot --platform {platform_arg} --course-snapshot {path} --query \"course-specific question\""],
            }
        )
    if "pagination" in gap_surfaces:
        lanes.append(
            {
                "lane": "pagination_coverage",
                "reason": "verify whether the account catalog has more pages or uses custom next-page controls",
                "commands": [f"aoa-course discover browser-snapshot {path} --platform {platform_arg} --max-sources 50"],
            }
        )
    return lanes


def _next_commands(
    snapshot_path: Path | None,
    platform: str,
    readiness: dict[str, bool],
    link_pattern: str | None,
) -> list[str]:
    path = shlex.quote(str(snapshot_path)) if snapshot_path else "/path/to/browser-snapshot.json"
    platform_arg = shlex.quote(platform)
    link_arg = f" --link-pattern {shlex.quote(link_pattern)}" if link_pattern else ""
    commands: list[str] = []
    if readiness["ready_for_discovery"]:
        commands.append(f"aoa-course discover browser-snapshot {path} --platform {platform_arg} --max-sources 50")
    if readiness["ready_for_crawl"]:
        commands.append(f"aoa-course crawl browser-snapshot {path} --platform {platform_arg} --run {platform_arg}-snapshot-crawl --max-lessons 50{link_arg}")
    if readiness["ready_for_materialize"]:
        commands.append(f"aoa-course materialize browser-snapshot {path} --platform {platform_arg} --run {platform_arg}-snapshot")
        commands.append(f"aoa-course smoke browser-snapshot --platform {platform_arg} --course-snapshot {path} --query \"course-specific question\"")
    return commands


def _caption_resource_parse_errors(resources: list[dict[str, object]]) -> list[dict[str, object]]:
    errors: list[dict[str, object]] = []
    for resource in resources:
        if not _is_caption_resource(resource):
            continue
        if caption_text_from_resource(resource):
            continue
        errors.append(
            {
                "url": str(resource.get("url") or resource.get("source_url") or ""),
                "content_type": str(resource.get("content_type") or ""),
                "reason": "caption resource parsed without transcript text",
            }
        )
    return errors


def _snapshot_resources(raw: dict[str, Any], pages: list[dict[str, Any]]) -> list[dict[str, object]]:
    resources_by_url: dict[str, dict[str, object]] = {}
    anonymous_resources: list[dict[str, object]] = []
    for container in [raw, *pages]:
        resources = container.get("resources") if isinstance(container, dict) else None
        if not isinstance(resources, list):
            continue
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            url = str(resource.get("url") or resource.get("source_url") or "")
            if url:
                resources_by_url[caption_resource_key(url)] = resource
            else:
                anonymous_resources.append(resource)
    return [*resources_by_url.values(), *anonymous_resources]


def _is_caption_resource(resource: dict[str, object]) -> bool:
    return resource_looks_like_caption(
        str(resource.get("url") or resource.get("source_url") or ""),
        str(resource.get("content_type") or ""),
    )


def _resource_urls(resources: list[dict[str, object]]) -> set[str]:
    urls: set[str] = set()
    for resource in resources:
        url = str(resource.get("url") or resource.get("source_url") or "")
        if url:
            urls.add(caption_resource_key(url))
    return urls


def _page_kind(page: dict[str, object]) -> str:
    return str(page.get("kind") or "page").casefold()
