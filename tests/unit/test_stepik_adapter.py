from __future__ import annotations

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
    build_keyword_index(storage, run_id="stepik-fixture")
    build_graph(storage, run_id="stepik-fixture")
    results = query_keyword_index(storage, "Stepik public API evidence", run_id="stepik-fixture")
    assert results
    assert results[0]["platform"] == "stepik"
    packet = render_answer_packet(storage, "Stepik public API evidence", run_id="stepik-fixture")
    assert packet["evidence_chain"]


def test_stepik_live_fetches_step_block_sources(monkeypatch) -> None:
    class FakeStepikClient:
        def __init__(self, **_kwargs: object) -> None:
            self.calls: list[tuple[str, int]] = []

        def first(self, resource: str, resource_id: int) -> dict[str, object]:
            self.calls.append((resource, resource_id))
            if resource == "courses":
                return {"id": resource_id, "title": "Demo", "sections": [10]}
            if resource == "sections":
                return {"id": resource_id, "title": "Section", "units": [20]}
            if resource == "units":
                return {"id": resource_id, "lesson": 30, "position": 1}
            if resource == "lessons":
                return {"id": resource_id, "title": "Lesson", "steps": [40]}
            if resource == "steps":
                return {"id": resource_id, "lesson": 30, "position": 1, "block": 50}
            if resource == "blocks":
                return {"id": resource_id, "name": "text", "text": "<p>Live Stepik text</p>"}
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
