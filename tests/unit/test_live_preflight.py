from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.readiness import live_preflight
from aoa_course_connector.sources import upsert_source


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_live_preflight_reports_stepik_token_without_value(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "stepik", "67", "Stepik API Fixture", access_mode="api_token")
    monkeypatch.setenv("STEPIK_API_TOKEN", "SUPER_SECRET_STEPIK_TOKEN")

    report = live_preflight(storage, platforms=["stepik"], stepik_token_env="STEPIK_API_TOKEN")

    assert report["schema"] == "aoa_course_live_preflight_v1"
    assert report["status"] == "ok"
    assert report["ready"] is True
    assert report["network_touched"] is False
    token_check = next(check for check in report["checks"] if check["kind"] == "token")
    assert token_check["token_present"] is True
    assert token_check["token_value_logged"] is False
    assert "SUPER_SECRET_STEPIK_TOKEN" not in json.dumps(report)


def test_live_preflight_browser_state_readiness_redacts_secret_material(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "getcourse", "https://school.example/teach/control/stream", "School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.example", "path": "/"}],
            "origins": [{"origin": "https://school.example", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )

    report = live_preflight(storage, platforms=["getcourse"], expect_origin_contains="school.example")

    assert report["status"] == "ok"
    assert report["ready"] is True
    state_check = next(check for check in report["checks"] if check["kind"] == "browser_state")
    assert state_check["ready"] is True
    assert state_check["expected_origin_matched"] is True
    assert state_check["cookie_count"] == 1
    assert state_check["local_storage_entry_count"] == 1
    rendered = json.dumps(report)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_live_preflight_reports_missing_browser_state_as_warning(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    upsert_source(storage.data, "skillspace", "https://school.skillspace.example/courses", "School")

    report = live_preflight(storage, platforms=["skillspace"])

    assert report["status"] == "warning"
    assert report["ready"] is False
    assert any(check["kind"] == "browser_state" and check["status"] == "missing" for check in report["checks"])
    assert any("capture-browser-state" in command for command in report["next_commands"])
