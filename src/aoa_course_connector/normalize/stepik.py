"""Normalize Stepik API snapshots into canonical course bundles."""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from typing import Any

from aoa_course_connector.evidence import make_evidence


TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def normalize_stepik_raw(raw: dict[str, Any], run_id: str, raw_ref: str | None = None) -> dict[str, object]:
    fetched_at = str(raw.get("fetched_at") or _now())
    source = dict(raw.get("source") or {})
    course_raw = dict(raw.get("course") or {})
    course_id = str(course_raw.get("id") or source.get("source_ref") or "unknown")
    course_url = f"https://stepik.org/course/{course_id}"
    evidence: dict[str, dict[str, object]] = {}
    course_evidence = _evidence(evidence, course_url, fetched_at, f"course:{course_id}", raw_ref)
    course = {
        "course_id": f"stepik:course:{course_id}",
        "source_id": source.get("source_id") or f"source:stepik:{course_id}",
        "platform": "stepik",
        "title": course_raw.get("title") or f"Stepik course {course_id}",
        "description": _clean_html(course_raw.get("summary") or course_raw.get("description") or ""),
        "url": course_url,
        "progress": {
            "progress_id": f"progress:stepik:course:{course_id}",
            "course_id": f"stepik:course:{course_id}",
            "state": "unknown",
            "updated_at": course_raw.get("update_date") or fetched_at,
            "evidence": course_evidence,
        },
        "modules": [],
        "topics": ["stepik", "clean-api"],
        "entities": [{"entity_id": f"entity:platform:stepik", "kind": "platform", "value": "Stepik", "evidence_refs": [course_evidence["evidence_id"]]}],
        "evidence": course_evidence,
    }
    for section_index, section_item in enumerate(raw.get("sections", []), start=1):
        if not isinstance(section_item, dict):
            continue
        section_raw = dict(section_item.get("section") or {})
        section_id = str(section_raw.get("id") or section_index)
        module = {
            "module_id": f"stepik:section:{section_id}",
            "course_id": course["course_id"],
            "title": section_raw.get("title") or f"Stepik section {section_id}",
            "order": int(section_raw.get("position") or section_index),
            "lessons": [],
        }
        for unit_index, unit_item in enumerate(section_item.get("units", []), start=1):
            if not isinstance(unit_item, dict):
                continue
            lesson_raw = dict(unit_item.get("lesson") or {})
            unit_raw = dict(unit_item.get("unit") or {})
            lesson_id = str(lesson_raw.get("id") or unit_raw.get("lesson") or unit_index)
            lesson_url = str(lesson_raw.get("canonical_url") or f"https://stepik.org/lesson/{lesson_id}/")
            lesson_evidence = _evidence(evidence, lesson_url, fetched_at, f"lesson:{lesson_id}", raw_ref)
            lesson = {
                "lesson_id": f"stepik:lesson:{lesson_id}",
                "course_id": course["course_id"],
                "module_id": module["module_id"],
                "title": lesson_raw.get("title") or f"Stepik lesson {lesson_id}",
                "url": lesson_url,
                "order": int(unit_raw.get("position") or unit_index),
                "freshness_state": "current" if lesson_raw.get("update_date") else "unknown",
                "steps": [],
                "assets": [],
                "transcripts": [],
                "assignments": [],
                "comment_threads": [],
                "topics": ["stepik", str(section_raw.get("title") or "").casefold()],
                "entities": [{"entity_id": f"entity:stepik_lesson:{lesson_id}", "kind": "stepik_lesson", "value": lesson_id, "evidence_refs": [lesson_evidence["evidence_id"]]}],
                "evidence": lesson_evidence,
            }
            for step_index, step_raw in enumerate(unit_item.get("steps", []), start=1):
                if not isinstance(step_raw, dict):
                    continue
                step_id = str(step_raw.get("id") or step_index)
                block = step_raw.get("block") if isinstance(step_raw.get("block"), dict) else {}
                kind = str(block.get("name") or "step")
                step_url = f"https://stepik.org/lesson/{lesson_id}/step/{step_raw.get('position') or step_index}"
                step_evidence = _evidence(evidence, step_url, fetched_at, f"step:{step_id}", raw_ref)
                text = _step_text(block, step_raw)
                lesson["steps"].append(
                    {
                        "step_id": f"stepik:step:{step_id}",
                        "lesson_id": lesson["lesson_id"],
                        "kind": kind,
                        "order": int(step_raw.get("position") or step_index),
                        "text": text,
                        "evidence": step_evidence,
                    }
                )
                if kind != "text":
                    lesson["assignments"].append(
                        {
                            "assignment_id": f"stepik:assignment:{step_id}",
                            "lesson_id": lesson["lesson_id"],
                            "prompt": text or f"Stepik {kind} assignment {step_id}",
                            "status": str(step_raw.get("status") or "unknown"),
                            "evidence": step_evidence,
                        }
                    )
                video = block.get("video")
                if video:
                    lesson["assets"].append(
                        {
                            "asset_id": f"stepik:asset:video:{step_id}",
                            "lesson_id": lesson["lesson_id"],
                            "kind": "video",
                            "title": f"Stepik video step {step_id}",
                            "url": str(video),
                            "download_state": "metadata_only",
                            "evidence": step_evidence,
                        }
                    )
                for subtitle in block.get("subtitle_files") or []:
                    if isinstance(subtitle, dict) and subtitle.get("url"):
                        lesson["assets"].append(
                            {
                                "asset_id": f"stepik:asset:subtitle:{step_id}:{subtitle.get('lang') or 'unknown'}",
                                "lesson_id": lesson["lesson_id"],
                                "kind": "subtitle",
                                "title": f"Stepik subtitle {subtitle.get('lang') or ''}".strip(),
                                "url": str(subtitle.get("url")),
                                "download_state": "metadata_only",
                                "evidence": step_evidence,
                            }
                        )
            module["lessons"].append(lesson)
        course["modules"].append(module)
    return {
        "schema": "aoa_course_normalized_bundle_v1",
        "run_id": run_id,
        "source": source or {"source_id": f"source:stepik:{course_id}", "platform": "stepik", "source_ref": course_id, "access_mode": "public_api"},
        "normalized_at": _now(),
        "courses": [course],
        "evidence": list(evidence.values()),
    }


def _step_text(block: dict[str, Any], step_raw: dict[str, Any]) -> str:
    parts = [block.get("text"), step_raw.get("instruction")]
    options = block.get("options")
    if isinstance(options, dict):
        for key in ["title", "description", "prompt"]:
            if options.get(key):
                parts.append(options[key])
    text = " ".join(_clean_html(part) for part in parts if part)
    return text or str(block.get("name") or "Stepik step")


def _clean_html(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = TAG_RE.sub(" ", text)
    return SPACE_RE.sub(" ", text).strip()


def _evidence(store: dict[str, dict[str, object]], source_url: str, fetched_at: str, selector: str, raw_ref: str | None) -> dict[str, object]:
    item = make_evidence("stepik", source_url, fetched_at, selector=selector, raw_ref=raw_ref or "")
    store[str(item["evidence_id"])] = item
    return item


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
