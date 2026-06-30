"""Small Stepik REST API client.

The adapter intentionally uses the standard library so the clean API path works
for public clones without extra dependencies. Authenticated Stepik access can be
provided with a bearer token when needed; public course reads work without it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


DEFAULT_STEPIK_API_BASE = "https://stepik.org/api/"


class StepikClient:
    def __init__(self, base_url: str = DEFAULT_STEPIK_API_BASE, token: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = base_url if base_url.endswith("/") else f"{base_url}/"
        self.token = token
        self.timeout = timeout

    def get_resource(self, resource: str, resource_id: int) -> dict[str, Any]:
        url = urljoin(self.base_url, f"{resource}/{resource_id}")
        return self._get_json(url)

    def get_collection(self, resource: str, params: dict[str, object] | None = None) -> dict[str, Any]:
        query = urlencode(params or {}, doseq=True)
        url = urljoin(self.base_url, resource)
        if query:
            url = f"{url}?{query}"
        return self._get_json(url)

    def get_objects(self, resource: str, resource_ids: list[int], *, batch_size: int = 20) -> list[dict[str, Any]]:
        ordered_ids = _dedupe_ids(resource_ids)
        objects: dict[int, dict[str, Any]] = {}
        for batch in _chunks(ordered_ids, max(1, batch_size)):
            payload = self.get_collection(resource, {"ids[]": batch})
            for item in payload.get(resource, []):
                if isinstance(item, dict) and item.get("id") is not None:
                    objects[int(item["id"])] = dict(item)
        return [objects[item] for item in ordered_ids if item in objects]

    def iter_pages(self, resource: str, params: dict[str, object] | None = None, *, max_pages: int | None = None) -> list[dict[str, Any]]:
        page = 1
        collected: list[dict[str, Any]] = []
        while True:
            payload = self.get_collection(resource, {**(params or {}), "page": page})
            items = payload.get(resource, [])
            if isinstance(items, list):
                collected.extend(dict(item) for item in items if isinstance(item, dict))
            meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
            if not meta.get("has_next"):
                break
            page += 1
            if max_pages is not None and page > max_pages:
                break
        return collected

    def _get_json(self, url: str) -> dict[str, Any]:
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
    batch_size: int = 20,
    include_step_sources: bool = False,
) -> dict[str, Any]:
    client = StepikClient(base_url=base_url, token=token, timeout=timeout)
    course = client.first("courses", course_id)
    sections = []
    section_ids = _limited_ids(course.get("sections", []), max_sections)
    for section in client.get_objects("sections", section_ids, batch_size=batch_size):
        units = []
        unit_ids = _limited_ids(section.get("units", []), max_units_per_section)
        unit_items = client.get_objects("units", unit_ids, batch_size=batch_size)
        lesson_ids = _dedupe_ids([int(unit["lesson"]) for unit in unit_items if unit.get("lesson")])
        lesson_by_id = {int(item["id"]): item for item in client.get_objects("lessons", lesson_ids, batch_size=batch_size)}
        for unit in unit_items:
            lesson_id = unit.get("lesson")
            lesson = lesson_by_id.get(int(lesson_id), {}) if lesson_id else {}
            steps = []
            step_ids = _limited_ids(lesson.get("steps", []), max_steps_per_lesson)
            for step in client.get_objects("steps", step_ids, batch_size=batch_size):
                steps.append(_step_with_block(client, step, include_step_sources=include_step_sources))
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
            "batch_size": batch_size,
            "include_step_sources": include_step_sources,
        },
    }


def _dedupe_ids(values: list[int]) -> list[int]:
    seen: set[int] = set()
    ids = []
    for value in values:
        item = int(value)
        if item in seen:
            continue
        seen.add(item)
        ids.append(item)
    return ids


def _limited_ids(values: object, limit: int | None) -> list[int]:
    ids = [int(value) for value in values] if isinstance(values, list) else []
    return ids[:limit] if limit is not None else ids


def _chunks(values: list[int], size: int) -> list[list[int]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _step_with_block(client: StepikClient, step: dict[str, Any], *, include_step_sources: bool = False) -> dict[str, Any]:
    step = dict(step)
    block_ref = step.get("block")
    if not isinstance(block_ref, dict) and block_ref is not None:
        try:
            block_id = int(block_ref)
        except (TypeError, ValueError):
            block_id = 0
        if block_id:
            step["block"] = client.first("blocks", block_id)
    if include_step_sources and step.get("id") is not None:
        try:
            step["step_source"] = client.first("step-sources", int(step["id"]))
        except Exception as exc:  # pragma: no cover - Stepik permissions vary by account
            step["step_source_error"] = str(exc)
    return step


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
