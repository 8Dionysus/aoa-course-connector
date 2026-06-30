"""Dependency-free HTML snapshot extraction for browser-session adapters."""

from __future__ import annotations

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


@dataclass
class HtmlSnapshot:
    title: str
    text: str
    headings: list[dict[str, str]]
    links: list[dict[str, str]]
    assets: list[dict[str, str]]


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
        if self._stack and self._stack[-1].get("tag") == tag:
            item = self._stack.pop()
            text = _clean(" ".join(str(part) for part in item.get("text", [])))
            if not text:
                return
            attrs = item.get("attrs") if isinstance(item.get("attrs"), dict) else {}
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


def parse_html_snapshot(html: str, base_url: str) -> HtmlSnapshot:
    parser = _SnapshotParser(base_url)
    parser.feed(html)
    title = parser.headings[0]["text"] if parser.headings else _clean(" ".join(parser.title_parts))
    text = _clean(" ".join(parser.blocks))
    return HtmlSnapshot(title=title, text=text, headings=parser.headings, links=parser.links, assets=parser.assets)


def _clean(value: str) -> str:
    return " ".join(value.split())


def _looks_like_asset_link(attrs: dict[str, str], href: str) -> bool:
    if "download" in attrs:
        return True
    path = urlparse(href).path.lower()
    return any(path.endswith(extension) for extension in ASSET_LINK_EXTENSIONS)
