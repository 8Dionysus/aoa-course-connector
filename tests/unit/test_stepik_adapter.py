from __future__ import annotations

import json
from pathlib import Path

import aoa_course_connector.ingest.stepik as stepik_ingest
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
    graph_path = build_graph(storage, run_id="stepik-fixture")
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    assignment_id = lesson["assignments"][0]["assignment_id"]
    assert any(node["node_id"] == assignment_id and node["kind"] == "assignment" for node in graph["nodes"])
    assert any(
        edge["kind"] == "lesson_has_assignment"
        and edge["from_node"] == lesson["lesson_id"]
        and edge["to_node"] == assignment_id
        for edge in graph["edges"]
    )
    results = query_keyword_index(storage, "Stepik public API evidence", run_id="stepik-fixture")
    assert results
    assert results[0]["platform"] == "stepik"
    assert results[0]["authority_tier"] == "official_lesson"
    assert results[0]["source_authority"] == "stepik_step_api"
    packet = render_answer_packet(storage, "Stepik public API evidence", run_id="stepik-fixture")
    assert packet["evidence_chain"]
    assert packet["evidence_chain"][0]["platform"] == "stepik"
    assert packet["evidence_chain"][0]["authority_tier"] == "official_lesson"
    assert packet["evidence_chain"][0]["source_authority"] == "stepik_step_api"


def test_stepik_live_fetches_step_block_sources(monkeypatch) -> None:
    class FakeStepikClient:
        def __init__(self, **_kwargs: object) -> None:
            self.calls: list[tuple[str, object]] = []

        def first(self, resource: str, resource_id: int, **_kwargs: object) -> dict[str, object]:
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


def test_stepik_cookie_header_takes_precedence_over_exported_token(monkeypatch) -> None:
    headers = stepik_client.StepikClient(token="TOKEN", cookie_header="sessionid=COOKIE")._headers()
    assert "Authorization" not in headers
    assert headers["Cookie"] == "sessionid=COOKIE"

    class FakeStepikClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def first(self, resource: str, resource_id: int, **_kwargs: object) -> dict[str, object]:
            assert resource == "courses"
            return {"id": resource_id, "title": "Demo", "sections": []}

        def get_objects(self, *_args: object, **_kwargs: object) -> list[dict[str, object]]:
            return []

    instances: list[FakeStepikClient] = []

    def fake_client(**kwargs: object) -> FakeStepikClient:
        instance = FakeStepikClient(**kwargs)
        instances.append(instance)
        return instance

    monkeypatch.setattr(stepik_client, "StepikClient", fake_client)

    raw = stepik_client.fetch_stepik_course(1, token="TOKEN", cookie_header="sessionid=COOKIE")

    assert raw["source"]["access_mode"] == "browser_session"
    assert instances[0].kwargs["token"] == "TOKEN"
    assert instances[0].kwargs["cookie_header"] == "sessionid=COOKIE"


def test_stepik_materialize_state_file_avoids_exported_token(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    state_file = tmp_path / "account.storage-state.json"
    state_file.write_text(
        json.dumps(
            {
                "cookies": [{"name": "sessionid", "value": "COOKIE", "domain": ".stepik.org", "path": "/"}],
                "origins": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("STEPIK_API_TOKEN", "TOKEN")
    captured: dict[str, object] = {}

    def fake_fetch_stepik_course(course_id: int, **kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "schema": "aoa_course_stepik_raw_v1",
            "fetched_at": "2026-07-08T00:00:00Z",
            "source": {
                "source_id": f"source:stepik:{course_id}",
                "platform": "stepik",
                "source_ref": str(course_id),
                "access_mode": "browser_session",
                "title": "Demo",
            },
            "course": {"id": course_id, "title": "Demo", "sections": []},
            "sections": [],
        }

    monkeypatch.setattr(stepik_ingest, "fetch_stepik_course", fake_fetch_stepik_course)

    receipt = stepik_ingest.materialize_stepik_live(storage, course_id=1, run_id="stepik-live", state_file=state_file)

    assert receipt["status"] == "ok"
    assert captured["token"] is None
    assert captured["cookie_header"] == "sessionid=COOKIE"


def test_stepik_live_batches_full_course_and_fetches_step_sources(monkeypatch) -> None:
    class FakeStepikClient:
        def __init__(self, **_kwargs: object) -> None:
            self.calls: list[tuple[str, object]] = []

        def first(self, resource: str, resource_id: int, **_kwargs: object) -> dict[str, object]:
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
    assert raw["coverage"]["schema"] == "aoa_course_ingest_coverage_v1"
    assert raw["coverage"]["status"] == "complete"
    assert raw["coverage"]["complete_for_scope"] is True
    assert raw["coverage"]["inventory_exhausted"] is True
    assert raw["coverage"]["counts"]["referenced_section_count"] == 2
    assert raw["coverage"]["counts"]["fetched_section_count"] == 2
    assert raw["coverage"]["enrichment"]["step_sources"]["status"] == "complete"


def test_stepik_step_source_enrichment_is_bounded(monkeypatch) -> None:
    class FakeStepikClient:
        def __init__(self, **_kwargs: object) -> None:
            self.calls: list[tuple[str, object]] = []

        def first(self, resource: str, resource_id: int, **_kwargs: object) -> dict[str, object]:
            self.calls.append((resource, resource_id))
            if resource == "courses":
                return {"id": resource_id, "title": "Demo", "sections": [10]}
            if resource == "blocks":
                return {"id": resource_id, "name": "text", "text": f"<p>Block {resource_id}</p>"}
            if resource == "step-sources":
                return {"id": resource_id, "block": {"name": "text", "text": f"<p>Source text {resource_id}</p>"}}
            raise AssertionError(resource)

        def get_objects(self, resource: str, resource_ids: list[int], *, batch_size: int = 20) -> list[dict[str, object]]:
            self.calls.append((resource, tuple(resource_ids), batch_size))
            if resource == "sections":
                return [{"id": 10, "title": "First", "units": [20]}]
            if resource == "units":
                return [{"id": 20, "lesson": 30, "position": 1}]
            if resource == "lessons":
                return [{"id": 30, "title": "Lesson", "steps": [40, 41, 42]}]
            if resource == "steps":
                return [{"id": item, "lesson": 30, "position": 1, "block": item + 10} for item in resource_ids]
            raise AssertionError(resource)

    instances: list[FakeStepikClient] = []

    def fake_client(**kwargs: object) -> FakeStepikClient:
        instance = FakeStepikClient(**kwargs)
        instances.append(instance)
        return instance

    monkeypatch.setattr(stepik_client, "StepikClient", fake_client)

    raw = stepik_client.fetch_stepik_course(
        1,
        include_step_sources=True,
        max_step_sources=1,
        step_source_timeout=0.5,
    )

    steps = raw["sections"][0]["units"][0]["steps"]
    assert steps[0]["step_source"]["block"]["text"] == "<p>Source text 40</p>"
    assert steps[1]["step_source_skipped"] == "max_step_sources reached"
    assert steps[2]["step_source_skipped"] == "max_step_sources reached"
    assert raw["limits"]["max_step_sources"] == 1
    assert raw["limits"]["step_source_timeout"] == 0.5
    assert raw["diagnostics"]["step_source_attempt_count"] == 1
    assert raw["diagnostics"]["step_source_skipped_count"] == 2
    assert raw["coverage"]["status"] == "complete"
    assert raw["coverage"]["complete_for_scope"] is True
    assert raw["coverage"]["enrichment"]["step_sources"] == {
        "requested": True,
        "status": "bounded",
        "total_step_count": 3,
        "attempted_count": 1,
        "fetched_count": 1,
        "error_count": 0,
        "skipped_count": 2,
    }
    assert [call for call in instances[0].calls if call[0] == "step-sources"] == [("step-sources", 40)]


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
            if resource == "course-grades":
                return []
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
    assert raw["course_grade_count"] == 0
    assert ("enrollments", {"user": 501}, 3) in instances[0].calls
    assert ("course-grades", {"user": 501}, 3) in instances[0].calls
    assert ("courses", (67, 100), 10) in instances[0].calls


def test_stepik_account_discovery_uses_course_grades_when_enrollments_are_empty(monkeypatch) -> None:
    class FakeStepikClient:
        def __init__(self, **_kwargs: object) -> None:
            self.calls: list[tuple[str, object]] = []

        def get_resource(self, resource: str, resource_id: int) -> dict[str, object]:
            self.calls.append((resource, resource_id))
            assert (resource, resource_id) == ("stepics", 1)
            return {"users": [{"id": 501, "full_name": "Fixture Learner"}]}

        def iter_pages(self, resource: str, params: dict[str, object] | None = None, *, max_pages: int | None = None) -> list[dict[str, object]]:
            self.calls.append((resource, params or {}, max_pages))
            if resource == "enrollments":
                return []
            assert resource == "course-grades"
            return [
                {"id": 9001, "user": 501, "course": 67, "score": "0.0", "last_viewed": "2026-07-08T07:51:00Z"},
                {"id": 9002, "user": 501, "course": 100, "score": "0.5"},
            ]

        def get_objects(self, resource: str, resource_ids: list[int], *, batch_size: int = 20) -> list[dict[str, object]]:
            self.calls.append((resource, tuple(resource_ids), batch_size))
            assert resource == "courses"
            assert resource_ids == [67, 100]
            return [
                {"id": 67, "title": "Course From Grade", "canonical_url": "https://stepik.org/course/67"},
                {"id": 100, "title": "Second Grade Course", "canonical_url": "https://stepik.org/course/100"},
            ]

    instances: list[FakeStepikClient] = []

    def fake_client(**kwargs: object) -> FakeStepikClient:
        instance = FakeStepikClient(**kwargs)
        instances.append(instance)
        return instance

    monkeypatch.setattr(stepik_client, "StepikClient", fake_client)

    raw = stepik_client.fetch_stepik_account_courses(cookie_header="sessionid=secret", max_pages=4, batch_size=10)

    assert [course["source_ref"] for course in raw["courses"]] == ["67", "100"]
    assert raw["enrollment_count"] == 0
    assert raw["course_grade_count"] == 2
    assert raw["courses"][0]["course_grade"]["id"] == 9001
    assert raw["courses"][0]["course_grade"]["last_viewed"] == "2026-07-08T07:51:00Z"
    assert ("course-grades", {"user": 501}, 4) in instances[0].calls
    assert ("courses", (67, 100), 10) in instances[0].calls


def test_stepik_account_discovery_side_loaded_fallback_keeps_only_enrolled_courses(monkeypatch) -> None:
    class FakeStepikClient:
        def get_resource(self, resource: str, resource_id: int) -> dict[str, object]:
            assert (resource, resource_id) == ("stepics", 1)
            return {"users": [{"id": 501, "full_name": "Fixture Learner"}]}

        def iter_pages(self, resource: str, params: dict[str, object] | None = None, *, max_pages: int | None = None) -> list[dict[str, object]]:
            assert resource in {"enrollments", "course-grades"}
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
