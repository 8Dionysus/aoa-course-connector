"""Small Stepik REST API client.

The adapter intentionally uses the standard library so the clean API path works
for public clones without extra dependencies. Authenticated Stepik access can be
provided with a bearer token when needed; public course reads work without it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_STEPIK_API_BASE = "https://stepik.org/api/"


class StepikClient:
    def __init__(self, base_url: str = DEFAULT_STEPIK_API_BASE, token: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = base_url if base_url.endswith("/") else f"{base_url}/"
        self.token = token
        self.timeout = timeout

    def get_resource(self, resource: str, resource_id: int) -> dict[str, Any]:
        url = urljoin(self.base_url, f"{resource}/{resource_id}")
        request = Request(url, headers=self._headers())
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def first(self, resource: str, resource_id: int) -> dict[str, Any]:
        payload = self.get_resource(resource, resource_id)
        items = payload.get(resource)
        if not isinstance(items, list) or not items:
            raise ValueError(f"Stepik response did not contain {resource}/{resource_id}")
        return dict(items[0])

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "aoa-course-connector/0.1"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers


def fetch_stepik_course(
    course_id: int,
    *,
    token: str | None = None,
    base_url: str = DEFAULT_STEPIK_API_BASE,
    timeout: float = 30.0,
    max_sections: int | None = None,
    max_units_per_section: int | None = None,
    max_steps_per_lesson: int | None = None,
) -> dict[str, Any]:
    client = StepikClient(base_url=base_url, token=token, timeout=timeout)
    course = client.first("courses", course_id)
    sections = []
    section_ids = _limited_ids(course.get("sections", []), max_sections)
    for section_id in section_ids:
        section = client.first("sections", section_id)
        units = []
        unit_ids = _limited_ids(section.get("units", []), max_units_per_section)
        for unit_id in unit_ids:
            unit = client.first("units", unit_id)
            lesson_id = unit.get("lesson")
            lesson = client.first("lessons", int(lesson_id)) if lesson_id else {}
            steps = []
            step_ids = _limited_ids(lesson.get("steps", []), max_steps_per_lesson)
            for step_id in step_ids:
                steps.append(client.first("steps", step_id))
            units.append({"unit": unit, "lesson": lesson, "steps": steps})
        sections.append({"section": section, "units": units})
    return {
        "schema": "aoa_course_stepik_raw_v1",
        "fetched_at": _now(),
        "source": {
            "source_id": f"source:stepik:{course_id}",
            "platform": "stepik",
            "source_ref": str(course_id),
            "access_mode": "public_api" if token is None else "api_token",
            "title": course.get("title") or f"Stepik course {course_id}",
        },
        "course": course,
        "sections": sections,
        "limits": {
            "max_sections": max_sections,
            "max_units_per_section": max_units_per_section,
            "max_steps_per_lesson": max_steps_per_lesson,
        },
    }


def _limited_ids(values: object, limit: int | None) -> list[int]:
    ids = [int(value) for value in values] if isinstance(values, list) else []
    return ids[:limit] if limit is not None else ids


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
