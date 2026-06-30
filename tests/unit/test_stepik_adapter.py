from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.adapters.stepik import client as stepik_client
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index
from aoa_course_connector.ingest import materialize_stepik_fixture
from aoa_course_connector.query import query_keyword_index, render_answer_packet


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_stepik_fixture_to_answer_packet(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    receipt = materialize_stepik_fixture(storage, run_id="stepik-fixture")
    assert receipt["status"] == "ok"
    bundle = json.loads((storage.data / "runs/stepik-fixture/normalized/course_bundle.json").read_text(encoding="utf-8"))
    lesson = bundle["courses"][0]["modules"][0]["lessons"][0]
    assert lesson["steps"][0]["authority_tier"] == "official_lesson"
    assert lesson["steps"][0]["authority_label"] == "stepik official API"
    assert lesson["steps"][0]["source_authority"] == "stepik_step_api"
    assert lesson["assignments"][0]["authority_tier"] == "official_assignment"
    assert lesson["assignments"][0]["source_authority"] == "stepik_step_api"
    build_keyword_index(storage, run_id="stepik-fixture")
    build_graph(storage, run_id="stepik-fixture")
    results = query_keyword_index(storage, "Stepik public API evidence", run_id="stepik-fixture")
    assert results
    assert results[0]["platform"] == "stepik"
    assert results[0]["authority_tier"] == "official_lesson"
    assert results[0]["source_authority"] == "stepik_step_api"
    packet = render_answer_packet(storage, "Stepik public API evidence", run_id="stepik-fixture")
    assert packet["evidence_chain"]


def test_stepik_live_fetches_step_block_sources(monkeypatch) -> None:
    class FakeStepikClient:
        def __init__(self, **_kwargs: object) -> None:
            self.calls: list[tuple[str, object]] = []

        def first(self, resource: str, resource_id: int) -> dict[str, object]:
            self.calls.append((resource, resource_id))
            if resource == "courses":
                return {"id": resource_id, "title": "Demo", "sections": [10]}
            if resource == "blocks":
                return {"id": resource_id, "name": "text", "text": "<p>Live Stepik text</p>"}
            raise AssertionError(resource)

        def get_objects(self, resource: str, resource_ids: list[int], *, batch_size: int = 20) -> list[dict[str, object]]:
            self.calls.append((resource, tuple(resource_ids)))
            if resource == "sections":
                return [{"id": resource_ids[0], "title": "Section", "units": [20]}]
            if resource == "units":
                return [{"id": resource_ids[0], "lesson": 30, "position": 1}]
            if resource == "lessons":
                return [{"id": resource_ids[0], "title": "Lesson", "steps": [40]}]
            if resource == "steps":
                return [{"id": resource_ids[0], "lesson": 30, "position": 1, "block": 50}]
            raise AssertionError(resource)

    instances: list[FakeStepikClient] = []

    def fake_client(**kwargs: object) -> FakeStepikClient:
        instance = FakeStepikClient(**kwargs)
        instances.append(instance)
        return instance

    monkeypatch.setattr(stepik_client, "StepikClient", fake_client)

    raw = stepik_client.fetch_stepik_course(1)

    step = raw["sections"][0]["units"][0]["steps"][0]
    assert step["block"]["text"] == "<p>Live Stepik text</p>"
    assert ("blocks", 50) in instances[0].calls


def test_stepik_live_batches_full_course_and_fetches_step_sources(monkeypatch) -> None:
    class FakeStepikClient:
        def __init__(self, **_kwargs: object) -> None:
            self.calls: list[tuple[str, object]] = []

        def first(self, resource: str, resource_id: int) -> dict[str, object]:
            self.calls.append((resource, resource_id))
            if resource == "courses":
                return {"id": resource_id, "title": "Demo", "sections": [10, 11]}
            if resource == "blocks":
                return {"id": resource_id, "name": "text", "text": f"<p>Block {resource_id}</p>"}
            if resource == "step-sources":
                return {"id": resource_id, "block": {"name": "text", "text": f"<p>Source text {resource_id}</p>"}}
            raise AssertionError(resource)

        def get_objects(self, resource: str, resource_ids: list[int], *, batch_size: int = 20) -> list[dict[str, object]]:
            self.calls.append((resource, tuple(resource_ids), batch_size))
            if resource == "sections":
                return [
                    {"id": 10, "title": "First", "units": [20]},
                    {"id": 11, "title": "Second", "units": [21]},
                ]
            if resource == "units":
                return [{"id": item, "lesson": item + 10, "position": 1} for item in resource_ids]
            if resource == "lessons":
                return [{"id": item, "title": f"Lesson {item}", "steps": [item + 10]} for item in resource_ids]
            if resource == "steps":
                return [{"id": item, "lesson": item - 10, "position": 1, "block": item + 10} for item in resource_ids]
            raise AssertionError(resource)

    instances: list[FakeStepikClient] = []

    def fake_client(**kwargs: object) -> FakeStepikClient:
        instance = FakeStepikClient(**kwargs)
        instances.append(instance)
        return instance

    monkeypatch.setattr(stepik_client, "StepikClient", fake_client)

    raw = stepik_client.fetch_stepik_course(1, batch_size=2, include_step_sources=True)

    assert len(raw["sections"]) == 2
    assert raw["limits"]["max_sections"] is None
    assert raw["limits"]["include_step_sources"] is True
    first_step = raw["sections"][0]["units"][0]["steps"][0]
    assert first_step["step_source"]["block"]["text"] == "<p>Source text 40</p>"
    assert ("sections", (10, 11), 2) in instances[0].calls
    assert ("step-sources", 40) in instances[0].calls


def test_stepik_client_iter_pages_uses_meta_has_next(monkeypatch) -> None:
    client = stepik_client.StepikClient()
    calls: list[dict[str, object]] = []

    def fake_collection(resource: str, params: dict[str, object] | None = None) -> dict[str, object]:
        assert resource == "courses"
        params = params or {}
        calls.append(params)
        page = int(params["page"])
        return {
            "courses": [{"id": page}],
            "meta": {"has_next": page < 2},
        }

    monkeypatch.setattr(client, "get_collection", fake_collection)

    assert client.iter_pages("courses") == [{"id": 1}, {"id": 2}]
    assert calls == [{"page": 1}, {"page": 2}]


def test_stepik_account_discovery_uses_current_user_enrollments(monkeypatch) -> None:
    class FakeStepikClient:
        def __init__(self, **_kwargs: object) -> None:
            self.calls: list[tuple[str, object]] = []

        def get_resource(self, resource: str, resource_id: int) -> dict[str, object]:
            self.calls.append((resource, resource_id))
            assert (resource, resource_id) == ("stepics", 1)
            return {"users": [{"id": 501, "full_name": "Fixture Learner"}]}

        def iter_pages(self, resource: str, params: dict[str, object] | None = None, *, max_pages: int | None = None) -> list[dict[str, object]]:
            self.calls.append((resource, params or {}, max_pages))
            assert resource == "enrollments"
            return [
                {"id": 7001, "user": 501, "course": 67, "is_active": True},
                {"id": 7002, "user": 501, "course": 100, "is_active": True},
                {"id": 7003, "user": 501, "course": 200, "is_active": False},
                {"id": 7004, "user": 501, "course": 300, "is_deleted": True},
            ]

        def get_objects(self, resource: str, resource_ids: list[int], *, batch_size: int = 20) -> list[dict[str, object]]:
            self.calls.append((resource, tuple(resource_ids), batch_size))
            assert resource == "courses"
            assert resource_ids == [67, 100]
            return [
                {"id": 67, "title": "Stepik API Fixture", "canonical_url": "https://stepik.org/course/67"},
                {"id": 100, "title": "Connected Account Fixture", "canonical_url": "https://stepik.org/course/100"},
            ]

    instances: list[FakeStepikClient] = []

    def fake_client(**kwargs: object) -> FakeStepikClient:
        instance = FakeStepikClient(**kwargs)
        instances.append(instance)
        return instance

    monkeypatch.setattr(stepik_client, "StepikClient", fake_client)

    raw = stepik_client.fetch_stepik_account_courses(token="token", max_pages=3, batch_size=10)

    assert raw["schema"] == "aoa_course_stepik_account_discovery_v1"
    assert raw["account"]["user_id"] == 501
    assert [course["source_ref"] for course in raw["courses"]] == ["67", "100"]
    assert raw["courses"][0]["enrollment"]["id"] == 7001
    assert ("enrollments", {"user": 501}, 3) in instances[0].calls
    assert ("courses", (67, 100), 10) in instances[0].calls


def test_stepik_account_discovery_side_loaded_fallback_keeps_only_enrolled_courses(monkeypatch) -> None:
    class FakeStepikClient:
        def get_resource(self, resource: str, resource_id: int) -> dict[str, object]:
            assert (resource, resource_id) == ("stepics", 1)
            return {"users": [{"id": 501, "full_name": "Fixture Learner"}]}

        def iter_pages(self, resource: str, params: dict[str, object] | None = None, *, max_pages: int | None = None) -> list[dict[str, object]]:
            assert resource == "enrollments"
            return []

        def iter_payloads(self, resource: str, params: dict[str, object] | None = None, *, max_pages: int | None = None) -> list[dict[str, object]]:
            assert resource == "courses"
            return [
                {
                    "courses": [
                        {"id": 67, "title": "Enrolled Course"},
                        {"id": 200, "title": "Public But Not Enrolled"},
                        {"id": 300, "title": "Deleted Enrollment"},
                    ],
                    "enrollments": [
                        {"id": 7001, "user": 501, "course": 67, "is_active": True},
                        {"id": 7002, "user": 501, "course": 200, "is_active": False},
                        {"id": 7003, "user": 501, "course": 300, "is_deleted": True},
                    ],
                    "meta": {"page": 1, "has_next": False},
                }
            ]

    monkeypatch.setattr(stepik_client, "StepikClient", lambda **_kwargs: FakeStepikClient())

    raw = stepik_client.fetch_stepik_account_courses(token="token")

    assert [course["source_ref"] for course in raw["courses"]] == ["67"]
    assert raw["diagnostics"]["side_loaded_page_count"] == 1
