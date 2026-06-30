"""Adapter registry and platform contracts."""

from __future__ import annotations


ADAPTERS: dict[str, dict[str, object]] = {
    "getcourse": {
        "platform": "getcourse",
        "status": "hard_adapter_scaffold",
        "auth_modes": ["browser_session"],
        "coverage": ["course_tree", "lesson_page", "asset_metadata", "transcripts_when_visible", "comments_when_visible"],
        "notes": "Priority browser-session adapter for authorized GetCourse access.",
    },
    "skillspace": {
        "platform": "skillspace",
        "status": "hard_adapter_scaffold",
        "auth_modes": ["browser_session"],
        "coverage": ["course_tree", "lesson_page", "asset_metadata", "assignments_when_visible", "comments_when_visible"],
        "notes": "Priority browser-session adapter for authorized Skillspace access.",
    },
    "stepik": {
        "platform": "stepik",
        "status": "working_clean_api_adapter",
        "auth_modes": ["public_api", "api_token", "oauth"],
        "coverage": ["course", "sections", "units", "lessons", "steps"],
        "notes": "Working reference API adapter with fixture and bounded live materialization.",
    },
    "moodle": {
        "platform": "moodle",
        "status": "future_clean_lms_adapter",
        "auth_modes": ["api_token"],
        "coverage": ["course_contents", "modules", "files"],
        "notes": "Official LMS web-service route.",
    },
    "canvas": {
        "platform": "canvas",
        "status": "future_clean_lms_adapter",
        "auth_modes": ["api_token", "oauth"],
        "coverage": ["courses", "modules", "pages", "files"],
        "notes": "Official LMS REST route.",
    },
}


def adapter_list() -> list[dict[str, object]]:
    return [ADAPTERS[key] for key in sorted(ADAPTERS)]
