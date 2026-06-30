from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.adapters.browser.discovery import build_browser_catalog_discovery, discover_course_links
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.discover import discover_browser_fixture
from aoa_course_connector.discover.browser_session import collect_live_catalog_pages
from aoa_course_connector.sources import load_registry


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_getcourse_catalog_discovery_filters_lesson_links() -> None:
    fixture = json.loads((find_repo_root() / "connector/fixtures/browser/getcourse_catalog_snapshot.json").read_text(encoding="utf-8"))
    page = fixture["pages"][0]
    links = discover_course_links(page["html"], page["url"], platform="getcourse", max_sources=10)
    assert [link["href"] for link in links] == [
        "https://school.example/teach/control/stream/view/id/201",
        "https://school.example/teach/control/stream/view/id/202",
    ]
    discovery = build_browser_catalog_discovery(fixture, platform="getcourse")
    assert discovery["course_count"] == 3
    assert discovery["page_count"] == 2
    assert discovery["pagination"]["next_link_count"] == 1
    assert discovery["pagination"]["next_links"][0]["href"] == "https://school.example/teach/control/stream?page=2"
    assert [course["source_ref"] for course in discovery["courses"]] == [
        "https://school.example/teach/control/stream/view/id/201",
        "https://school.example/teach/control/stream/view/id/202",
        "https://school.example/teach/control/stream/view/id/203",
    ]


def test_catalog_link_pattern_rejects_nonmatching_course_hints() -> None:
    html = """
    <main>
      <a href="/course/allowed">Allowed course</a>
      <a href="/course/noisy">Noisy course</a>
    </main>
    """

    links = discover_course_links(html, "https://academy.example/", platform="skillspace", link_pattern="*/allowed")

    assert [link["href"] for link in links] == ["https://academy.example/course/allowed"]


def test_skillspace_catalog_allows_course_slugs_with_non_course_words() -> None:
    html = """
    <main>
      <a href="/course/lesson-planning">Lesson planning course</a>
      <a href="/lesson/intro">Intro lesson</a>
      <a href="/course/task-design">Task design course</a>
      <a href="/task/123">Task page</a>
    </main>
    """

    links = discover_course_links(html, "https://academy.example/", platform="skillspace", max_sources=10)

    assert [link["href"] for link in links] == [
        "https://academy.example/course/lesson-planning",
        "https://academy.example/course/task-design",
    ]


def test_skillspace_catalog_discovery_registers_sources(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    receipt = discover_browser_fixture(storage, "skillspace", run_id="skillspace-browser-discovery-fixture", register=True)
    assert receipt["status"] == "ok"
    assert receipt["course_count"] == 3
    assert receipt["page_count"] == 2
    assert receipt["pagination"]["next_link_count"] == 1
    assert len(receipt["registered_sources"]) == 3
    registry = load_registry(storage.data)
    sources = registry["sources"]
    assert {source["title"] for source in sources} == {"Firmware Audit", "Mobile Debugging", "Radio Diagnostics"}
    assert all(source["access_mode"] == "browser_session" for source in sources)


def test_live_catalog_page_collector_follows_bounded_next_links() -> None:
    page = FakePage(
        {
            "https://academy.example/courses": (
                "Catalog 1",
                '<main><a data-aoa-kind="course" href="/course/a">A</a><a rel="next" href="/courses?page=2">Next page</a></main>',
            ),
            "https://academy.example/courses?page=2": (
                "Catalog 2",
                '<main><a data-aoa-kind="course" href="/course/b">B</a><a rel="next" href="/courses?page=3">Next page</a></main>',
            ),
            "https://academy.example/courses?page=3": (
                "Catalog 3",
                '<main><a data-aoa-kind="course" href="/course/c">C</a></main>',
            ),
        }
    )

    pages = collect_live_catalog_pages(page, "https://academy.example/courses", wait_until="load", max_pages=2)

    assert [item["url"] for item in pages] == [
        "https://academy.example/courses",
        "https://academy.example/courses?page=2",
    ]
    assert page.visited == ["https://academy.example/courses", "https://academy.example/courses?page=2"]
    discovery = build_browser_catalog_discovery({"platform": "skillspace", "pages": pages}, platform="skillspace")
    assert discovery["course_count"] == 2
    assert discovery["pagination"]["next_link_count"] == 2


class FakePage:
    def __init__(self, pages: dict[str, tuple[str, str]]) -> None:
        self.pages = pages
        self.url = ""
        self.visited: list[str] = []

    def goto(self, url: str, wait_until: str = "networkidle") -> None:
        del wait_until
        self.url = url
        self.visited.append(url)

    def content(self) -> str:
        return self.pages[self.url][1]

    def title(self) -> str:
        return self.pages[self.url][0]
