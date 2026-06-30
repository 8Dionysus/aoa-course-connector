"""Browser-session adapter helpers."""

from aoa_course_connector.adapters.browser.captions import caption_resource_index, caption_resource_key, caption_text_from_resource, is_caption_asset, parse_caption_sidecar_text, resource_looks_like_caption
from aoa_course_connector.adapters.browser.crawl import build_crawled_snapshot, discover_lesson_links, is_lesson_link, placeholder_lesson_page
from aoa_course_connector.adapters.browser.discovery import build_browser_catalog_discovery, discover_course_links, is_course_link
from aoa_course_connector.adapters.browser.snapshot import HtmlSnapshot, parse_html_snapshot

__all__ = [
    "HtmlSnapshot",
    "build_browser_catalog_discovery",
    "build_crawled_snapshot",
    "caption_resource_index",
    "caption_resource_key",
    "caption_text_from_resource",
    "discover_course_links",
    "discover_lesson_links",
    "is_caption_asset",
    "is_course_link",
    "is_lesson_link",
    "parse_html_snapshot",
    "parse_caption_sidecar_text",
    "placeholder_lesson_page",
    "resource_looks_like_caption",
]
