"""Browser-session auth-state helpers.

The live Playwright login flow belongs in the browser optional extra. The base
package exposes planning and inspection helpers without requiring browser
dependencies.
"""

from __future__ import annotations

import json
import shlex
import shutil
import sqlite3
import tempfile
from configparser import ConfigParser
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse


TRACKING_COOKIE_PREFIXES = (
    "_ga",
    "_gid",
    "_ym",
    "amplitude",
    "carrotquest",
    "fbp",
    "fbc",
    "intercom",
    "jivo",
    "mindbox",
    "roistat",
    "tmr_",
    "ymex",
)
AUTH_STORAGE_NAME_HINTS = (
    "access",
    "account",
    "auth",
    "identity",
    "jwt",
    "login",
    "member",
    "refresh",
    "session",
    "sid",
    "token",
    "user",
)
STRICT_AUTH_SIGNAL_PLATFORMS = {"getcourse", "skillspace", "stepik"}


def browser_state_plan(auth_root: Path, platform: str, source_ref: str) -> dict[str, object]:
    state_file = default_browser_state_path(auth_root, platform, source_ref)
    expected_origin = _host_fragment(source_ref)
    inspect_command = f"aoa-course auth inspect-browser-state {str(state_file)!r} --platform {platform}"
    capture_command = (
        f"aoa-course auth capture-browser-state {platform} {source_ref!r} "
        f"--login-url <login-or-account-url> --state-file {str(state_file)!r}"
    )
    import_firefox_command = None
    if expected_origin:
        inspect_command += f" --expect-origin-contains {shlex.quote(expected_origin)}"
        capture_command += f" --expect-origin-contains {shlex.quote(expected_origin)}"
        import_firefox_command = (
            f"aoa-course auth import-firefox-state {platform} {source_ref!r} "
            f"--state-file {str(state_file)!r} --expect-origin-contains {shlex.quote(expected_origin)}"
        )
    return {
        "schema": "aoa_course_browser_state_plan_v1",
        "platform": platform,
        "source_ref": source_ref,
        "expected_origin_contains": expected_origin or None,
        "auth_root": str(auth_root),
        "state_file": str(state_file),
        "created_at": _now(),
        "capture_command": capture_command,
        "import_firefox_command": import_firefox_command,
        "inspect_command": inspect_command,
        "steps": [
            "install the browser extra when live capture is needed: python -m pip install -e '.[browser]'",
            "if already logged in through Firefox and import_firefox_command is present, import matching cookies without touching the network",
            "run capture-browser-state and log in through the local browser window",
            "confirm the capture or inspect receipt matches the expected source origin without printing cookies or tokens",
            "run discovery, sync, or smoke against the authorized state file",
        ],
        "git_safe": False,
    }


def default_browser_state_path(auth_root: Path, platform: str, source_ref: str) -> Path:
    return auth_root / _slug(platform) / f"{_slug(source_ref)}.storage-state.json"


def import_firefox_browser_state(
    auth_root: Path,
    platform: str,
    source_ref: str,
    *,
    state_file: Path | None = None,
    profile_dir: Path | None = None,
    profile_name: str | None = None,
    profiles_ini: Path | None = None,
    expect_origin_contains: str | None = None,
) -> dict[str, object]:
    expected_origin = expect_origin_contains or _source_ref_origin_hint(source_ref) or _platform_origin_hint(platform)
    if not expected_origin:
        raise ValueError("provide --expect-origin-contains when source_ref does not contain a host")
    selected_profile, candidates = _select_firefox_profile(
        profile_dir=profile_dir,
        profile_name=profile_name,
        profiles_ini=profiles_ini,
        expected_origin=expected_origin,
    )
    cookies = _firefox_cookies_for_host(selected_profile["path"], expected_origin)
    if not cookies:
        raise ValueError(f"Firefox profile does not contain cookies for {_host_fragment(expected_origin)}")
    resolved_state = (state_file or default_browser_state_path(auth_root, platform, source_ref)).expanduser().resolve()
    resolved_state.parent.mkdir(parents=True, exist_ok=True)
    origin_host = _host_fragment(expected_origin)
    storage_state = {
        "cookies": cookies,
        "origins": [{"origin": f"https://{origin_host}", "localStorage": []}],
    }
    resolved_state.write_text(json.dumps(storage_state, indent=2, sort_keys=True), encoding="utf-8")
    status = inspect_browser_state(resolved_state, expect_origin_contains=expected_origin, platform=platform)
    return {
        "schema": "aoa_course_firefox_state_import_receipt_v1",
        "status": "ok" if status.get("usable") else "warning",
        "platform": platform,
        "source_ref": source_ref,
        "expected_origin_contains": expected_origin,
        "expected_origin_matched": status.get("expected_origin_matched"),
        "state_file": str(resolved_state),
        "firefox_profile": {
            "name": selected_profile.get("name") or "",
            "path": str(selected_profile["path"]),
            "is_default": bool(selected_profile.get("is_default")),
            "matched_cookie_count": len(cookies),
        },
        "candidate_count": len(candidates),
        "network_touched": False,
        "state": status,
        "privacy": {
            "cookie_values_logged": False,
            "local_storage_values_logged": False,
            "token_values_logged": False,
            "do_not_commit_browser_state": True,
        },
    }


def browser_state_cookie_header(state_file: Path, expect_origin_contains: str) -> str:
    """Return a Cookie header for one expected host without exposing values."""

    path = state_file.expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("storage state root must be a JSON object")
    expected_host = _host_fragment(expect_origin_contains)
    if not expected_host:
        raise ValueError("expected browser-state origin host is empty")
    pairs = []
    cookies = raw.get("cookies") if isinstance(raw.get("cookies"), list) else []
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        domain = _host_fragment(str(cookie.get("domain") or ""))
        name = str(cookie.get("name") or "")
        value = cookie.get("value")
        if not domain or not name or value is None:
            continue
        if _host_domain_matches(expected_host, domain):
            pairs.append(f"{name}={value}")
    if not pairs:
        raise ValueError(f"browser storage state does not contain cookies for {expected_host}")
    return "; ".join(pairs)


def inspect_browser_state(state_file: Path, expect_origin_contains: str | None = None, *, platform: str | None = None) -> dict[str, object]:
    path = state_file.expanduser().resolve()
    platform_key = str(platform or "").casefold().strip()
    base: dict[str, object] = {
        "schema": "aoa_course_browser_state_status_v1",
        "state_file": str(path),
        "platform": platform_key or None,
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
    auth_signal = _auth_signal_summary(cookies, origins, platform_key)
    expect_match = None
    if expect_origin_contains:
        expect_match = _storage_state_matches_expected_origin(
            expect_origin_contains,
            origin_values=origin_values,
            cookies=cookies,
        )
    has_session_material = bool(cookies or local_storage_count or session_storage_count)
    status = "ok" if has_session_material else "empty"
    if status == "ok" and platform_key in STRICT_AUTH_SIGNAL_PLATFORMS and not auth_signal["auth_signal_present"]:
        status = "no_auth_signal"
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
        "auth_cookie_count": auth_signal["auth_cookie_count"],
        "tracking_cookie_count": auth_signal["tracking_cookie_count"],
        "auth_storage_entry_count": auth_signal["auth_storage_entry_count"],
        "auth_signal_present": auth_signal["auth_signal_present"],
        "auth_signal_required": auth_signal["auth_signal_required"],
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
    expected_origin = expect_origin_contains or _source_ref_origin_hint(source_ref) or _host_fragment(login_url)
    status = inspect_browser_state(resolved_state, expect_origin_contains=expected_origin or None, platform=platform)
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


def _select_firefox_profile(
    *,
    profile_dir: Path | None,
    profile_name: str | None,
    profiles_ini: Path | None,
    expected_origin: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    if profile_dir is not None:
        path = profile_dir.expanduser().resolve()
        return {"name": path.name, "path": path, "is_default": False}, []
    candidates = _firefox_profile_candidates(profiles_ini=profiles_ini)
    if profile_name:
        matches = [item for item in candidates if item.get("name") == profile_name or Path(str(item.get("path"))).name == profile_name]
        if not matches:
            raise ValueError(f"Firefox profile not found: {profile_name}")
        return matches[0], candidates
    with_host_cookies = [
        item for item in candidates
        if _firefox_cookie_count_for_host(Path(str(item["path"])), expected_origin) > 0
    ]
    if with_host_cookies:
        default_matches = [item for item in with_host_cookies if item.get("is_default")]
        return (default_matches or with_host_cookies)[0], candidates
    default_candidates = [item for item in candidates if item.get("is_default")]
    if default_candidates:
        return default_candidates[0], candidates
    if candidates:
        return candidates[0], candidates
    raise ValueError("Firefox profiles were not found")


def _firefox_profile_candidates(*, profiles_ini: Path | None = None) -> list[dict[str, object]]:
    ini_path = (profiles_ini or Path.home() / ".mozilla/firefox/profiles.ini").expanduser().resolve()
    root = ini_path.parent
    if not ini_path.exists():
        return []
    parser = ConfigParser()
    parser.read(ini_path, encoding="utf-8")
    install_defaults = {
        str(parser[section].get("Default"))
        for section in parser.sections()
        if section.startswith("Install") and parser[section].get("Default")
    }
    candidates = []
    for section in parser.sections():
        if not section.startswith("Profile"):
            continue
        raw_path = str(parser[section].get("Path") or "")
        if not raw_path:
            continue
        is_relative = parser[section].get("IsRelative", "1") == "1"
        path = (root / raw_path if is_relative else Path(raw_path)).expanduser().resolve()
        cookies_db = path / "cookies.sqlite"
        candidates.append(
            {
                "name": parser[section].get("Name") or path.name,
                "path": path,
                "is_default": parser[section].get("Default") == "1" or raw_path in install_defaults,
                "cookies_sqlite_exists": cookies_db.exists(),
                "cookies_sqlite_size": cookies_db.stat().st_size if cookies_db.exists() else 0,
            }
        )
    return sorted(candidates, key=lambda item: (not bool(item.get("is_default")), str(item.get("name") or ""), str(item.get("path") or "")))


def _firefox_cookie_count_for_host(profile_dir: Path, expected_origin: str) -> int:
    try:
        return len(_firefox_cookies_for_host(profile_dir, expected_origin, include_values=False))
    except Exception:
        return 0


def _firefox_cookies_for_host(profile_dir: Path, expected_origin: str, *, include_values: bool = True) -> list[dict[str, object]]:
    cookies_db = profile_dir.expanduser().resolve() / "cookies.sqlite"
    if not cookies_db.exists():
        return []
    expected_host = _host_fragment(expected_origin)
    cookies = []
    with tempfile.TemporaryDirectory(prefix="aoa-course-firefox-cookies-") as temp_dir:
        db_copy = Path(temp_dir) / "cookies.sqlite"
        for suffix in ["", "-wal", "-shm"]:
            source = Path(f"{cookies_db}{suffix}")
            if source.exists():
                shutil.copy2(source, Path(f"{db_copy}{suffix}"))
        connection = sqlite3.connect(db_copy)
        try:
            connection.row_factory = sqlite3.Row
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(moz_cookies)").fetchall()}
            wanted_columns = [
                column
                for column in ["name", "value", "host", "path", "expiry", "isHttpOnly", "isSecure"]
                if column in columns
            ]
            if {"name", "value", "host"} - set(wanted_columns):
                return []
            rows = connection.execute(
                f"SELECT {', '.join(wanted_columns)} FROM moz_cookies WHERE lower(host) LIKE ?",
                (f"%{expected_host.casefold()}%",),
            ).fetchall()
        finally:
            connection.close()
    for row in rows:
        host = str(row["host"] or "")
        if not _host_domain_matches(expected_host, _host_fragment(host)):
            continue
        cookie = {
            "name": str(row["name"] or ""),
            "value": str(row["value"] if include_values else ""),
            "domain": host,
            "path": str(row["path"] or "/"),
            "expires": _playwright_cookie_expires(row["expiry"] if "expiry" in row.keys() else None),
            "httpOnly": bool(row["isHttpOnly"]) if "isHttpOnly" in row.keys() else False,
            "secure": bool(row["isSecure"]) if "isSecure" in row.keys() else False,
        }
        if cookie["name"]:
            cookies.append(cookie)
    return sorted(cookies, key=lambda item: (str(item.get("domain") or ""), str(item.get("path") or ""), str(item.get("name") or "")))


def _playwright_cookie_expires(value: object) -> int:
    if value is None:
        return -1
    try:
        expires = int(value)
    except (TypeError, ValueError):
        return -1
    if expires > 9_999_999_999:
        expires = expires // 1000
    return expires if expires > 0 else -1


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "source"


def _entry_count(mapping: dict[str, object], key: str) -> int:
    entries = mapping.get(key)
    return len(entries) if isinstance(entries, list) else 0


def _auth_signal_summary(cookies: list[object], origins: list[object], platform: str) -> dict[str, object]:
    cookie_names = [
        str(cookie.get("name") or "")
        for cookie in cookies
        if isinstance(cookie, dict) and cookie.get("name")
    ]
    tracking_cookie_count = sum(1 for name in cookie_names if _is_tracking_cookie_name(name))
    auth_cookie_count = sum(1 for name in cookie_names if not _is_tracking_cookie_name(name))
    auth_storage_entry_count = 0
    for origin in origins:
        if not isinstance(origin, dict):
            continue
        for key in ["localStorage", "sessionStorage"]:
            entries = origin.get(key)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict) and _is_auth_storage_name(str(entry.get("name") or "")):
                    auth_storage_entry_count += 1
    auth_signal_required = platform in STRICT_AUTH_SIGNAL_PLATFORMS
    return {
        "auth_cookie_count": auth_cookie_count,
        "tracking_cookie_count": tracking_cookie_count,
        "auth_storage_entry_count": auth_storage_entry_count,
        "auth_signal_present": bool(auth_cookie_count or auth_storage_entry_count),
        "auth_signal_required": auth_signal_required,
    }


def _is_tracking_cookie_name(name: str) -> bool:
    normalized = name.casefold().strip().lstrip(".")
    return any(normalized == prefix or normalized.startswith(prefix) for prefix in TRACKING_COOKIE_PREFIXES)


def _is_auth_storage_name(name: str) -> bool:
    normalized = name.casefold().strip()
    return any(hint in normalized for hint in AUTH_STORAGE_NAME_HINTS)


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


def _source_ref_origin_hint(source_ref: str) -> str:
    host = _host_fragment(source_ref)
    if host in {"account", "default", "browser", "session"}:
        return ""
    return host


def _platform_origin_hint(platform: str) -> str:
    return {"stepik": "stepik.org"}.get(platform.casefold().strip(), "")


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
