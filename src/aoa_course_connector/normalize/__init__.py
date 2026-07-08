"""Normalize raw course-platform snapshots into canonical course bundles."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from aoa_course_connector.evidence import make_evidence


def normalize_fixture(raw_path: Path, run_id: str, raw_ref: str | None = None) -> dict[str, object]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    captured_at = str(raw.get("captured_at") or _now())
    source = dict(raw.get("source") or {})
    platform = str(source.get("platform") or "offline_export")
    evidence: dict[str, dict[str, object]] = {}
    courses: list[dict[str, object]] = []
    for raw_course in raw.get("courses", []):
        course_url = str(raw_course.get("url") or source.get("source_ref") or "")
        course_evidence = _evidence(evidence, platform, course_url, captured_at, "course", raw_ref)
        course = {
            "course_id": raw_course["course_id"],
            "source_id": source.get("source_id"),
            "platform": platform,
            "title": raw_course.get("title"),
            "description": raw_course.get("description", ""),
            "url": course_url,
            "progress": _progress(raw_course, captured_at, course_evidence),
            "modules": [],
            "topics": [],
            "entities": [],
            "evidence": course_evidence,
        }
        for raw_module in raw_course.get("modules", []):
            module = {
                "module_id": raw_module["module_id"],
                "course_id": course["course_id"],
                "title": raw_module.get("title"),
                "order": raw_module.get("order", 0),
                "lessons": [],
            }
            for raw_lesson in raw_module.get("lessons", []):
                lesson_url = str(raw_lesson.get("url") or course_url)
                lesson_evidence = _evidence(evidence, platform, lesson_url, captured_at, f"lesson:{raw_lesson['lesson_id']}", raw_ref)
                lesson_temporal = _temporal_fields(raw_lesson, captured_at)
                lesson = {
                    "lesson_id": raw_lesson["lesson_id"],
                    "course_id": course["course_id"],
                    "module_id": module["module_id"],
                    "title": raw_lesson.get("title"),
                    "url": lesson_url,
                    "order": raw_lesson.get("order", 0),
                    "freshness_state": raw_lesson.get("freshness_state", "unknown"),
                    "steps": [],
                    "assets": [],
                    "transcripts": [],
                    "assignments": [],
                    "comment_threads": [],
                    "topics": raw_lesson.get("topics", []),
                    "entities": _entities(raw_lesson.get("entities", []), lesson_evidence),
                    "evidence": lesson_evidence,
                    **lesson_temporal,
                }
                for raw_step in raw_lesson.get("steps", []):
                    step_evidence = _evidence(evidence, platform, lesson_url, captured_at, f"step:{raw_step['step_id']}", raw_ref)
                    lesson["steps"].append({**raw_step, "lesson_id": lesson["lesson_id"], "evidence": step_evidence, **_temporal_fields(raw_step, captured_at, lesson_temporal)})
                for raw_asset in raw_lesson.get("assets", []):
                    asset_evidence = _evidence(evidence, platform, str(raw_asset.get("url") or lesson_url), captured_at, f"asset:{raw_asset['asset_id']}", raw_ref)
                    lesson["assets"].append({**raw_asset, "lesson_id": lesson["lesson_id"], "evidence": asset_evidence, **_temporal_fields(raw_asset, captured_at, lesson_temporal)})
                for raw_transcript in raw_lesson.get("transcripts", []):
                    transcript_evidence = _evidence(evidence, platform, lesson_url, captured_at, f"transcript:{raw_transcript['transcript_id']}", raw_ref)
                    lesson["transcripts"].append({**raw_transcript, "lesson_id": lesson["lesson_id"], "evidence": transcript_evidence, **_temporal_fields(raw_transcript, captured_at, lesson_temporal)})
                for raw_assignment in raw_lesson.get("assignments", []):
                    assignment_evidence = _evidence(evidence, platform, lesson_url, captured_at, f"assignment:{raw_assignment['assignment_id']}", raw_ref)
                    lesson["assignments"].append({**raw_assignment, "lesson_id": lesson["lesson_id"], "evidence": assignment_evidence, **_temporal_fields(raw_assignment, captured_at, lesson_temporal)})
                for raw_thread in raw_lesson.get("comment_threads", []):
                    thread_evidence = _evidence(evidence, platform, lesson_url, captured_at, f"thread:{raw_thread['thread_id']}", raw_ref)
                    comments = []
                    for raw_comment in raw_thread.get("comments", []):
                        comment_evidence = _evidence(evidence, platform, lesson_url, captured_at, f"comment:{raw_comment['comment_id']}", raw_ref)
                        comments.append({**raw_comment, "thread_id": raw_thread["thread_id"], "evidence": comment_evidence, **_temporal_fields(raw_comment, captured_at, lesson_temporal)})
                    lesson["comment_threads"].append({**raw_thread, "lesson_id": lesson["lesson_id"], "comments": comments, "evidence": thread_evidence, **_temporal_fields(raw_thread, captured_at, lesson_temporal)})
                module["lessons"].append(lesson)
            course["modules"].append(module)
        courses.append(course)
    return {
        "schema": "aoa_course_normalized_bundle_v1",
        "run_id": run_id,
        "source": source,
        "normalized_at": _now(),
        "courses": courses,
        "evidence": list(evidence.values()),
    }


def write_normalized_bundle(bundle: dict[str, object], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "course_bundle.json"
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _evidence(store: dict[str, dict[str, object]], platform: str, source_url: str, fetched_at: str, selector: str, raw_ref: str | None) -> dict[str, object]:
    item = make_evidence(platform, source_url, fetched_at, selector=selector, raw_ref=raw_ref or "")
    store[str(item["evidence_id"])] = item
    return item


def _temporal_fields(raw: dict[str, object], captured_at: str, inherited: dict[str, object] | None = None) -> dict[str, object]:
    inherited = inherited or {}
    fields: dict[str, object] = {}
    for key in ["version_group_id", "valid_from", "valid_until"]:
        value = raw.get(key) if raw.get(key) is not None else inherited.get(key)
        if value:
            fields[key] = value
    observed_at = raw.get("observed_at") or raw.get("updated_at") or raw.get("posted_at") or raw.get("captured_at") or inherited.get("observed_at") or captured_at
    if observed_at:
        fields["observed_at"] = observed_at
    return fields


def _entities(raw_entities: list[object], evidence: dict[str, object]) -> list[dict[str, object]]:
    entities: list[dict[str, object]] = []
    for raw in raw_entities:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "entity")
        value = str(raw.get("value") or "")
        entities.append(
            {
                "entity_id": f"entity:{kind}:{value.casefold()}",
                "kind": kind,
                "value": value,
                "evidence_refs": [str(evidence.get("evidence_id"))],
            }
        )
    return entities


def _progress(raw_course: dict[str, object], captured_at: str, evidence: dict[str, object]) -> dict[str, object]:
    progress = dict(raw_course.get("progress") or {})
    return {
        "progress_id": f"progress:{raw_course['course_id']}",
        "course_id": raw_course["course_id"],
        "state": progress.get("state", "unknown"),
        "updated_at": progress.get("updated_at", captured_at),
        "evidence": evidence,
    }


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
