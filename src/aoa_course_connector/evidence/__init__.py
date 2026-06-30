"""Evidence helpers."""

from __future__ import annotations

import hashlib


def evidence_id(platform: str, source_url: str, selector: str = "") -> str:
    digest = hashlib.sha1(f"{platform}|{source_url}|{selector}".encode("utf-8")).hexdigest()[:12]
    return f"evidence:{platform}:{digest}"


def make_evidence(platform: str, source_url: str, fetched_at: str, selector: str = "", raw_ref: str = "", confidence: float = 1.0) -> dict[str, object]:
    return {
        "evidence_id": evidence_id(platform, source_url, selector),
        "platform": platform,
        "source_url": source_url,
        "selector": selector,
        "fetched_at": fetched_at,
        "raw_ref": raw_ref,
        "confidence": confidence,
    }
