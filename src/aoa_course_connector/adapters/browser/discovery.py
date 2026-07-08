"""Browser-session account catalog discovery helpers."""

from __future__ import annotations

import re
from fnmatch import fnmatch
from typing import Any
from urllib.parse import urljoin, urlparse

from aoa_course_connector.adapters.browser.snapshot import parse_html_snapshot


COURSE_KINDS = {"course", "course_index", "training", "program", "catalog_course"}
PAGINATION_KINDS = {"next", "next-page", "pagination", "pagination-next"}
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
    "files",
    "assets",
    "login",
    "logout",
)
NON_COURSE_PATH_SEGMENTS = set(NON_COURSE_URL_HINTS)
GETCOURSE_TRAINING_ID_RE = re.compile(r"(?:^|/)training/(\d+)/?(?:$|[?#])")


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
    pagination_links: list[dict[str, object]] = []
    seen: set[str] = set()
    for page in pages:
        page_url = str(page.get("url") or source.get("source_ref") or "")
        snapshot = parse_html_snapshot(str(page.get("html") or ""), page_url)
        for link in snapshot.pagination_links:
            pagination_links.append({"page_url": page_url, "href": link.get("href"), "text": link.get("text")})
        links = discover_course_links(
            str(page.get("html") or ""),
            page_url,
            platform=resolved_platform,
            max_sources=max_sources,
            link_pattern=link_pattern,
        )
        links.extend(
            discover_embedded_catalog_links(
                page.get("api_payloads"),
                page_url,
                platform=resolved_platform,
                max_sources=max_sources,
                link_pattern=link_pattern,
            )
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
        "page_count": len(pages),
        "pagination": {
            "next_link_count": len(pagination_links),
            "next_links": pagination_links,
        },
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


def discover_embedded_catalog_links(
    payloads: object,
    base_url: str,
    *,
    platform: str | None = None,
    max_sources: int = 50,
    link_pattern: str | None = None,
) -> list[dict[str, str]]:
    if max_sources <= 0 or platform != "getcourse":
        return []
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for payload in _iter_payload_json(payloads):
        for block in _iter_dicts(payload):
            training_id = _getcourse_training_id(block)
            if not training_id:
                continue
            href = urljoin(base_url, f"/teach/control/stream/view/id/{training_id}")
            if link_pattern and not fnmatch(href, link_pattern):
                continue
            if href in seen:
                continue
            title = _getcourse_training_title(block)
            if not title:
                continue
            seen.add(href)
            links.append(
                {
                    "href": href,
                    "text": title,
                    "kind": "training",
                    "module": "",
                    "title": title,
                }
            )
            if len(links) >= max_sources:
                return links
    return links


def is_course_link(link: dict[str, str], *, platform: str | None = None, link_pattern: str | None = None) -> bool:
    href = str(link.get("href") or "")
    if not href:
        return False
    kind = str(link.get("kind") or "").casefold()
    rel = str(link.get("rel") or "").casefold().split()
    text = str(link.get("text") or "").casefold()
    if kind in PAGINATION_KINDS or "next" in rel or text in {"next", "next page", "more"}:
        return False
    if link_pattern:
        return fnmatch(href, link_pattern)
    if kind in COURSE_KINDS:
        return True
    lowered = href.casefold()
    if _has_non_course_path_segment(lowered):
        return False
    if platform == "getcourse" and "teach/control/stream" in lowered:
        return True
    if platform == "skillspace" and "/course/" in lowered:
        return True
    return any(hint in lowered for hint in COURSE_URL_HINTS)


def _has_non_course_path_segment(href: str) -> bool:
    segments = {segment for segment in urlparse(href).path.casefold().split("/") if segment}
    return bool(segments & NON_COURSE_PATH_SEGMENTS)


def _iter_payload_json(payloads: object) -> list[object]:
    if not isinstance(payloads, list):
        return []
    items: list[object] = []
    for payload in payloads:
        if isinstance(payload, dict) and "json" in payload:
            items.append(payload["json"])
    return items


def _iter_dicts(value: object) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(_iter_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_iter_dicts(child))
    return found


def _getcourse_training_id(block: dict[str, Any]) -> str:
    candidates = [
        block.get("id"),
        block.get("route"),
        block.get("shortRoute"),
    ]
    onclick = block.get("onClick")
    if isinstance(onclick, dict):
        candidates.extend([onclick.get("url"), onclick.get("route")])
    for value in candidates:
        match = GETCOURSE_TRAINING_ID_RE.search(str(value or ""))
        if match:
            return match.group(1)
    return ""


def _getcourse_training_title(block: dict[str, Any]) -> str:
    for key in ["title", "name", "text"]:
        value = str(block.get(key) or "").strip()
        if value:
            return value
    parents = block.get("parents")
    if isinstance(parents, list):
        for parent in parents:
            if isinstance(parent, dict):
                value = str(parent.get("name") or parent.get("title") or "").strip()
                if value:
                    return value
    return ""
