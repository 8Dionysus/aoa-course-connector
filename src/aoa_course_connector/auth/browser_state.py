"""Browser-session route planning.

The live Playwright login flow belongs in the browser optional extra. The base
package exposes the storage and evidence contract without requiring browser
dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def browser_state_plan(auth_root: Path, platform: str, source_ref: str) -> dict[str, object]:
    state_dir = auth_root / platform
    state_file = state_dir / f"{_slug(source_ref)}.storage-state.json"
    return {
        "schema": "aoa_course_browser_state_plan_v1",
        "platform": platform,
        "source_ref": source_ref,
        "auth_root": str(auth_root),
        "state_file": str(state_file),
        "created_at": _now(),
        "steps": [
            "install browser extra when live capture is needed",
            "open platform login in a local browser context",
            "save storage state under AOA_COURSE_AUTH_ROOT",
            "run discovery against the authorized state file",
        ],
        "git_safe": False,
    }


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "source"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
