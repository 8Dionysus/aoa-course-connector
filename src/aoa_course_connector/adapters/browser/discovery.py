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
    if max_sources <= 0:
        return []
    if platform == "skillspace":
        return _discover_skillspace_embedded_catalog_links(payloads, base_url, max_sources=max_sources, link_pattern=link_pattern)
    if platform != "getcourse":
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


def _discover_skillspace_embedded_catalog_links(
    payloads: object,
    base_url: str,
    *,
    max_sources: int,
    link_pattern: str | None,
) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in _iter_payload_records(payloads):
        payload = record.get("json")
        source_url = str(record.get("url") or "")
        catalog_endpoint = _skillspace_catalog_endpoint(source_url)
        for block in _iter_skillspace_course_blocks(payload, catalog_endpoint=catalog_endpoint):
            item = _skillspace_course_link(block, base_url)
            if not item:
                continue
            href = item["href"]
            if link_pattern and not fnmatch(href, link_pattern):
                continue
            if href in seen:
                continue
            seen.add(href)
            links.append(item)
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


def _iter_payload_records(payloads: object) -> list[dict[str, Any]]:
    if not isinstance(payloads, list):
        return []
    return [payload for payload in payloads if isinstance(payload, dict) and "json" in payload]


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


def _skillspace_catalog_endpoint(url: str) -> bool:
    lowered = url.casefold()
    return "/api/rest/student/course/list" in lowered or "/api/rest/school/course/list" in lowered


def _iter_skillspace_course_blocks(value: object, *, catalog_endpoint: bool) -> list[dict[str, Any]]:
    if catalog_endpoint:
        return _iter_catalog_items(value)
    return [block for block in _iter_dicts(value) if _skillspace_courseish_block(block)]


def _iter_catalog_items(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return []
    for key in ["courses", "items", "rows", "list", "content", "data", "result"]:
        child = value.get(key)
        if isinstance(child, list):
            return [item for item in child if isinstance(item, dict)]
        if isinstance(child, dict):
            nested = _iter_catalog_items(child)
            if nested:
                return nested
    return [value] if _skillspace_courseish_block(value) else []


def _skillspace_courseish_block(block: dict[str, Any]) -> bool:
    typename = str(block.get("__typename") or block.get("type") or "").casefold()
    if "course" in typename:
        return True
    if _first_course_url(block):
        return True
    keys = {str(key).casefold() for key in block}
    if keys & {"courseid", "course_id", "courseuuid", "course_uuid"}:
        return True
    course = block.get("course")
    return isinstance(course, dict) and bool(_skillspace_course_id(course) or _skillspace_course_title(course))


def _skillspace_course_link(block: dict[str, Any], base_url: str) -> dict[str, str] | None:
    href = _first_course_url(block)
    course_block = block.get("course") if isinstance(block.get("course"), dict) else block
    course_id = _skillspace_course_id(block) or _skillspace_course_id(course_block)
    if not href and course_id:
        href = urljoin(base_url, f"/course/{course_id}")
    elif href:
        href = urljoin(base_url, href)
    if not href:
        return None
    title = _skillspace_course_title(block) or _skillspace_course_title(course_block) or href
    return {
        "href": href,
        "text": title,
        "kind": "course",
        "module": "",
        "title": title,
    }


def _first_course_url(value: object) -> str:
    if isinstance(value, dict):
        for key in ["url", "href", "link", "path", "route", "to"]:
            candidate = str(value.get(key) or "")
            if _looks_like_skillspace_course_url(candidate):
                return candidate
        for key in ["course", "flow"]:
            nested = value.get(key)
            candidate = _first_course_url(nested)
            if candidate:
                return candidate
    return ""


def _looks_like_skillspace_course_url(value: str) -> bool:
    lowered = value.casefold()
    if "/course/" not in lowered:
        return False
    return not any(segment in lowered for segment in ["/constructor/", "/completion", "/certificate"])


def _skillspace_course_id(block: object) -> str:
    if not isinstance(block, dict):
        return ""
    for key in ["courseId", "course_id", "courseUuid", "course_uuid", "uuid", "id", "slug"]:
        value = str(block.get(key) or "").strip()
        if value and value.lower() not in {"none", "null"}:
            return value
    for key in ["course", "flow"]:
        value = _skillspace_course_id(block.get(key))
        if value:
            return value
    return ""


def _skillspace_course_title(block: object) -> str:
    if not isinstance(block, dict):
        return ""
    for key in ["title", "name", "label"]:
        value = str(block.get(key) or "").strip()
        if value:
            return value
    for key in ["course", "flow"]:
        value = _skillspace_course_title(block.get(key))
        if value:
            return value
    return ""


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
