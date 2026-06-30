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
        collected: list[dict[str, Any]] = []
        for payload in self.iter_payloads(resource, params, max_pages=max_pages):
            items = payload.get(resource, [])
            if isinstance(items, list):
                collected.extend(dict(item) for item in items if isinstance(item, dict))
        return collected

    def iter_payloads(self, resource: str, params: dict[str, object] | None = None, *, max_pages: int | None = None) -> list[dict[str, Any]]:
        page = 1
        payloads: list[dict[str, Any]] = []
        while True:
            payload = self.get_collection(resource, {**(params or {}), "page": page})
            payloads.append(payload)
            meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
            if not meta.get("has_next"):
                break
            page += 1
            if max_pages is not None and page > max_pages:
                break
        return payloads

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


def fetch_stepik_account_courses(
    *,
    token: str | None,
    base_url: str = DEFAULT_STEPIK_API_BASE,
    timeout: float = 30.0,
    max_pages: int = 5,
    batch_size: int = 20,
) -> dict[str, Any]:
    if not token:
        raise ValueError("Stepik account discovery requires an OAuth/API bearer token")
    client = StepikClient(base_url=base_url, token=token, timeout=timeout)
    current_user = _current_stepik_user(client)
    user_id = _int_or_none(current_user.get("id"))
    enrollment_error = ""
    enrollments: list[dict[str, Any]] = []
    if user_id is not None:
        try:
            enrollments = client.iter_pages("enrollments", {"user": user_id}, max_pages=max_pages)
        except Exception as exc:  # pragma: no cover - Stepik account scopes vary.
            enrollment_error = str(exc)
    course_ids = _course_ids_from_enrollments(enrollments)
    courses_by_id: dict[int, dict[str, Any]] = {}
    if course_ids:
        courses_by_id.update({int(course["id"]): course for course in client.get_objects("courses", course_ids, batch_size=batch_size) if course.get("id") is not None})
    side_loaded_payloads = []
    if not courses_by_id:
        for payload in client.iter_payloads("courses", max_pages=max_pages):
            side_loaded_payloads.append(_payload_summary(payload))
            for enrollment in _payload_items(payload, "enrollments"):
                if user_id is None or _int_or_none(enrollment.get("user")) == user_id:
                    enrollments.append(enrollment)
            wanted = set(_course_ids_from_enrollments(enrollments))
            for course in _payload_items(payload, "courses"):
                course_id = _int_or_none(course.get("id"))
                if course_id is not None and course_id in wanted:
                    courses_by_id[course_id] = course
    courses = [_course_discovery_record(courses_by_id[course_id], enrollments) for course_id in sorted(courses_by_id)]
    return {
        "schema": "aoa_course_stepik_account_discovery_v1",
        "fetched_at": _now(),
        "account": {
            "user_id": user_id,
            "profile": {key: current_user.get(key) for key in ["id", "first_name", "last_name", "full_name", "profile"] if key in current_user},
        },
        "courses": courses,
        "enrollment_count": len(enrollments),
        "limits": {"max_pages": max_pages, "batch_size": batch_size},
        "diagnostics": {
            "enrollment_error": enrollment_error,
            "side_loaded_page_count": len(side_loaded_payloads),
            "side_loaded_pages": side_loaded_payloads,
        },
        "network_touched": True,
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


def _current_stepik_user(client: StepikClient) -> dict[str, Any]:
    payload = client.get_resource("stepics", 1)
    for key in ["users", "stepics"]:
        items = payload.get(key)
        if isinstance(items, list) and items and isinstance(items[0], dict):
            return dict(items[0])
    raise ValueError("Stepik response did not include current user from stepics/1")


def _course_ids_from_enrollments(enrollments: list[dict[str, Any]]) -> list[int]:
    ids = []
    for enrollment in enrollments:
        if not _enrollment_is_active(enrollment):
            continue
        course_id = _int_or_none(enrollment.get("course") or enrollment.get("course_id"))
        if course_id is not None:
            ids.append(course_id)
    return _dedupe_ids(ids)


def _enrollment_is_active(enrollment: dict[str, Any]) -> bool:
    if enrollment.get("is_deleted") is True:
        return False
    if enrollment.get("is_active") is False:
        return False
    return True


def _course_discovery_record(course: dict[str, Any], enrollments: list[dict[str, Any]]) -> dict[str, Any]:
    course_id = int(course["id"])
    enrollment = next(
        (
            item
            for item in enrollments
            if _enrollment_is_active(item)
            and _int_or_none(item.get("course") or item.get("course_id")) == course_id
        ),
        {},
    )
    return {
        "course_id": course_id,
        "source_ref": str(course_id),
        "title": course.get("title") or f"Stepik course {course_id}",
        "slug": course.get("slug"),
        "canonical_url": course.get("canonical_url") or f"https://stepik.org/course/{course_id}",
        "update_date": course.get("update_date"),
        "enrollment": {
            key: enrollment.get(key)
            for key in ["id", "user", "course", "is_active", "is_deleted", "create_date", "update_date"]
            if key in enrollment
        },
    }


def _payload_items(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    items = payload.get(key)
    return [dict(item) for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _payload_summary(payload: dict[str, Any]) -> dict[str, object]:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    return {
        "page": meta.get("page"),
        "has_next": bool(meta.get("has_next")),
        "course_count": len(_payload_items(payload, "courses")),
        "enrollment_count": len(_payload_items(payload, "enrollments")),
    }


def _int_or_none(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
