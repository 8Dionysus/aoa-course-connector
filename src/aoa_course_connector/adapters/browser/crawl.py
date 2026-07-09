"""Course-tree discovery helpers for browser-session adapters."""

from __future__ import annotations

import re
from fnmatch import fnmatch
from html import unescape
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

from aoa_course_connector.adapters.browser.snapshot import parse_html_snapshot


LESSON_URL_HINTS = (
    "lesson",
    "teach/control",
    "/pl/teach/",
    "/course/",
    "/training/",
    "/module/",
)
GETCOURSE_EMBEDDED_LESSON_RE = re.compile(
    r"(?<![=?&])(?P<url>(?:https?://[^/\"'\\<>\s]+)?/teach/control/lesson/view/id/\d+)",
    re.IGNORECASE,
)


def build_crawled_snapshot(
    raw: dict[str, Any],
    *,
    platform: str | None = None,
    max_lessons: int = 20,
    link_pattern: str | None = None,
) -> dict[str, Any]:
    """Return a raw browser snapshot expanded from course index links.

    The function is intentionally dependency-free so fixture and operator-provided
    snapshots can prove the course-tree route without Playwright.
    """

    resolved = dict(raw)
    if platform:
        resolved["platform"] = platform
        resolved.setdefault("source", {})["platform"] = platform
    pages = [page for page in raw.get("pages", []) if isinstance(page, dict)]
    index_page = first_page(pages, "course_index") or (pages[0] if pages else {})
    if not index_page:
        resolved["pages"] = []
        resolved["crawl"] = _crawl_meta(max_lessons=max_lessons, discovered=0, included=0, missing=0, link_pattern=link_pattern)
        return resolved
    index_url = str(index_page.get("url") or raw.get("source", {}).get("source_ref") or "")
    lesson_links = discover_lesson_links(
        str(index_page.get("html") or ""),
        index_url,
        platform=platform,
        max_lessons=max_lessons,
        link_pattern=link_pattern,
    )
    page_by_url = {_canonical_url(str(page.get("url") or "")): page for page in pages if page.get("url")}
    expanded_pages: list[dict[str, Any]] = [dict(index_page, kind="course_index")]
    missing = 0
    for order, link in enumerate(lesson_links, start=1):
        url = str(link["href"])
        page = page_by_url.get(_canonical_url(url))
        if page:
            lesson_page = dict(page)
            lesson_page["kind"] = "lesson"
            lesson_page.setdefault("title", link.get("text") or link.get("title") or url)
            lesson_page.setdefault("module_title", link.get("module") or "Browser Session Lessons")
            lesson_page.setdefault("order", order)
        else:
            missing += 1
            lesson_page = placeholder_lesson_page(link, order)
        expanded_pages.append(lesson_page)
    if not lesson_links:
        expanded_pages.extend(dict(page) for page in pages if page is not index_page)
    resolved["pages"] = expanded_pages
    resolved["crawl"] = _crawl_meta(
        max_lessons=max_lessons,
        discovered=len(lesson_links),
        included=max(0, len(expanded_pages) - 1),
        missing=missing,
        link_pattern=link_pattern,
    )
    return resolved


def discover_lesson_links(
    html: str,
    base_url: str,
    *,
    platform: str | None = None,
    max_lessons: int = 20,
    link_pattern: str | None = None,
) -> list[dict[str, str]]:
    if max_lessons <= 0:
        return []
    snapshot = parse_html_snapshot(html, base_url)
    candidates = list(snapshot.links)
    if str(platform or "").casefold() == "getcourse":
        candidates.extend(_embedded_getcourse_lesson_links(html, base_url))
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in candidates:
        href = str(link.get("href") or "")
        canonical = _canonical_url(href)
        if not canonical or canonical in seen:
            continue
        if not is_lesson_link(link, platform=platform, link_pattern=link_pattern):
            continue
        seen.add(canonical)
        links.append(
            {
                "href": href,
                "text": str(link.get("text") or ""),
                "kind": str(link.get("kind") or ""),
                "module": str(link.get("module") or ""),
                "title": str(link.get("title") or ""),
            }
        )
        if len(links) >= max_lessons:
            break
    return links


def is_lesson_link(link: dict[str, str], *, platform: str | None = None, link_pattern: str | None = None) -> bool:
    href = str(link.get("href") or "")
    if not href:
        return False
    if link_pattern:
        return fnmatch(href, link_pattern)
    if str(link.get("kind") or "").casefold() == "lesson":
        return True
    lowered = href.casefold()
    if str(platform or "").casefold() == "getcourse":
        return "/teach/control/lesson/" in lowered
    return any(hint in lowered for hint in LESSON_URL_HINTS)


def placeholder_lesson_page(link: dict[str, str], order: int) -> dict[str, object]:
    href = str(link.get("href") or "")
    title = str(link.get("text") or link.get("title") or href)
    module = str(link.get("module") or "Browser Session Lessons")
    return {
        "page_id": f"crawl-link-{order}",
        "kind": "lesson",
        "url": href,
        "title": title,
        "module_title": module,
        "order": order,
        "freshness_state": "discovered_not_fetched",
        "html": f"<article><h1>{_html_escape(title)}</h1><p>Discovered from course index. Fetch this lesson page for full content.</p></article>",
    }


def first_page(pages: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    for page in pages:
        if str(page.get("kind") or "").casefold() == kind:
            return page
    return None


def _embedded_getcourse_lesson_links(html: str, base_url: str) -> list[dict[str, str]]:
    normalized = unescape(html).replace("\\/", "/")
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in GETCOURSE_EMBEDDED_LESSON_RE.finditer(normalized):
        href = urljoin(base_url, match.group("url"))
        canonical = _canonical_url(href)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        links.append({"href": href, "text": "", "kind": "lesson", "module": "", "title": ""})
    return links


def _crawl_meta(*, max_lessons: int, discovered: int, included: int, missing: int, link_pattern: str | None) -> dict[str, object]:
    return {
        "schema": "aoa_course_browser_crawl_v1",
        "mode": "course_tree",
        "max_lessons": max_lessons,
        "discovered_lesson_count": discovered,
        "included_lesson_count": included,
        "missing_lesson_page_count": missing,
        "link_pattern": link_pattern or "",
    }


def _canonical_url(url: str) -> str:
    if not url:
        return ""
    stripped, _fragment = urldefrag(url)
    parts = urlsplit(stripped)
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def _html_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
