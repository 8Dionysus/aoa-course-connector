"""Adapter registry and platform contracts."""

from __future__ import annotations


ADAPTERS: dict[str, dict[str, object]] = {
    "getcourse": {
        "platform": "getcourse",
        "status": "working_browser_session_discovery_and_crawl_adapter",
        "auth_modes": ["browser_session"],
        "coverage": ["account_discovery", "source_registry", "course_tree", "lesson_page", "asset_metadata", "transcripts_when_visible", "comments_when_visible"],
        "notes": "Working browser discovery, snapshot, and bounded crawl adapter; live Playwright routes are optional and local-auth gated.",
    },
    "skillspace": {
        "platform": "skillspace",
        "status": "working_browser_session_discovery_and_crawl_adapter",
        "auth_modes": ["browser_session"],
        "coverage": ["account_discovery", "source_registry", "course_tree", "lesson_page", "asset_metadata", "assignments_when_visible", "comments_when_visible"],
        "notes": "Working browser discovery, snapshot, and bounded crawl adapter; live Playwright routes are optional and local-auth gated.",
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
