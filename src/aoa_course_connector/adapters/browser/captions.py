"""Caption sidecar helpers for browser-session adapters."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urldefrag, urlsplit, urlunsplit


CAPTION_ASSET_KINDS = {"caption", "captions", "subtitle", "subtitles", "track"}
CAPTION_RESOURCE_EXTENSIONS = (".srt", ".vtt")
CAPTION_CONTENT_TYPE_HINTS = ("text/vtt", "application/x-subrip", "text/srt", "text/plain")
TIMING_LINE_RE = re.compile(r"^\s*(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}\s*-->\s*(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}")
TAG_RE = re.compile(r"<[^>]+>")
STYLE_RE = re.compile(r"\{[^}]+\}")


def is_caption_asset(asset: dict[str, Any]) -> bool:
    kind = str(asset.get("kind") or "").casefold()
    url = str(asset.get("url") or "")
    return kind in CAPTION_ASSET_KINDS or _has_caption_extension(url)


def caption_resource_key(url: str) -> str:
    stripped, _fragment = urldefrag(url)
    parts = urlsplit(stripped)
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def caption_resource_index(raw: dict[str, Any], page: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for container in [raw, page]:
        resources = container.get("resources") if isinstance(container, dict) else None
        if not isinstance(resources, list):
            continue
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            url = str(resource.get("url") or resource.get("source_url") or "")
            if url:
                index[caption_resource_key(url)] = resource
    return index


def caption_text_from_resource(resource: dict[str, Any]) -> str:
    raw_text = str(resource.get("text") or resource.get("body") or resource.get("content") or "")
    return parse_caption_sidecar_text(raw_text)


def parse_caption_sidecar_text(value: str) -> str:
    lines: list[str] = []
    skipping_block = False
    for raw_line in value.replace("\ufeff", "").splitlines():
        line = raw_line.strip()
        if not line:
            skipping_block = False
            continue
        upper = line.upper()
        if upper.startswith("WEBVTT"):
            continue
        if upper.startswith(("NOTE", "STYLE", "REGION")):
            skipping_block = True
            continue
        if skipping_block:
            continue
        if line.isdigit() or TIMING_LINE_RE.match(line) or "-->" in line:
            continue
        cleaned = STYLE_RE.sub(" ", TAG_RE.sub(" ", line))
        cleaned = " ".join(cleaned.split())
        if cleaned and (not lines or lines[-1] != cleaned):
            lines.append(cleaned)
    return " ".join(lines)


def resource_looks_like_caption(url: str, content_type: str) -> bool:
    lowered_content_type = content_type.casefold()
    return _has_caption_extension(url) or any(hint in lowered_content_type for hint in CAPTION_CONTENT_TYPE_HINTS)


def _has_caption_extension(url: str) -> bool:
    path = urlsplit(url).path.casefold()
    return path.endswith(CAPTION_RESOURCE_EXTENSIONS)
