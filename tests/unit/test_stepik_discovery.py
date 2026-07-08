from __future__ import annotations

from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.discover import discover_stepik_account_browser_state, discover_stepik_account_fixture
from aoa_course_connector.adapters.stepik import client as stepik_client
from aoa_course_connector.sources import load_registry


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_stepik_account_fixture_discovery_registers_sources(tmp_path: Path) -> None:
    storage = roots(tmp_path)

    receipt = discover_stepik_account_fixture(
        storage,
        run_id="stepik-account-discovery-fixture",
        register=True,
        source_limit=2,
    )

    assert receipt["schema"] == "aoa_course_stepik_account_discovery_receipt_v1"
    assert receipt["status"] == "ok"
    assert receipt["network_touched"] is False
    assert receipt["course_count"] == 2
    assert [course["source_ref"] for course in receipt["courses"]] == ["67", "100"]
    assert len(receipt["registered_sources"]) == 2
    registry = load_registry(storage.data)
    refs = {source["source_ref"] for source in registry["sources"]}
    assert refs == {"67", "100"}
    assert {source["access_mode"] for source in registry["sources"]} == {"api_token"}


def test_stepik_account_browser_state_discovery_registers_sources_without_logging_cookie(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    state_file = storage.auth / "stepik" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        """
{
  "cookies": [
    {"name": "sessionid", "value": "SUPER_SECRET_STEPIK_COOKIE", "domain": ".stepik.org", "path": "/"}
  ],
  "origins": [
    {"origin": "https://stepik.org", "localStorage": []}
  ]
}
""".strip(),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakeStepikClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def get_resource(self, resource: str, resource_id: int) -> dict[str, object]:
            assert (resource, resource_id) == ("stepics", 1)
            return {"users": [{"id": 501, "full_name": "Fixture Learner"}]}

        def iter_pages(self, resource: str, params: dict[str, object] | None = None, *, max_pages: int | None = None) -> list[dict[str, object]]:
            if resource == "course-grades":
                return []
            assert resource == "enrollments"
            return [{"id": 7001, "user": 501, "course": 67, "is_active": True}]

        def get_objects(self, resource: str, resource_ids: list[int], *, batch_size: int = 20) -> list[dict[str, object]]:
            assert resource == "courses"
            assert resource_ids == [67]
            return [{"id": 67, "title": "Browser State Course", "canonical_url": "https://stepik.org/course/67"}]

    monkeypatch.setattr(stepik_client, "StepikClient", lambda **kwargs: FakeStepikClient(**kwargs))

    receipt = discover_stepik_account_browser_state(
        storage,
        run_id="stepik-browser-state-discovery",
        state_file=state_file,
        register=True,
    )

    assert receipt["status"] == "ok"
    assert receipt["source_mode"] == "stepik_account_browser_state"
    assert receipt["course_count"] == 1
    assert receipt["network_touched"] is True
    assert receipt["privacy"]["cookie_values_logged"] is False
    assert captured["cookie_header"] == "sessionid=SUPER_SECRET_STEPIK_COOKIE"
    registry = load_registry(storage.data)
    assert registry["sources"][0]["access_mode"] == "browser_session"
    rendered = str(receipt)
    assert "SUPER_SECRET_STEPIK_COOKIE" not in rendered
