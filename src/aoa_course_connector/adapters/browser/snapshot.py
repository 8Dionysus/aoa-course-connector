"""Dependency-free HTML snapshot extraction for browser-session adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


BLOCK_TAGS = {"title", "h1", "h2", "h3", "h4", "p", "li", "div", "section", "article", "main"}
ASSET_TAGS = {"video", "audio", "source", "iframe", "img", "a"}
ASSET_LINK_EXTENSIONS = {
    ".avi",
    ".csv",
    ".doc",
    ".docx",
    ".gif",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".srt",
    ".txt",
    ".vtt",
    ".wav",
    ".webm",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}
COMMENT_HINTS = {
    "answer",
    "comment",
    "comments",
    "discussion",
    "forum",
    "message",
    "reply",
    "вопрос",
    "коммент",
    "обсужд",
    "ответ",
}
COMMENT_NOISE_TEXTS = {"add comment", "comments", "leave a comment", "добавить комментарий", "комментарии"}
PROGRESS_HINTS = {
    "complete",
    "completed",
    "completion",
    "done",
    "percent",
    "progress",
    "progressbar",
    "status",
    "выполн",
    "заверш",
    "прогресс",
    "пройден",
}
PERCENT_RE = re.compile(r"(?<!\d)(100|\d{1,2})(?:\s*(?:%|percent|процент))", re.IGNORECASE)


@dataclass
class HtmlSnapshot:
    title: str
    text: str
    headings: list[dict[str, str]]
    links: list[dict[str, str]]
    assets: list[dict[str, str]]
    progress: dict[str, str] = field(default_factory=dict)
    comments: list[dict[str, str]] = field(default_factory=list)
    pagination_links: list[dict[str, str]] = field(default_factory=list)


class _SnapshotParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self._stack: list[dict[str, object]] = []
        self._link_stack: list[dict[str, str]] = []
        self.blocks: list[str] = []
        self.title_parts: list[str] = []
        self.headings: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.assets: list[dict[str, str]] = []
        self.progress: dict[str, str] = {}
        self.comments: list[dict[str, str]] = []
        self.pagination_links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if tag in BLOCK_TAGS:
            self._stack.append({"tag": tag, "attrs": attr, "text": []})
        if tag == "a" and attr.get("href"):
            link = {
                "href": urljoin(self.base_url, attr["href"]),
                "text": "",
                "kind": attr.get("data-aoa-kind", ""),
                "module": attr.get("data-aoa-module", ""),
                "title": attr.get("title", ""),
                "rel": attr.get("rel", ""),
            }
            self._link_stack.append(link)
        if tag in ASSET_TAGS:
            src = attr.get("src") or attr.get("href")
            if src:
                kind = attr.get("data-aoa-kind") or tag
                if tag == "a" and kind != "asset" and not _looks_like_asset_link(attr, src):
                    return
                if tag == "a" and kind != "asset":
                    kind = "asset"
                self.assets.append(
                    {
                        "kind": kind,
                        "url": urljoin(self.base_url, src),
                        "title": attr.get("title") or attr.get("alt") or attr.get("download") or src.rsplit("/", 1)[-1],
                    }
                )

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._link_stack:
            link = self._link_stack.pop()
            link["text"] = _clean(link.get("text") or link.get("title") or link.get("href") or "")
            self.links.append(link)
            if _is_pagination_link(link):
                self.pagination_links.append(link)
        if self._stack and self._stack[-1].get("tag") == tag:
            item = self._stack.pop()
            text = _clean(" ".join(str(part) for part in item.get("text", [])))
            attrs = item.get("attrs") if isinstance(item.get("attrs"), dict) else {}
            semantic_text = text or _semantic_label(attrs)
            if not semantic_text and _looks_like_progress_block(tag, attrs, ""):
                semantic_text = _progress_label(attrs, "")
            if semantic_text:
                self._capture_semantic_block(tag, attrs, semantic_text)
            if not text:
                return
            if tag == "title":
                self.title_parts.append(text)
            elif tag in {"h1", "h2", "h3", "h4"}:
                self.headings.append({"level": tag, "text": text, "module": str(attrs.get("data-aoa-module", ""))})
                self.blocks.append(text)
            else:
                self.blocks.append(text)

    def handle_data(self, data: str) -> None:
        text = unescape(data)
        if self._stack:
            self._stack[-1]["text"].append(text)  # type: ignore[index,union-attr]
        if self._link_stack:
            self._link_stack[-1]["text"] = f"{self._link_stack[-1].get('text', '')} {text}".strip()

    def _capture_semantic_block(self, tag: str, attrs: dict[object, object], text: str) -> None:
        kind = str(attrs.get("data-aoa-kind") or "").casefold()
        if _looks_like_progress_block(tag, attrs, text):
            self.progress = {
                "state": _progress_state(attrs, text),
                "percent": _progress_percent(attrs, text),
                "updated_at": str(attrs.get("data-aoa-updated-at") or ""),
                "label": text,
            }
        if kind == "comment" or _looks_like_comment_block(tag, attrs, text):
            self.comments.append(
                {
                    "comment_id": str(attrs.get("data-aoa-comment-id") or attrs.get("id") or f"comment-{len(self.comments) + 1}"),
                    "thread_id": str(attrs.get("data-aoa-thread-id") or attrs.get("data-aoa-comment-thread") or "visible-thread"),
                    "author": str(attrs.get("data-aoa-author") or attrs.get("data-aoa-comment-author") or ""),
                    "created_at": str(attrs.get("data-aoa-created-at") or attrs.get("datetime") or ""),
                    "text": text,
                }
            )


def parse_html_snapshot(html: str, base_url: str) -> HtmlSnapshot:
    parser = _SnapshotParser(base_url)
    parser.feed(html)
    title = parser.headings[0]["text"] if parser.headings else _clean(" ".join(parser.title_parts))
    text = _clean(" ".join(parser.blocks))
    return HtmlSnapshot(
        title=title,
        text=text,
        headings=parser.headings,
        links=parser.links,
        assets=parser.assets,
        progress=parser.progress,
        comments=parser.comments,
        pagination_links=parser.pagination_links,
    )


def _clean(value: str) -> str:
    return " ".join(value.split())


def _looks_like_asset_link(attrs: dict[str, str], href: str) -> bool:
    if "download" in attrs:
        return True
    path = urlparse(href).path.lower()
    return any(path.endswith(extension) for extension in ASSET_LINK_EXTENSIONS)


def _looks_like_progress_block(tag: str, attrs: dict[object, object], text: str) -> bool:
    kind = str(attrs.get("data-aoa-kind") or "").casefold()
    if kind == "progress" or attrs.get("data-aoa-progress-state") or attrs.get("data-aoa-progress-percent"):
        return True
    role = str(attrs.get("role") or "").casefold()
    if role == "progressbar" or attrs.get("aria-valuenow"):
        return True
    haystack = _attribute_haystack(attrs, text)
    if not any(hint in haystack for hint in PROGRESS_HINTS):
        return False
    return bool(_progress_percent(attrs, text)) or tag in {"meter", "progress"}


def _looks_like_comment_block(tag: str, attrs: dict[object, object], text: str) -> bool:
    kind = str(attrs.get("data-aoa-kind") or "").casefold()
    if kind == "comment" or attrs.get("data-aoa-comment-id"):
        return True
    cleaned = _clean(text)
    if len(cleaned) < 8 or len(cleaned) > 1200:
        return False
    if cleaned.casefold() in COMMENT_NOISE_TEXTS or len(cleaned.split()) < 3:
        return False
    attr_text = _attribute_haystack(attrs, "")
    if not any(hint in attr_text for hint in COMMENT_HINTS):
        return False
    return tag in {"article", "div", "li", "p", "section"}


def _attribute_haystack(attrs: dict[object, object], text: str) -> str:
    parts = [text]
    for key in ["class", "id", "role", "aria-label", "data-testid", "data-test", "data-qa", "data-aoa-kind"]:
        value = attrs.get(key)
        if value:
            parts.append(str(value))
    return " ".join(parts).casefold()


def _semantic_label(attrs: dict[object, object]) -> str:
    for key in ["aria-valuetext", "aria-label", "title", "data-aoa-label"]:
        value = attrs.get(key)
        if value:
            return _clean(str(value))
    return ""


def _progress_percent(attrs: dict[object, object], text: str) -> str:
    value = attrs.get("data-aoa-progress-percent") or attrs.get("aria-valuenow")
    if value not in {None, ""}:
        return str(value)
    match = PERCENT_RE.search(text)
    return match.group(1) if match else ""


def _progress_label(attrs: dict[object, object], text: str) -> str:
    label = text or _semantic_label(attrs)
    if label:
        return label
    percent = _progress_percent(attrs, "")
    return f"{percent} percent" if percent else "progress"


def _progress_state(attrs: dict[object, object], text: str) -> str:
    value = attrs.get("data-aoa-progress-state")
    if value:
        return str(value)
    lowered = text.casefold()
    percent = _progress_percent(attrs, text)
    if _is_zero_percent(percent) or any(token in lowered for token in ["not started", "not-started", "not_started", "не нач", "не приступ"]):
        return "not_started"
    if percent == "100" or any(token in lowered for token in ["done", "завершен", "завершено"]):
        return "completed"
    if any(token in lowered for token in ["complete", "completed", "progress", "started", "in progress", "выполн", "прогресс", "пройден"]):
        return "in_progress"
    return "visible"


def _is_zero_percent(value: str) -> bool:
    if value in {"", None}:
        return False
    try:
        return float(str(value).replace(",", ".")) == 0
    except ValueError:
        return False


def _is_pagination_link(link: dict[str, str]) -> bool:
    kind = str(link.get("kind") or "").casefold()
    rel = str(link.get("rel") or "").casefold().split()
    text = str(link.get("text") or "").casefold()
    return kind in {"next", "next-page", "pagination", "pagination-next"} or "next" in rel or text in {"next", "next page", "more"}
