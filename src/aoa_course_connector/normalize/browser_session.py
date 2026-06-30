"""Normalize browser-session snapshots into canonical course bundles."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aoa_course_connector.adapters.browser import parse_html_snapshot
from aoa_course_connector.evidence import make_evidence


def normalize_browser_snapshot(raw: dict[str, Any], run_id: str, raw_ref: str | None = None) -> dict[str, object]:
    captured_at = str(raw.get("captured_at") or _now())
    platform = str(raw.get("platform") or raw.get("source", {}).get("platform") or "browser_session")
    source = dict(raw.get("source") or {})
    pages = [page for page in raw.get("pages", []) if isinstance(page, dict)]
    course_page = _first_page(pages, "course_index") or (pages[0] if pages else {})
    course_url = str(course_page.get("url") or source.get("source_ref") or "")
    course_snapshot = parse_html_snapshot(str(course_page.get("html") or ""), course_url)
    progress_info = course_snapshot.progress
    evidence: dict[str, dict[str, object]] = {}
    course_evidence = _evidence(evidence, platform, course_url, captured_at, "course_index", raw_ref)
    course_id = f"{platform}:course:{_slug(source.get('source_ref') or course_url or 'browser-course')}"
    course = {
        "course_id": course_id,
        "source_id": source.get("source_id") or f"source:{platform}:{_slug(source.get('source_ref') or course_url)}",
        "platform": platform,
        "title": raw.get("course_title") or course_snapshot.title or source.get("title") or f"{platform} browser course",
        "description": course_snapshot.text[:1000],
        "url": course_url,
        "progress": {
            "progress_id": f"progress:{course_id}",
            "course_id": course_id,
            "state": str(raw.get("progress_state") or progress_info.get("state") or "unknown"),
            "percent": str(progress_info.get("percent") or raw.get("progress_percent") or ""),
            "label": str(progress_info.get("label") or ""),
            "updated_at": str(progress_info.get("updated_at") or captured_at),
            "evidence": course_evidence,
        },
        "modules": [],
        "topics": [platform, "browser-session"],
        "entities": [
            {"entity_id": f"entity:platform:{platform}", "kind": "platform", "value": platform, "evidence_refs": [course_evidence["evidence_id"]]},
            {"entity_id": "entity:mode:browser-session", "kind": "mode", "value": "browser_session", "evidence_refs": [course_evidence["evidence_id"]]},
        ],
        "evidence": course_evidence,
    }
    lesson_pages = [page for page in pages if str(page.get("kind") or "").casefold() == "lesson"]
    if not lesson_pages:
        lesson_pages = _lessons_from_index(course_page, course_snapshot)
    module_map: dict[str, dict[str, object]] = {}
    for index, page in enumerate(lesson_pages, start=1):
        lesson = _lesson_from_page(page, course, platform, captured_at, raw_ref, evidence, index)
        module_title = str(page.get("module_title") or page.get("module") or "Browser Session Lessons")
        module_id = f"{platform}:module:{_slug(module_title)}"
        module = module_map.setdefault(
            module_id,
            {
                "module_id": module_id,
                "course_id": course_id,
                "title": module_title,
                "order": len(module_map) + 1,
                "lessons": [],
            },
        )
        lesson["module_id"] = module_id
        module["lessons"].append(lesson)  # type: ignore[index,union-attr]
    course["modules"] = list(module_map.values())
    return {
        "schema": "aoa_course_normalized_bundle_v1",
        "run_id": run_id,
        "source": source or {"source_id": course["source_id"], "platform": platform, "source_ref": course_url, "access_mode": "browser_session"},
        "normalized_at": _now(),
        "courses": [course],
        "evidence": list(evidence.values()),
    }


def _lesson_from_page(page: dict[str, Any], course: dict[str, object], platform: str, captured_at: str, raw_ref: str | None, evidence: dict[str, dict[str, object]], order: int) -> dict[str, object]:
    url = str(page.get("url") or course.get("url") or "")
    snapshot = parse_html_snapshot(str(page.get("html") or ""), url)
    lesson_id = f"{platform}:lesson:{_slug(page.get('page_id') or url or order)}"
    lesson_evidence = _evidence(evidence, platform, url, captured_at, f"lesson:{lesson_id}", raw_ref)
    step_text = snapshot.text or str(page.get("title") or snapshot.title or lesson_id)
    step_evidence = _evidence(evidence, platform, url, captured_at, f"step:{lesson_id}:body", raw_ref)
    lesson = {
        "lesson_id": lesson_id,
        "course_id": course["course_id"],
        "module_id": "",
        "title": page.get("title") or snapshot.title or f"Browser lesson {order}",
        "url": url,
        "order": int(page.get("order") or order),
        "freshness_state": str(page.get("freshness_state") or "current"),
        "steps": [
            {
                "step_id": f"{lesson_id}:body",
                "lesson_id": lesson_id,
                "kind": "browser_html_text",
                "order": 1,
                "text": step_text,
                "evidence": step_evidence,
            }
        ],
        "assets": [],
        "transcripts": [],
        "assignments": [],
        "comment_threads": [],
        "topics": [platform, "browser-session", str(page.get("module_title") or page.get("module") or "").casefold()],
        "entities": [{"entity_id": f"entity:{platform}_lesson:{_slug(page.get('page_id') or url or order)}", "kind": f"{platform}_lesson", "value": str(page.get("page_id") or url), "evidence_refs": [lesson_evidence["evidence_id"]]}],
        "evidence": lesson_evidence,
    }
    for asset_index, asset in enumerate(snapshot.assets, start=1):
        asset_evidence = _evidence(evidence, platform, asset.get("url", url), captured_at, f"asset:{lesson_id}:{asset_index}", raw_ref)
        lesson["assets"].append(
            {
                "asset_id": f"{lesson_id}:asset:{asset_index}",
                "lesson_id": lesson_id,
                "kind": asset.get("kind") or "asset",
                "title": asset.get("title") or f"Asset {asset_index}",
                "url": asset.get("url") or url,
                "download_state": "metadata_only",
                "evidence": asset_evidence,
            }
        )
    for link in snapshot.links:
        if link.get("kind") == "assignment" or "homework" in link.get("href", "") or "task" in link.get("href", ""):
            lesson["assignments"].append(
                {
                    "assignment_id": f"{lesson_id}:assignment:{len(lesson['assignments']) + 1}",
                    "lesson_id": lesson_id,
                    "prompt": link.get("text") or link.get("href"),
                    "status": "available",
                    "evidence": lesson_evidence,
                }
            )
    for thread in _comment_threads_from_snapshot(snapshot.comments, lesson_id, lesson_evidence, evidence, platform, url, captured_at, raw_ref):
        lesson["comment_threads"].append(thread)
    return lesson


def _comment_threads_from_snapshot(
    comments: list[dict[str, str]],
    lesson_id: str,
    lesson_evidence: dict[str, object],
    evidence: dict[str, dict[str, object]],
    platform: str,
    url: str,
    captured_at: str,
    raw_ref: str | None,
) -> list[dict[str, object]]:
    threads: dict[str, dict[str, object]] = {}
    for index, comment in enumerate(comments, start=1):
        raw_thread_id = str(comment.get("thread_id") or "visible-thread")
        thread_id = f"{lesson_id}:thread:{_slug(raw_thread_id)}"
        thread_evidence = _evidence(evidence, platform, url, captured_at, f"thread:{thread_id}", raw_ref)
        thread = threads.setdefault(
            thread_id,
            {
                "thread_id": thread_id,
                "lesson_id": lesson_id,
                "title": raw_thread_id,
                "status": "visible",
                "comments": [],
                "evidence": thread_evidence,
            },
        )
        comment_id = f"{thread_id}:comment:{_slug(comment.get('comment_id') or index)}"
        comment_evidence = _evidence(evidence, platform, url, captured_at, f"comment:{comment_id}", raw_ref)
        thread["comments"].append(
            {
                "comment_id": comment_id,
                "thread_id": thread_id,
                "author_label": comment.get("author") or "visible user",
                "posted_at": comment.get("created_at") or captured_at,
                "text": comment.get("text") or "",
                "evidence": comment_evidence,
            }
        )
    return list(threads.values())


def _lessons_from_index(course_page: dict[str, Any], snapshot: object) -> list[dict[str, object]]:
    links = getattr(snapshot, "links", [])
    pages: list[dict[str, object]] = []
    for index, link in enumerate(links, start=1):
        href = str(link.get("href") or "")
        if link.get("kind") == "lesson" or "lesson" in href or "teach/control" in href:
            pages.append(
                {
                    "page_id": f"index-link-{index}",
                    "kind": "lesson",
                    "url": href,
                    "title": link.get("text") or link.get("title") or href,
                    "module_title": link.get("module") or "Browser Session Lessons",
                    "order": index,
                    "html": f"<article><h1>{link.get('text') or href}</h1><p>Discovered from course index. Fetch this lesson page for full content.</p></article>",
                }
            )
    if not pages and course_page:
        pages.append({**course_page, "kind": "lesson", "page_id": course_page.get("page_id") or "course-index-as-lesson"})
    return pages


def _first_page(pages: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    for page in pages:
        if str(page.get("kind") or "").casefold() == kind:
            return page
    return None


def _evidence(store: dict[str, dict[str, object]], platform: str, source_url: str, fetched_at: str, selector: str, raw_ref: str | None) -> dict[str, object]:
    item = make_evidence(platform, source_url, fetched_at, selector=selector, raw_ref=raw_ref or "")
    store[str(item["evidence_id"])] = item
    return item


def _slug(value: object) -> str:
    text = str(value or "").casefold()
    slug = "".join(ch if ch.isalnum() else "-" for ch in text).strip("-")
    return slug or "item"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
