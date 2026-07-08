"""Compact normalized bundle counters for materialization receipts."""

from __future__ import annotations


def bundle_content_counts(bundle: dict[str, object]) -> dict[str, int]:
    counts = {
        "course_count": 0,
        "module_count": 0,
        "lesson_count": 0,
        "step_count": 0,
        "asset_count": 0,
        "transcript_count": 0,
        "assignment_count": 0,
        "thread_count": 0,
        "comment_count": 0,
        "topic_count": 0,
        "entity_count": 0,
        "evidence_count": len(bundle.get("evidence", [])) if isinstance(bundle.get("evidence"), list) else 0,
    }
    courses = bundle.get("courses") if isinstance(bundle.get("courses"), list) else []
    for course in courses:
        if not isinstance(course, dict):
            continue
        counts["course_count"] += 1
        modules = course.get("modules") if isinstance(course.get("modules"), list) else []
        for module in modules:
            if not isinstance(module, dict):
                continue
            counts["module_count"] += 1
            lessons = module.get("lessons") if isinstance(module.get("lessons"), list) else []
            for lesson in lessons:
                if not isinstance(lesson, dict):
                    continue
                counts["lesson_count"] += 1
                counts["step_count"] += _list_len(lesson.get("steps"))
                counts["asset_count"] += _list_len(lesson.get("assets"))
                counts["transcript_count"] += _list_len(lesson.get("transcripts"))
                counts["assignment_count"] += _list_len(lesson.get("assignments"))
                counts["topic_count"] += _list_len(lesson.get("topics"))
                counts["entity_count"] += _list_len(lesson.get("entities"))
                threads = lesson.get("comment_threads") if isinstance(lesson.get("comment_threads"), list) else []
                counts["thread_count"] += len(threads)
                for thread in threads:
                    if isinstance(thread, dict):
                        counts["comment_count"] += _list_len(thread.get("comments"))
    return counts


def _list_len(value: object) -> int:
    return len(value) if isinstance(value, list) else 0
