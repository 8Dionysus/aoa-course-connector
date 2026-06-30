"""Browser-session auth-state helpers.

The live Playwright login flow belongs in the browser optional extra. The base
package exposes planning and inspection helpers without requiring browser
dependencies.
"""

from __future__ import annotations

import json
import shlex
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse


def browser_state_plan(auth_root: Path, platform: str, source_ref: str) -> dict[str, object]:
    state_file = default_browser_state_path(auth_root, platform, source_ref)
    expected_origin = _host_fragment(source_ref)
    inspect_command = f"aoa-course auth inspect-browser-state {str(state_file)!r}"
    capture_command = (
        f"aoa-course auth capture-browser-state {platform} {source_ref!r} "
        f"--login-url <login-or-account-url> --state-file {str(state_file)!r}"
    )
    if expected_origin:
        inspect_command += f" --expect-origin-contains {shlex.quote(expected_origin)}"
        capture_command += f" --expect-origin-contains {shlex.quote(expected_origin)}"
    return {
        "schema": "aoa_course_browser_state_plan_v1",
        "platform": platform,
        "source_ref": source_ref,
        "expected_origin_contains": expected_origin or None,
        "auth_root": str(auth_root),
        "state_file": str(state_file),
        "created_at": _now(),
        "capture_command": capture_command,
        "inspect_command": inspect_command,
        "steps": [
            "install the browser extra when live capture is needed: python -m pip install -e '.[browser]'",
            "run capture-browser-state and log in through the local browser window",
            "confirm the capture or inspect receipt matches the expected source origin without printing cookies or tokens",
            "run discovery, sync, or smoke against the authorized state file",
        ],
        "git_safe": False,
    }


def default_browser_state_path(auth_root: Path, platform: str, source_ref: str) -> Path:
    return auth_root / _slug(platform) / f"{_slug(source_ref)}.storage-state.json"


def inspect_browser_state(state_file: Path, expect_origin_contains: str | None = None) -> dict[str, object]:
    path = state_file.expanduser().resolve()
    base: dict[str, object] = {
        "schema": "aoa_course_browser_state_status_v1",
        "state_file": str(path),
        "exists": path.exists(),
        "git_safe": False,
        "secrets_redacted": True,
    }
    if not path.exists():
        return {**base, "status": "missing", "usable": False}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {**base, "status": "invalid", "usable": False, "error": str(exc)}
    if not isinstance(raw, dict):
        return {**base, "status": "invalid", "usable": False, "error": "storage state root must be a JSON object"}

    cookies = raw.get("cookies") if isinstance(raw.get("cookies"), list) else []
    origins = raw.get("origins") if isinstance(raw.get("origins"), list) else []
    origin_values = [str(item.get("origin")) for item in origins if isinstance(item, dict) and item.get("origin")]
    local_storage_count = sum(_entry_count(item, "localStorage") for item in origins if isinstance(item, dict))
    session_storage_count = sum(_entry_count(item, "sessionStorage") for item in origins if isinstance(item, dict))
    expect_match = None
    if expect_origin_contains:
        expect_match = _storage_state_matches_expected_origin(
            expect_origin_contains,
            origin_values=origin_values,
            cookies=cookies,
        )
    has_session_material = bool(cookies or local_storage_count or session_storage_count)
    status = "ok" if has_session_material else "empty"
    if expect_match is False:
        status = "mismatch"
    stat = path.stat()
    return {
        **base,
        "status": status,
        "usable": status == "ok",
        "size_bytes": stat.st_size,
        "modified_at": _from_timestamp(stat.st_mtime),
        "cookie_count": len(cookies),
        "origin_count": len(origin_values),
        "local_storage_entry_count": local_storage_count,
        "session_storage_entry_count": session_storage_count,
        "expect_origin_contains": expect_origin_contains,
        "expected_origin_matched": expect_match,
    }


def capture_browser_state(
    auth_root: Path,
    platform: str,
    source_ref: str,
    login_url: str,
    *,
    state_file: Path | None = None,
    headless: bool = False,
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 120_000,
    expect_origin_contains: str | None = None,
    pause: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depends on optional extra.
        raise RuntimeError("Install the browser extra first: python -m pip install -e '.[browser]'") from exc

    resolved_state = (state_file or default_browser_state_path(auth_root, platform, source_ref)).expanduser().resolve()
    resolved_state.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(login_url, wait_until=wait_until, timeout=timeout_ms)
            page_info = {"url": page.url, "title": page.title(), "state_file": str(resolved_state)}
            if pause is not None:
                pause(page_info)
            final_info = {"url": page.url, "title": page.title()}
            context.storage_state(path=str(resolved_state))
        finally:
            browser.close()
    expected_origin = expect_origin_contains or _host_fragment(source_ref) or _host_fragment(login_url)
    status = inspect_browser_state(resolved_state, expect_origin_contains=expected_origin or None)
    return {
        "schema": "aoa_course_browser_state_capture_receipt_v1",
        "status": "ok" if status.get("usable") else "warning",
        "platform": platform,
        "source_ref": source_ref,
        "login_url": login_url,
        "expected_origin_contains": expected_origin or None,
        "expected_origin_matched": status.get("expected_origin_matched"),
        "state_file": str(resolved_state),
        "headless": headless,
        "network_touched": True,
        "opened_page": page_info,
        "final_page": final_info,
        "state": status,
    }


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "source"


def _entry_count(mapping: dict[str, object], key: str) -> int:
    entries = mapping.get(key)
    return len(entries) if isinstance(entries, list) else 0


def _storage_state_matches_expected_origin(
    expect_origin_contains: str,
    *,
    origin_values: list[str],
    cookies: list[object],
) -> bool:
    needle = expect_origin_contains.casefold().strip()
    if not needle:
        return True
    if any(_origin_matches_expected_origin(needle, origin) for origin in origin_values):
        return True
    expected_host = _host_fragment(needle)
    if not expected_host:
        return False
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        domain = _host_fragment(str(cookie.get("domain") or ""))
        if domain and _host_domain_matches(expected_host, domain):
            return True
    return False


def _host_fragment(value: str) -> str:
    raw = value.casefold().strip().lstrip(".")
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    host = parsed.hostname or raw.split("/", 1)[0]
    return host.strip().lstrip(".")


def _origin_matches_expected_origin(expected_origin: str, origin: str) -> bool:
    expected = expected_origin.casefold().strip()
    actual = origin.casefold().strip()
    expected_host = _host_fragment(expected)
    actual_host = _host_fragment(actual)
    if not expected_host or not actual_host:
        return False
    expected_parsed = urlparse(expected if "://" in expected else f"//{expected}")
    actual_parsed = urlparse(actual if "://" in actual else f"//{actual}")
    if expected_parsed.scheme and actual_parsed.scheme and expected_parsed.scheme != actual_parsed.scheme:
        return False
    return expected_host == actual_host


def _host_domain_matches(expected_host: str, cookie_domain: str) -> bool:
    return (
        expected_host == cookie_domain
        or expected_host.endswith(f".{cookie_domain}")
    )


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _from_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
