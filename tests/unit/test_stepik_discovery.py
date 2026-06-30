from __future__ import annotations

from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.discover import discover_stepik_account_fixture
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
