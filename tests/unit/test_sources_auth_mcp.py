from __future__ import annotations

import os
from pathlib import Path

from aoa_course_connector.auth import browser_state_plan, default_browser_state_path, inspect_browser_state
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index
from aoa_course_connector.ingest import materialize_fixture
from aoa_course_connector.mcp.server import call_tool, tools_manifest
from aoa_course_connector.sources import load_registry, upsert_source
from aoa_course_connector.sync.checkpoints import make_checkpoint, upsert_checkpoint


def test_source_registry_and_browser_plan(tmp_path: Path) -> None:
    source, path, state = upsert_source(tmp_path / "data", "getcourse", "https://school.example", "School")
    assert state == "added"
    assert source["access_mode"] == "browser_session"
    assert path.exists()
    assert load_registry(tmp_path / "data")["sources"]
    plan = browser_state_plan(tmp_path / "auth", "getcourse", "https://school.example")
    assert plan["state_file"]
    assert plan["state_file"] == str(default_browser_state_path(tmp_path / "auth", "getcourse", "https://school.example"))
    assert "capture-browser-state" in plan["capture_command"]
    assert "inspect-browser-state" in plan["inspect_command"]
    assert plan["git_safe"] is False


def test_browser_state_inspect_redacts_secret_material(tmp_path: Path) -> None:
    state_file = tmp_path / "auth" / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        """
{
  "cookies": [
    {
      "name": "session",
      "value": "SUPER_SECRET_COOKIE",
      "domain": ".school.example",
      "path": "/",
      "expires": -1,
      "httpOnly": true,
      "secure": true,
      "sameSite": "Lax"
    }
  ],
  "origins": [
    {
      "origin": "https://school.example",
      "localStorage": [
        {"name": "token", "value": "SUPER_SECRET_TOKEN"}
      ]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    status = inspect_browser_state(state_file, expect_origin_contains="school.example")

    assert status["status"] == "ok"
    assert status["usable"] is True
    assert status["cookie_count"] == 1
    assert status["origin_count"] == 1
    assert status["local_storage_entry_count"] == 1
    assert status["expected_origin_matched"] is True
    rendered = str(status)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_browser_state_inspect_reports_missing_and_origin_mismatch(tmp_path: Path) -> None:
    missing = inspect_browser_state(tmp_path / "missing.storage-state.json")
    assert missing["status"] == "missing"
    assert missing["usable"] is False

    state_file = tmp_path / "account.storage-state.json"
    state_file.write_text('{"cookies": [{"name": "session", "value": "secret"}], "origins": []}', encoding="utf-8")
    mismatch = inspect_browser_state(state_file, expect_origin_contains="school.example")
    assert mismatch["status"] == "mismatch"
    assert mismatch["usable"] is False


def test_stepik_source_defaults_to_public_api(tmp_path: Path) -> None:
    source, _path, state = upsert_source(tmp_path / "data", "stepik", "67", "Stepik Course")
    assert state == "added"
    assert source["access_mode"] == "public_api"


def test_mcp_tools_and_search(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_graph(storage, run_id="starter-fixture")
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))
    assert any(tool["name"] == "search" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "sync_status" for tool in tools_manifest()["tools"])
    result = call_tool("search", {"query": "rollback", "run": "starter-fixture"})
    assert result["results"]
    checkpoint = make_checkpoint(
        source={"source_id": "source:getcourse:test", "platform": "getcourse", "source_ref": "https://school.example", "access_mode": "browser_session"},
        sync_run_id="browser-sync-fixture",
        run_id="browser-sync-fixture-source",
        status="ok",
    )
    upsert_checkpoint(storage, checkpoint)
    sync_status = call_tool("sync_status", {"sync_run": "browser-sync-fixture"})
    assert sync_status["sync"]["ok_count"] == 1
