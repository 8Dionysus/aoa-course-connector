"""Browser-session account catalog discovery helpers."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

from aoa_course_connector.adapters.browser.snapshot import parse_html_snapshot


COURSE_KINDS = {"course", "course_index", "training", "program", "catalog_course"}
COURSE_URL_HINTS = (
    "teach/control/stream",
    "/pl/teach/control",
    "/course/",
    "/courses/",
    "/training/",
    "/program/",
)
NON_COURSE_URL_HINTS = (
    "lesson",
    "task",
    "homework",
    "assignment",
    "files/",
    "assets/",
    "login",
    "logout",
)


def build_browser_catalog_discovery(
    raw: dict[str, Any],
    *,
    platform: str | None = None,
    max_sources: int = 50,
    link_pattern: str | None = None,
) -> dict[str, object]:
    resolved_platform = str(platform or raw.get("platform") or raw.get("source", {}).get("platform") or "browser")
    captured_at = str(raw.get("captured_at") or "")
    source = dict(raw.get("source") or {})
    pages = [page for page in raw.get("pages", []) if isinstance(page, dict)]
    discovered: list[dict[str, object]] = []
    seen: set[str] = set()
    for page in pages:
        page_url = str(page.get("url") or source.get("source_ref") or "")
        links = discover_course_links(
            str(page.get("html") or ""),
            page_url,
            platform=resolved_platform,
            max_sources=max_sources,
            link_pattern=link_pattern,
        )
        for link in links:
            href = str(link["href"])
            if href in seen:
                continue
            seen.add(href)
            discovered.append(
                {
                    "platform": resolved_platform,
                    "source_ref": href,
                    "title": link.get("text") or link.get("title") or href,
                    "access_mode": "browser_session",
                    "source_kind": link.get("kind") or "course",
                    "order": len(discovered) + 1,
                    "evidence": {
                        "page_url": page_url,
                        "selector": f"link:{len(discovered) + 1}",
                        "fetched_at": captured_at,
                    },
                }
            )
            if len(discovered) >= max_sources:
                break
        if len(discovered) >= max_sources:
            break
    return {
        "schema": "aoa_course_browser_catalog_discovery_v1",
        "platform": resolved_platform,
        "source_ref": source.get("source_ref") or "",
        "captured_at": captured_at,
        "course_count": len(discovered),
        "courses": discovered,
    }


def discover_course_links(
    html: str,
    base_url: str,
    *,
    platform: str | None = None,
    max_sources: int = 50,
    link_pattern: str | None = None,
) -> list[dict[str, str]]:
    if max_sources <= 0:
        return []
    snapshot = parse_html_snapshot(html, base_url)
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in snapshot.links:
        href = str(link.get("href") or "")
        if not href or href in seen:
            continue
        if not is_course_link(link, platform=platform, link_pattern=link_pattern):
            continue
        seen.add(href)
        links.append(
            {
                "href": href,
                "text": str(link.get("text") or ""),
                "kind": str(link.get("kind") or ""),
                "module": str(link.get("module") or ""),
                "title": str(link.get("title") or ""),
            }
        )
        if len(links) >= max_sources:
            break
    return links


def is_course_link(link: dict[str, str], *, platform: str | None = None, link_pattern: str | None = None) -> bool:
    href = str(link.get("href") or "")
    if not href:
        return False
    if link_pattern:
        return fnmatch(href, link_pattern)
    kind = str(link.get("kind") or "").casefold()
    if kind in COURSE_KINDS:
        return True
    lowered = href.casefold()
    if any(hint in lowered for hint in NON_COURSE_URL_HINTS):
        return False
    if platform == "getcourse" and "teach/control/stream" in lowered:
        return True
    if platform == "skillspace" and "/course/" in lowered:
        return True
    return any(hint in lowered for hint in COURSE_URL_HINTS)
