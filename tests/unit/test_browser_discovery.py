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


def test_catalog_link_pattern_still_rejects_pagination_links() -> None:
    html = """
    <main>
      <a href="/teach/control/stream/view/id/201">Course A</a>
      <a rel="next" href="/teach/control/stream?page=2">Next page</a>
    </main>
    """

    links = discover_course_links(html, "https://school.example/", platform="getcourse", link_pattern="*/teach/control/stream*")

    assert [link["href"] for link in links] == ["https://school.example/teach/control/stream/view/id/201"]


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


def test_getcourse_catalog_discovery_reads_chatium_proxy_training_blocks() -> None:
    raw = {
        "platform": "getcourse",
        "captured_at": "2026-07-08T08:10:00Z",
        "pages": [
            {
                "url": "https://getcourse.ru/c/s/index",
                "title": "GetCourse",
                "html": "<main><div class='ScreenBlock__item-title-left'>Марафон</div></main>",
                "api_payloads": [
                    {
                        "url": "https://app.gcext.su/api/2.0/proxy/https://getcourse.ru/c/s/index",
                        "content_type": "application/json; charset=utf-8",
                        "json": {
                            "success": True,
                            "data": {
                                "blocks": [
                                    {
                                        "type": "screen",
                                        "id": "116/training/911642804",
                                        "title": "Марафон «Точка Старта»",
                                        "onClick": {
                                            "type": "navigate",
                                            "url": "https://getcourse.ru/teach/control/stream/view/id/911642804",
                                        },
                                    },
                                    {
                                        "type": "screen",
                                        "id": "116/training/659592",
                                        "title": "Помощь",
                                        "onClick": {"type": "navigate", "url": "https://getcourse.ru/menublog"},
                                    },
                                ]
                            },
                        },
                    }
                ],
            }
        ],
    }

    discovery = build_browser_catalog_discovery(raw, platform="getcourse")

    assert discovery["course_count"] == 2
    assert [course["title"] for course in discovery["courses"]] == ["Марафон «Точка Старта»", "Помощь"]
    assert [course["source_ref"] for course in discovery["courses"]] == [
        "https://getcourse.ru/teach/control/stream/view/id/911642804",
        "https://getcourse.ru/teach/control/stream/view/id/659592",
    ]
    assert discovery["courses"][0]["source_kind"] == "training"


def test_getcourse_catalog_discovery_reads_canonical_onclick_stream_view_url() -> None:
    raw = {
        "platform": "getcourse",
        "captured_at": "2026-07-08T08:10:00Z",
        "pages": [
            {
                "url": "https://getcourse.ru/c/s/index",
                "title": "GetCourse",
                "html": "<main><div class='ScreenBlock__item-title-left'>Марафон</div></main>",
                "api_payloads": [
                    {
                        "url": "https://app.gcext.su/api/2.0/proxy/https://getcourse.ru/c/s/index",
                        "content_type": "application/json; charset=utf-8",
                        "json": {
                            "data": {
                                "blocks": [
                                    {
                                        "type": "screen",
                                        "id": "opaque-card",
                                        "title": "Курс из onClick",
                                        "onClick": {
                                            "type": "navigate",
                                            "url": "https://getcourse.ru/teach/control/stream/view/id/911642804",
                                        },
                                    }
                                ]
                            }
                        },
                    }
                ],
            }
        ],
    }

    discovery = build_browser_catalog_discovery(raw, platform="getcourse")

    assert discovery["course_count"] == 1
    assert discovery["courses"][0]["source_ref"] == "https://getcourse.ru/teach/control/stream/view/id/911642804"
    assert discovery["courses"][0]["title"] == "Курс из onClick"


def test_getcourse_catalog_discovery_preserves_absolute_onclick_url_before_training_id() -> None:
    raw = {
        "platform": "getcourse",
        "captured_at": "2026-07-08T08:10:00Z",
        "pages": [
            {
                "url": "https://school.example/c/s/index",
                "title": "GetCourse",
                "html": "<main></main>",
                "api_payloads": [
                    {
                        "url": "https://app.gcext.su/api/2.0/proxy/https://school.example/c/s/index",
                        "content_type": "application/json; charset=utf-8",
                        "json": {
                            "data": {
                                "blocks": [
                                    {
                                        "type": "screen",
                                        "id": "116/training/911642804",
                                        "title": "Canonical host",
                                        "onClick": {
                                            "type": "navigate",
                                            "url": "https://getcourse.ru/teach/control/stream/view/id/911642804",
                                        },
                                    }
                                ]
                            }
                        },
                    }
                ],
            }
        ],
    }

    discovery = build_browser_catalog_discovery(
        raw,
        platform="getcourse",
        link_pattern="https://getcourse.ru/teach/control/stream/view/id/*",
    )

    assert discovery["course_count"] == 1
    assert discovery["courses"][0]["source_ref"] == "https://getcourse.ru/teach/control/stream/view/id/911642804"


def test_skillspace_catalog_discovery_reads_student_course_list_payload() -> None:
    raw = {
        "platform": "skillspace",
        "captured_at": "2026-07-08T12:00:00Z",
        "pages": [
            {
                "url": "https://academy.example/school/courses",
                "title": "Skillspace",
                "html": "<main id='app'></main>",
                "api_payloads": [
                    {
                        "url": "https://academy.example/api/rest/student/course/list",
                        "content_type": "application/json; charset=utf-8",
                        "json": [
                            {
                                "uuid": "course-a",
                                "name": "Mobile Debugging",
                                "cover": "https://academy.example/media/cover-a.jpg",
                            },
                            {
                                "course": {
                                    "id": "course-b",
                                    "title": "Radio Diagnostics",
                                },
                                "flow": {"name": "Radio Diagnostics Flow"},
                            },
                            {
                                "url": "/course/course-c",
                                "name": "Firmware Audit",
                            },
                        ],
                    }
                ],
            }
        ],
    }

    discovery = build_browser_catalog_discovery(raw, platform="skillspace")

    assert discovery["course_count"] == 3
    assert [course["title"] for course in discovery["courses"]] == [
        "Mobile Debugging",
        "Radio Diagnostics",
        "Firmware Audit",
    ]
    assert [course["source_ref"] for course in discovery["courses"]] == [
        "https://academy.example/course/course-a",
        "https://academy.example/course/course-b",
        "https://academy.example/course/course-c",
    ]
    assert all(course["source_kind"] == "course" for course in discovery["courses"])


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


def test_live_catalog_page_collector_captures_getcourse_chatium_proxy_json() -> None:
    payload = {
        "success": True,
        "data": {
            "blocks": [
                {
                    "type": "screen",
                    "id": "116/training/300",
                    "title": "Free GetCourse Training",
                    "onClick": {"type": "navigate", "url": "https://getcourse.ru/teach/control/stream/view/id/300"},
                }
            ]
        },
    }
    page = FakePageWithResponses(
        {
            "https://getcourse.ru/c/s/index": (
                "GetCourse",
                "<main><div class='ScreenBlock __clickable'>Free GetCourse Training</div></main>",
            )
        },
        {
            "https://getcourse.ru/c/s/index": [
                FakeResponse(
                    "https://app.gcext.su/api/2.0/proxy/https://getcourse.ru/c/s/index?ccc=1",
                    {"content-type": "application/json; charset=utf-8"},
                    payload,
                )
            ]
        },
    )

    pages = collect_live_catalog_pages(page, "https://getcourse.ru/c/s/index", platform="getcourse")

    assert pages[0]["api_payloads"][0]["json"] == payload
    discovery = build_browser_catalog_discovery({"platform": "getcourse", "pages": pages}, platform="getcourse")
    assert discovery["course_count"] == 1
    assert discovery["courses"][0]["source_ref"] == "https://getcourse.ru/teach/control/stream/view/id/300"


def test_live_catalog_page_collector_captures_skillspace_student_course_list() -> None:
    payload = [
        {
            "uuid": "course-a",
            "name": "Mobile Debugging",
        }
    ]
    page = FakePageWithResponses(
        {
            "https://academy.example/school/courses": (
                "Skillspace",
                "<main id='app'></main>",
            )
        },
        {
            "https://academy.example/school/courses": [
                FakeResponse(
                    "https://academy.example/api/rest/student/course/list",
                    {"content-type": "application/json; charset=utf-8"},
                    payload,
                )
            ]
        },
    )

    pages = collect_live_catalog_pages(page, "https://academy.example/school/courses", platform="skillspace")

    assert pages[0]["api_payloads"][0]["json"] == payload
    discovery = build_browser_catalog_discovery({"platform": "skillspace", "pages": pages}, platform="skillspace")
    assert discovery["course_count"] == 1
    assert discovery["courses"][0]["source_ref"] == "https://academy.example/course/course-a"


def test_skillspace_api_catalog_prefers_nested_course_identity() -> None:
    discovery = build_browser_catalog_discovery(
        {
            "platform": "skillspace",
            "pages": [
                {
                    "url": "https://academy.example/school/courses",
                    "title": "Skillspace",
                    "html": "<main id='app'></main>",
                    "api_payloads": [
                        {
                            "url": "https://academy.example/api/rest/student/course/list",
                            "json": {
                                "items": [
                                    {
                                        "id": "enrollment-1",
                                        "name": "Wrapper title",
                                        "course": {
                                            "id": "course-a",
                                            "title": "Mobile Debugging",
                                        },
                                    }
                                ]
                            },
                        }
                    ],
                }
            ],
        },
        platform="skillspace",
    )

    assert discovery["course_count"] == 1
    assert discovery["courses"][0]["source_ref"] == "https://academy.example/course/course-a"
    assert discovery["courses"][0]["title"] == "Mobile Debugging"


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


class FakeResponse:
    def __init__(self, url: str, headers: dict[str, str], payload: object) -> None:
        self.url = url
        self.headers = headers
        self._payload = payload

    def json(self) -> object:
        return self._payload


class FakePageWithResponses(FakePage):
    def __init__(self, pages: dict[str, tuple[str, str]], responses: dict[str, list[FakeResponse]]) -> None:
        super().__init__(pages)
        self.responses = responses
        self.handlers: dict[str, list[object]] = {}

    def on(self, event: str, callback: object) -> None:
        self.handlers.setdefault(event, []).append(callback)

    def goto(self, url: str, wait_until: str = "networkidle") -> None:
        super().goto(url, wait_until=wait_until)
        for response in self.responses.get(url, []):
            for callback in self.handlers.get("response", []):
                callback(response)  # type: ignore[operator]

    def wait_for_load_state(self, state: str, timeout: int = 0) -> None:
        del state, timeout

    def wait_for_timeout(self, timeout: int) -> None:
        del timeout
