"""Operator-local source registry."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


PLATFORMS = {"getcourse", "skillspace", "stepik", "moodle", "canvas", "coursera", "teachable", "thinkific", "kajabi", "offline_export"}
ACCESS_MODES = {"browser_session", "api_token", "oauth", "offline_export", "public_api"}


def registry_path(data_root: Path) -> Path:
    return data_root / "sources" / "course_sources.json"


def load_registry(data_root: Path) -> dict[str, object]:
    path = registry_path(data_root)
    if not path.exists():
        return {"schema": "aoa_course_source_registry_v1", "sources": []}
    return json.loads(path.read_text(encoding="utf-8"))


def upsert_source(data_root: Path, platform: str, source_ref: str, title: str | None = None, access_mode: str | None = None, enabled: bool = True) -> tuple[dict[str, object], Path, str]:
    if platform not in PLATFORMS:
        raise ValueError(f"unsupported platform: {platform}")
    resolved_access = access_mode or _default_access(platform)
    if resolved_access not in ACCESS_MODES:
        raise ValueError(f"unsupported access mode: {resolved_access}")
    data = load_registry(data_root)
    sources = list(data.get("sources", []))
    source_id = _source_id(platform, source_ref)
    source = {
        "source_id": source_id,
        "platform": platform,
        "source_ref": source_ref,
        "title": title or source_ref,
        "access_mode": resolved_access,
        "enabled": enabled,
        "updated_at": _now(),
    }
    for index, existing in enumerate(sources):
        if existing.get("source_id") == source_id:
            sources[index] = {**existing, **source}
            state = "updated"
            break
    else:
        sources.append(source)
        state = "added"
    data = {"schema": "aoa_course_source_registry_v1", "sources": sorted(sources, key=lambda item: str(item.get("source_id")))}
    path = registry_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return source, path, state


def _default_access(platform: str) -> str:
    if platform in {"getcourse", "skillspace", "coursera", "teachable", "thinkific", "kajabi"}:
        return "browser_session"
    if platform == "stepik":
        return "public_api"
    if platform == "offline_export":
        return "offline_export"
    return "api_token"


def _source_id(platform: str, source_ref: str) -> str:
    digest = hashlib.sha1(f"{platform}|{source_ref}".encode("utf-8")).hexdigest()[:10]
    return f"source:{platform}:{digest}"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
