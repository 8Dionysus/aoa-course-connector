"""Adapter registry and platform contracts."""

from __future__ import annotations


ADAPTERS: dict[str, dict[str, object]] = {
    "getcourse": {
        "platform": "getcourse",
        "status": "working_browser_session_discovery_and_crawl_adapter",
        "auth_modes": ["browser_session"],
        "coverage": ["account_discovery", "live_paginated_discovery", "source_registry", "course_tree", "lesson_page", "asset_metadata", "progress_when_visible", "transcripts_when_visible", "comments_when_visible"],
        "notes": "Working browser discovery, snapshot, progress/comment extraction, and bounded crawl adapter; live Playwright routes are optional and local-auth gated.",
    },
    "skillspace": {
        "platform": "skillspace",
        "status": "working_browser_session_discovery_and_crawl_adapter",
        "auth_modes": ["browser_session"],
        "coverage": ["account_discovery", "live_paginated_discovery", "source_registry", "course_tree", "lesson_page", "asset_metadata", "progress_when_visible", "assignments_when_visible", "comments_when_visible"],
        "notes": "Working browser discovery, snapshot, progress/comment extraction, and bounded crawl adapter; live Playwright routes are optional and local-auth gated.",
    },
    "stepik": {
        "platform": "stepik",
        "status": "working_clean_api_adapter",
        "auth_modes": ["public_api", "api_token", "oauth"],
        "coverage": [
            "course",
            "sections",
            "units",
            "lessons",
            "steps",
            "source_registry_sync",
            "batched_full_course",
            "step_sources_when_authorized",
            "paginated_collections",
        ],
        "notes": (
            "Working reference API adapter with fixture, bounded live smoke, "
            "batched full-course materialization, and optional authenticated "
            "step-source enrichment."
        ),
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
    "coursera": {
        "platform": "coursera",
        "status": "future_platform_adapter",
        "auth_modes": ["browser_session", "oauth"],
        "coverage": ["courses", "modules", "lessons", "asset_metadata", "assignments_when_accessible"],
        "notes": "Future adapter; route depends on operator-owned access and available export/API surfaces.",
    },
    "teachable": {
        "platform": "teachable",
        "status": "future_platform_adapter",
        "auth_modes": ["browser_session", "api_token"],
        "coverage": ["courses", "sections", "lectures", "asset_metadata", "comments_when_visible"],
        "notes": "Future adapter with API/browser-session split depending on school configuration.",
    },
    "thinkific": {
        "platform": "thinkific",
        "status": "future_platform_adapter",
        "auth_modes": ["browser_session", "api_token"],
        "coverage": ["courses", "chapters", "lessons", "asset_metadata", "comments_when_visible"],
        "notes": "Future adapter with API/browser-session split depending on school configuration.",
    },
    "kajabi": {
        "platform": "kajabi",
        "status": "future_platform_adapter",
        "auth_modes": ["browser_session", "api_token"],
        "coverage": ["products", "modules", "posts", "asset_metadata", "comments_when_visible"],
        "notes": "Future adapter with API/browser-session split depending on site configuration.",
    },
}


def adapter_list() -> list[dict[str, object]]:
    return [ADAPTERS[key] for key in sorted(ADAPTERS)]
