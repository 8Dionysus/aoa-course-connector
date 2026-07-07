from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import aoa_course_connector.cli as cli_module
from aoa_course_connector.adapters import adapter_list
from aoa_course_connector.auth import browser_state_plan, capture_browser_state, default_browser_state_path, inspect_browser_state
from aoa_course_connector.calibration.connected_run import run_connected_calibration
from aoa_course_connector.connection_profile import (
    apply_connection_profile,
    build_connection_profile,
    connection_profile_run_plan,
    connection_profile_status,
    inspect_connection_profile,
    load_connection_profile,
    render_connection_profile_runbook,
    write_connection_profile,
    write_connection_profile_runbook,
)
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index, build_semantic_index
from aoa_course_connector.ingest import materialize_fixture
from aoa_course_connector.mcp.server import call_tool, handle_jsonrpc_message, tools_manifest
from aoa_course_connector.readiness import semantic_provider_preflight
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
    assert plan["expected_origin_contains"] == "school.example"
    assert "capture-browser-state" in plan["capture_command"]
    assert "--state-file" in plan["capture_command"]
    assert "--expect-origin-contains school.example" in plan["capture_command"]
    assert "inspect-browser-state" in plan["inspect_command"]
    assert "--expect-origin-contains school.example" in plan["inspect_command"]
    assert plan["git_safe"] is False


def test_connection_profile_plans_and_applies_operator_sources(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(tmp_path / "auth"))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("AOA_COURSE_TEST_EMBEDDING_TOKEN", "SUPER_SECRET_EMBEDDING_TOKEN")
    monkeypatch.setenv("STEPIK_API_TOKEN", "SUPER_SECRET_STEPIK_TOKEN")
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    profile = build_connection_profile(
        storage,
        name="live-courses",
        getcourse_urls=["https://school.example/teach/control/stream"],
        skillspace_urls=["https://academy.example/course/demo"],
        stepik_course_ids=["67"],
        stepik_token_env="STEPIK_API_TOKEN",
        run_id="connected-live-calibration",
        query="course-specific question",
        live_scope="full-course",
        include_step_sources=True,
        semantic_provider="http_json_v1",
        embedding_endpoint="https://embed.example/v1",
        embedding_model="course-embedding",
        embedding_token_env="AOA_COURSE_TEST_EMBEDDING_TOKEN",
    )
    profile_path = tmp_path / "artifacts" / "connections" / "live-courses.connection-profile.json"
    write_receipt = write_connection_profile(profile, profile_path)
    loaded = load_connection_profile(profile_path)
    inspection = inspect_connection_profile(storage, loaded, profile_path=profile_path)

    rendered = json.dumps({"profile": loaded, "inspection": inspection})
    assert write_receipt["written"] is True
    assert loaded["schema"] == "aoa_course_connection_profile_v1"
    assert inspection["schema"] == "aoa_course_connection_profile_inspection_v1"
    assert inspection["network_touched"] is False
    assert inspection["live_readiness"]["schema"] == "aoa_course_connection_profile_readiness_v1"
    assert inspection["live_readiness"]["ready_for_connected_run"] is False
    assert inspection["live_readiness"]["blocked_by"]
    assert inspection["source_registry"]["registered_profile_source_count"] == 0
    assert "SUPER_SECRET_EMBEDDING_TOKEN" not in rendered
    assert "SUPER_SECRET_STEPIK_TOKEN" not in rendered
    assert any("sources add" in command for command in inspection["next_commands"])
    assert any("auth capture-browser-state" in command for command in inspection["next_commands"])
    runbook_text = render_connection_profile_runbook(inspection)
    assert "Course Connection Profile Runbook" in runbook_text
    assert "Browser Auth" in runbook_text
    assert "Live Readiness" in runbook_text
    assert "Semantic Provider" in runbook_text
    assert "SUPER_SECRET_EMBEDDING_TOKEN" not in runbook_text
    runbook = write_connection_profile_runbook(inspection, tmp_path / "artifacts" / "connections" / "live-courses.runbook.md")
    assert runbook["written"] is True
    assert Path(str(runbook["path"])).is_file()

    apply_receipt = apply_connection_profile(storage, loaded, profile_path=profile_path)
    registry = load_registry(storage.data)
    assert apply_receipt["status"] == "ok"
    assert len(apply_receipt["applied"]) == 3
    assert len(registry["sources"]) == 3
    assert apply_receipt["inspection"]["source_registry"]["registered_profile_source_count"] == 3
    status = connection_profile_status(apply_receipt["inspection"])
    assert status["schema"] == "aoa_course_connection_profile_status_v1"
    assert status["live_readiness"]["ready_for_connected_run"] is False
    stepik_plan = next(plan for plan in apply_receipt["inspection"]["connected_plans"] if plan["platform"] == "stepik")
    assert "--stepik-token-env STEPIK_API_TOKEN" in stepik_plan["command"]
    assert "--stepik-token-env STEPIK_API_TOKEN" in stepik_plan["plan"]["connected_run_plan"].get("command", "")

    mcp = call_tool("connection_profile_inspect", {"profile_path": str(profile_path)})
    assert mcp["tool"] == "connection_profile_inspect"
    assert mcp["inspection"]["schema"] == "aoa_course_connection_profile_inspection_v1"
    assert mcp["inspection"]["network_touched"] is False
    mcp_status = call_tool("connection_profile_status", {"profile_path": str(profile_path)})
    assert mcp_status["tool"] == "connection_profile_status"
    assert mcp_status["status"]["schema"] == "aoa_course_connection_profile_status_v1"
    assert mcp_status["status"]["network_touched"] is False


def test_connection_profile_live_readiness_reports_ready_connected_run(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))
    source_url = "https://school.operator.edu/teach/control/stream"
    profile = build_connection_profile(
        storage,
        name="ready-live",
        getcourse_urls=[source_url],
        run_id="connected-live-calibration",
        query="course-specific question",
    )
    state_file = default_browser_state_path(storage.auth, "getcourse", source_url)
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )
    profile_path = tmp_path / "artifacts" / "connections" / "ready-live.connection-profile.json"
    write_connection_profile(profile, profile_path)
    receipt = apply_connection_profile(storage, load_connection_profile(profile_path), profile_path=profile_path)
    readiness = receipt["inspection"]["live_readiness"]
    run_plan = connection_profile_run_plan(profile, receipt["inspection"], platform="getcourse")
    mcp_plan = call_tool("connection_profile_run_plan", {"profile_path": str(profile_path), "platform": "getcourse"})

    assert readiness["ready_for_connected_run"] is True
    assert run_plan["schema"] == "aoa_course_connection_profile_run_plan_v1"
    assert run_plan["ready"] is True
    assert run_plan["platform"] == "getcourse"
    assert run_plan["source_ids"] == [receipt["applied"][0]["source"]["source_id"]]
    assert run_plan["browser_state_file"] == str(state_file)
    assert run_plan["expect_origin_contains"] == "school.operator.edu"
    assert "calibration connected-run --mode live --allow-network" in run_plan["command"]
    assert readiness["registered_source_count"] == 1
    assert readiness["browser_auth_ready_count"] == 1
    assert readiness["ready_connected_plan_count"] == 1
    assert readiness["blocked_by"] == []
    source_id = str(receipt["applied"][0]["source"]["source_id"])
    browser_auth = receipt["inspection"]["browser_auth"][0]
    assert browser_auth["source_id"] == source_id
    assert f"--source-id {source_id}" in browser_auth["preflight_command"]
    assert receipt["inspection"]["connected_plans"][0]["source_ids"] == [source_id]
    assert any("calibration connected-run --mode live --allow-network" in command for command in readiness["connected_run_commands"])
    assert mcp_plan["tool"] == "connection_profile_run_plan"
    assert mcp_plan["run_plan"]["schema"] == "aoa_course_connection_profile_run_plan_v1"
    assert mcp_plan["run_plan"]["ready"] is True
    assert mcp_plan["run_plan"]["network_touched"] is False
    assert mcp_plan["run_plan"]["platform"] == "getcourse"
    assert mcp_plan["run_plan"]["source_ids"] == [source_id]
    assert "calibration connected-run --mode live --allow-network" in mcp_plan["run_plan"]["command"]
    rendered = json.dumps(receipt)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered
    assert "SUPER_SECRET_COOKIE" not in json.dumps(mcp_plan)
    assert "SUPER_SECRET_TOKEN" not in json.dumps(mcp_plan)


def test_connect_run_executes_ready_profile_with_network_gate(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(tmp_path / "auth"))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    source_url = "https://school.operator.edu/teach/control/stream"
    profile = build_connection_profile(
        storage,
        name="ready-run",
        getcourse_urls=[source_url],
        run_id="connected-profile-run",
        query="course-specific question",
        link_pattern="*/lessons/*",
        max_lessons=7,
        max_pages=3,
        max_sources=2,
    )
    state_file = default_browser_state_path(storage.auth, "getcourse", source_url)
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )
    profile_path = tmp_path / "artifacts" / "connections" / "ready-run.connection-profile.json"
    write_connection_profile(profile, profile_path)
    apply_connection_profile(storage, load_connection_profile(profile_path), profile_path=profile_path)
    captured: dict[str, object] = {}

    def fake_run_connected_calibration(roots_arg, **kwargs):
        captured["roots"] = roots_arg
        captured["kwargs"] = kwargs
        return {
            "schema": "aoa_course_connected_calibration_run_receipt_v1",
            "status": "ok",
            "network_touched": True,
            "run_id": kwargs["run_id"],
        }

    monkeypatch.setattr(cli_module, "run_connected_calibration", fake_run_connected_calibration)

    result = cli_module.cmd_connect_run(
        types.SimpleNamespace(
            profile=profile_path,
            platform="getcourse",
            source_id=None,
            allow_network=True,
            require_ready=False,
        )
    )

    output = json.loads(capsys.readouterr().out)
    kwargs = captured["kwargs"]
    assert result == 0
    assert output["schema"] == "aoa_course_connection_profile_run_receipt_v1"
    assert output["status"] == "ok"
    assert output["executed"] is True
    assert output["network_touched"] is True
    assert output["run_plan"]["ready"] is True
    assert output["connected_run"]["run_id"] == "connected-profile-run"
    assert kwargs["run_id"] == "connected-profile-run"
    assert kwargs["platforms"] == ["getcourse"]
    assert kwargs["allow_network"] is True
    assert kwargs["browser_state_file"] == state_file
    assert kwargs["expect_origin_contains"] == "school.operator.edu"
    assert kwargs["link_pattern"] == "*/lessons/*"
    assert kwargs["max_lessons"] == 7
    assert kwargs["max_pages"] == 3
    assert kwargs["max_sources"] == 2
    rendered = json.dumps(output)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_capture_browser_state_receipt_verifies_expected_origin(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "auth" / "getcourse" / "account.storage-state.json"

    class FakePage:
        url = "https://school.example/cms/system/login"

        def goto(self, *_args, **_kwargs) -> None:
            return None

        def title(self) -> str:
            return "Login"

    class FakeContext:
        def new_page(self) -> FakePage:
            return FakePage()

        def storage_state(self, *, path: str) -> None:
            Path(path).write_text(
                json.dumps({
                    "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.example", "path": "/"}],
                    "origins": [{"origin": "https://school.example", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
                }),
                encoding="utf-8",
            )

    class FakeBrowser:
        def new_context(self) -> FakeContext:
            return FakeContext()

        def close(self) -> None:
            return None

    class FakeChromium:
        def launch(self, *, headless: bool = False) -> FakeBrowser:
            assert headless is True
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeSyncPlaywright:
        def __enter__(self) -> FakePlaywright:
            return FakePlaywright()

        def __exit__(self, *_args) -> None:
            return None

    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: FakeSyncPlaywright()
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    receipt = capture_browser_state(
        tmp_path / "auth",
        "getcourse",
        "https://school.example",
        "https://school.example/cms/system/login",
        state_file=state_file,
        headless=True,
        pause=lambda _page_info: None,
    )
    alias = capture_browser_state(
        tmp_path / "auth",
        "getcourse",
        "account",
        "https://school.example/cms/system/login",
        state_file=state_file,
        headless=True,
        pause=lambda _page_info: None,
    )
    mismatch = capture_browser_state(
        tmp_path / "auth",
        "getcourse",
        "account",
        "https://school.example/cms/system/login",
        state_file=state_file,
        headless=True,
        expect_origin_contains="other.example",
        pause=lambda _page_info: None,
    )

    assert receipt["status"] == "ok"
    assert receipt["expected_origin_contains"] == "school.example"
    assert receipt["expected_origin_matched"] is True
    assert receipt["state"]["expected_origin_matched"] is True
    assert alias["status"] == "ok"
    assert alias["expected_origin_contains"] == "school.example"
    assert alias["expected_origin_matched"] is True
    assert mismatch["status"] == "warning"
    assert mismatch["expected_origin_contains"] == "other.example"
    assert mismatch["expected_origin_matched"] is False
    rendered = json.dumps(receipt) + json.dumps(alias) + json.dumps(mismatch)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered


def test_adapter_registry_covers_connector_platform_topology(tmp_path: Path) -> None:
    adapters = {str(adapter["platform"]): adapter for adapter in adapter_list()}
    expected = {
        "getcourse",
        "skillspace",
        "stepik",
        "moodle",
        "canvas",
        "coursera",
        "teachable",
        "thinkific",
        "kajabi",
    }

    assert expected <= set(adapters)
    assert adapters["getcourse"]["status"].startswith("working_")
    assert adapters["skillspace"]["status"].startswith("working_")
    assert adapters["stepik"]["status"] == "working_clean_api_adapter"
    for platform in ["moodle", "canvas", "coursera", "teachable", "thinkific", "kajabi"]:
        assert str(adapters[platform]["status"]).startswith("future_")

    for platform in ["coursera", "teachable", "thinkific", "kajabi"]:
        source, path, state = upsert_source(tmp_path / "data", platform, f"https://{platform}.example/course/demo", platform.title())
        assert state == "added"
        assert source["platform"] == platform
        assert source["access_mode"] == "browser_session"
        assert path.exists()


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


def test_browser_state_inspect_rejects_origin_substring_match(tmp_path: Path) -> None:
    state_file = tmp_path / "account.storage-state.json"
    state_file.write_text(
        json.dumps({
            "cookies": [],
            "origins": [{"origin": "https://my-school.example", "localStorage": [{"name": "token", "value": "secret"}]}],
        }),
        encoding="utf-8",
    )

    status = inspect_browser_state(state_file, expect_origin_contains="school.example")

    assert status["status"] == "mismatch"
    assert status["usable"] is False
    assert status["expected_origin_matched"] is False


def test_browser_state_inspect_matches_expected_origin_from_cookie_domain(tmp_path: Path) -> None:
    state_file = tmp_path / "account.storage-state.json"
    state_file.write_text(
        '{"cookies": [{"name": "session", "value": "secret", "domain": ".school.example", "path": "/"}], "origins": []}',
        encoding="utf-8",
    )

    status = inspect_browser_state(state_file, expect_origin_contains="https://school.example/dashboard")

    assert status["status"] == "ok"
    assert status["usable"] is True
    assert status["cookie_count"] == 1
    assert status["origin_count"] == 0
    assert status["expected_origin_matched"] is True


def test_browser_state_inspect_rejects_subdomain_cookie_for_parent_origin(tmp_path: Path) -> None:
    state_file = tmp_path / "account.storage-state.json"
    state_file.write_text(
        '{"cookies": [{"name": "session", "value": "secret", "domain": ".login.school.example", "path": "/"}], "origins": []}',
        encoding="utf-8",
    )

    status = inspect_browser_state(state_file, expect_origin_contains="https://school.example")

    assert status["status"] == "mismatch"
    assert status["usable"] is False
    assert status["expected_origin_matched"] is False


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
    assert any(tool["name"] == "connector_readiness" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "search" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "sync_status" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "live_preflight" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "connected_source_plan" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "semantic_provider_preflight" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "browser_snapshot_audit" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "connection_profile_run_plan" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "connected_run_status" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "refresh_plan" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "graph_neighbors" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "freshness_report" for tool in tools_manifest()["tools"])
    assert any(tool["name"] == "evidence_report" for tool in tools_manifest()["tools"])
    ingest = call_tool("ingest_status", {"run": "starter-fixture"})
    assert ingest["schema"] == "aoa_course_ingest_status_v1"
    assert ingest["status"] == "ready"
    assert ingest["network_touched"] is False
    assert ingest["readiness"]["agent_query_ready"] is True
    assert ingest["normalized"]["counts"]["courses"] == 1
    assert ingest["normalized"]["counts"]["lessons"] >= 1
    assert ingest["normalized"]["fetched_at"]["latest"] == "2026-06-29T12:00:00Z"
    assert ingest["indexes"]["keyword"]["doc_count"] >= 1
    assert ingest["indexes"]["semantic"]["exists"] is False
    assert ingest["graph"]["node_count"] >= 1
    assert ingest["receipts"][0]["schema"] == "aoa_course_materialize_receipt_v1"
    assert any(command == "aoa-course build-semantic-index --run starter-fixture" for command in ingest["next_commands"])
    missing_ingest = call_tool("ingest_status", {"run": "missing-run"})
    assert missing_ingest["status"] == "missing"
    assert missing_ingest["readiness"]["agent_query_ready"] is False
    assert missing_ingest["next_commands"]
    result = call_tool("search", {"query": "rollback", "run": "starter-fixture"})
    assert result["results"]
    graph = call_tool("graph_neighbors", {"node_id": "lesson:starter:unlock-risk", "run": "starter-fixture"})
    assert graph["graph"]["node"]["node_id"] == "lesson:starter:unlock-risk"
    assert graph["graph"]["neighbors"]
    context = call_tool("lesson_context", {"query": "bootloader rollback", "run": "starter-fixture", "graph_limit": 6})
    assert context["lesson_context"]["schema"] == "aoa_course_lesson_context_packet_v1"
    assert context["answer_packet"]["evidence_chain"]
    assert context["answer_packet"]["quality"]["ready"] is True
    assert context["answer_packet"]["quality"]["evidence_count"] == len(context["answer_packet"]["evidence_chain"])
    assert context["lesson_context"]["answer_packet"] == context["answer_packet"]
    assert context["lesson_context"]["graph_context"] == context["graph_context"]
    assert context["graph_context"]["schema"] == "aoa_course_lesson_graph_context_v1"
    assert context["graph_context"]["status"] == "ready"
    assert context["graph_context"]["contexts"][0]["evidence_id"] == context["answer_packet"]["evidence_chain"][0]["evidence_id"]
    assert context["graph_context"]["contexts"][0]["node_id"] == context["answer_packet"]["evidence_chain"][0]["lesson_id"]
    assert context["graph_context"]["contexts"][0]["graph"]["node"]["kind"] == "lesson"
    assert context["graph_context"]["contexts"][0]["graph"]["neighbors"]
    freshness = call_tool("freshness_report", {"run": "starter-fixture"})
    assert freshness["freshness"]["states"]
    evidence = call_tool("evidence_report", {"query": "rollback", "run": "starter-fixture"})
    assert evidence["evidence_chain"]
    assert evidence["quality"]["schema"] == "aoa_course_answer_quality_summary_v1"
    assert evidence["quality"]["ready"] is True
    assert evidence["quality"]["result_count"] == evidence["result_count"]
    assert evidence["quality"]["evidence_count"] == len(evidence["evidence_chain"])
    assert evidence["quality"]["top_result"]["doc_id"] == evidence["result_refs"][0]["doc_id"]
    assert evidence["freshness_report"]["has_source_timestamps"] is True
    assert evidence["refresh_report"]["local_rebuild_commands"]
    assert evidence["result_refs"][0]["evidence_id"]
    assert evidence["evidence_chain"][0]["freshness_state"]
    assert evidence["evidence_chain"][0]["authority_tier"]
    assert evidence["evidence_chain"][0]["rank_score"] == evidence["result_refs"][0]["rank_score"]
    assert evidence["evidence_chain"][0]["snippet"] == evidence["result_refs"][0]["snippet"]
    assert evidence["result_refs"][0]["rank_features"]["provenance_complete"] is True

    assert evidence["result_refs"][0]["refresh_hint"]["schema"] == "aoa_course_refresh_hint_v1"
    snapshot_audit = call_tool(
        "browser_snapshot_audit",
        {
            "snapshot_path": str(find_repo_root() / "connector/fixtures/browser/getcourse_starter_snapshot.json"),
            "platform": "getcourse",
        },
    )
    rendered_audit = json.dumps(snapshot_audit)
    assert snapshot_audit["tool"] == "browser_snapshot_audit"
    assert snapshot_audit["audit"]["schema"] == "aoa_course_browser_snapshot_audit_v1"
    assert snapshot_audit["audit"]["network_touched"] is False
    assert snapshot_audit["audit"]["readiness"]["ready_for_materialize"] is True
    assert snapshot_audit["audit"]["privacy"]["raw_html_included"] is False
    assert "rollback index" not in rendered_audit
    checkpoint = make_checkpoint(
        source={"source_id": "source:getcourse:test", "platform": "getcourse", "source_ref": "https://school.example", "access_mode": "browser_session"},
        sync_run_id="browser-sync-fixture",
        run_id="browser-sync-fixture-source",
        status="ok",
    )
    upsert_checkpoint(storage, checkpoint)
    sync_status = call_tool("sync_status", {"sync_run": "browser-sync-fixture"})
    assert sync_status["sync"]["ok_count"] == 1
    upsert_source(storage.data, "getcourse", "https://school.example", "School")
    plan = call_tool("connected_source_plan", {"platforms": ["getcourse"], "query": "rollback"})
    assert plan["tool"] == "connected_source_plan"
    assert plan["plan"]["network_touched"] is False
    assert plan["plan"]["live_scope"] == "bounded"
    assert plan["plan"]["source_plans"]
    missing_connected_run = call_tool("connected_run_status", {"run": "missing-connected-run"})
    assert missing_connected_run["tool"] == "connected_run_status"
    assert missing_connected_run["connected_run"]["status"] == "missing"
    run_connected_calibration(storage, mode="fixture", platforms=["stepik"])
    default_connected_run = call_tool("connected_run_status", {})
    assert default_connected_run["tool"] == "connected_run_status"
    assert default_connected_run["connected_run"]["status"] == "ok"
    assert default_connected_run["connected_run"]["run_id"] == "connected-calibration"
    assert default_connected_run["connected_run"]["network_touched"] is False
    run_connected_calibration(storage, run_id="mcp-connected-fixture", mode="fixture", platforms=["stepik"])
    connected_run = call_tool("connected_run_status", {"run": "mcp-connected-fixture"})
    assert connected_run["connected_run"]["schema"] == "aoa_course_connected_calibration_run_status_v1"
    assert connected_run["connected_run"]["status"] == "ok"
    assert connected_run["connected_run"]["network_touched"] is False
    readiness = call_tool("connector_readiness", {"runs": ["starter-fixture"], "connected_run": "mcp-connected-fixture"})
    assert readiness["schema"] == "aoa_course_connector_readiness_v1"
    assert readiness["network_touched"] is False
    assert readiness["operational_ready"] is True
    assert readiness["connected_live_ready"] is False
    assert readiness["connected_live_ready"] == readiness["lanes"]["connected_live_ready"]
    assert readiness["lanes"]["agent_query_ready"] is True
    assert readiness["lanes"]["mcp_tools_ready"] is True
    assert readiness["connected_run"]["status"] == "ok"
    assert readiness["mcp"]["missing_tools"] == []
    assert readiness["runs"][0]["readiness"]["agent_query_ready"] is True
    refresh = call_tool("refresh_plan", {"query": "rollback", "run": "starter-fixture", "mode": "keyword"})
    assert refresh["tool"] == "refresh_plan"
    assert refresh["refresh"]["schema"] == "aoa_course_refresh_cycle_v1"
    assert refresh["refresh"]["status"] == "planned"
    assert refresh["refresh"]["network_touched"] is False
    assert any("lesson-context" in command for command in refresh["refresh"]["planned_commands"]["local_query_commands"])


def test_semantic_provider_preflight_redacts_token_values(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    materialize_fixture(storage, run_id="starter-fixture")

    missing = semantic_provider_preflight(
        storage,
        run_id="starter-fixture",
        provider="http_json_v1",
        embedding_endpoint="https://embed.example/v1",
        embedding_model="course-embedding",
        embedding_token_env="AOA_COURSE_TEST_EMBEDDING_TOKEN",
    )
    assert missing["schema"] == "aoa_course_semantic_provider_preflight_v1"
    assert missing["ready"] is False
    assert missing["network_touched"] is False
    assert missing["provider_config"]["token_env_present"] is False
    assert "export AOA_COURSE_TEST_EMBEDDING_TOKEN=<redacted-token>" in missing["next_commands"]

    monkeypatch.setenv("AOA_COURSE_TEST_EMBEDDING_TOKEN", "SUPER_SECRET_EMBEDDING_TOKEN")
    ready = semantic_provider_preflight(
        storage,
        run_id="starter-fixture",
        provider="http_json_v1",
        embedding_endpoint="https://embed.example/v1",
        embedding_model="course-embedding",
        embedding_token_env="AOA_COURSE_TEST_EMBEDDING_TOKEN",
    )
    serialized = json.dumps(ready, sort_keys=True)
    assert ready["ready"] is True
    assert ready["provider_config"]["token_env_present"] is True
    assert ready["provider_config"]["secret_values_logged"] is False
    assert "SUPER_SECRET_EMBEDDING_TOKEN" not in serialized
    assert "build-semantic-index --run starter-fixture --provider http_json_v1" in ready["commands"]["build"]

    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))
    readiness = call_tool(
        "connector_readiness",
        {
            "runs": ["starter-fixture"],
            "semantic_provider": "http_json_v1",
            "embedding_endpoint": "https://embed.example/v1",
            "embedding_model": "course-embedding",
            "embedding_token_env": "AOA_COURSE_TEST_EMBEDDING_TOKEN",
        },
    )
    assert any(
        "build-semantic-index --run starter-fixture --provider http_json_v1" in command
        for command in readiness["next_commands"]
    )
    semantic_build_commands = [
        command
        for command in readiness["next_commands"]
        if command.startswith("aoa-course build-semantic-index --run starter-fixture")
    ]
    assert semantic_build_commands
    assert all("--provider http_json_v1" in command for command in semantic_build_commands)
    assert not any("build-semantic-index --run starter-fixture --provider local_hashing" in command for command in readiness["next_commands"])


def test_ingest_status_treats_corrupt_artifacts_as_not_ready(tmp_path: Path, monkeypatch) -> None:
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
    keyword_path = storage.artifact / "runs" / "starter-fixture" / "indexes" / "keyword_index.json"
    keyword_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    ingest = call_tool("ingest_status", {"run": "starter-fixture"})

    assert ingest["status"] == "partial"
    assert ingest["indexes"]["keyword"]["status"] == "error"
    assert ingest["readiness"]["query_ready"] is False
    assert ingest["readiness"]["agent_query_ready"] is False
    assert any(command == "aoa-course build-index --run starter-fixture" for command in ingest["next_commands"])


def test_connector_readiness_uses_selected_connected_run_in_remediation(tmp_path: Path, monkeypatch) -> None:
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

    readiness = call_tool("connector_readiness", {"runs": ["starter-fixture"], "connected_run": "custom-connected-run"})

    assert readiness["connected_run"]["status"] == "missing"
    assert readiness["connected_run"]["run_id"] == "custom-connected-run"
    assert any(
        command == "aoa-course bootstrap fixture --connected-run custom-connected-run"
        for command in readiness["next_commands"]
    )
    assert not any("--connected-run connected-calibration" in command for command in readiness["next_commands"])


def test_connector_readiness_surfaces_partial_connected_run_repair_lanes(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_semantic_index(storage, run_id="starter-fixture")
    build_graph(storage, run_id="starter-fixture")
    upsert_source(storage.data, "stepik", "https://stepik.org/course/67/syllabus", "Stepik Public", access_mode="public_api")
    run_connected_calibration(storage, run_id="partial-connected-run", mode="live", platforms=["stepik"])
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    readiness = call_tool(
        "connector_readiness",
        {"runs": ["starter-fixture"], "platforms": ["stepik"], "connected_run": "partial-connected-run"},
    )

    assert readiness["connected_run"]["status"] == "partial"
    assert readiness["connected_run"]["repair_lanes"][0]["lane"] == "network_gate"
    assert readiness["lanes"]["connected_run_receipt_ready"] is False
    assert any(command.startswith("aoa-course preflight connected-plan --platform stepik") for command in readiness["next_commands"])
    assert any("aoa-course calibration connected-run --mode live --allow-network --run partial-connected-run" in command for command in readiness["next_commands"])
    assert not any(
        "aoa-course calibration connected-run --mode live --allow-network --run connected-live-calibration" in command
        for command in readiness["next_commands"]
    )
    assert not any(command == "aoa-course bootstrap fixture --connected-run partial-connected-run" for command in readiness["next_commands"])


def test_mcp_live_preflight_reports_readiness_without_secret_values(tmp_path: Path, monkeypatch) -> None:
    storage = StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )
    upsert_source(storage.data, "getcourse", "https://school.operator.edu/teach/control/stream", "School")
    state_file = storage.auth / "getcourse" / "account.storage-state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "session", "value": "SUPER_SECRET_COOKIE", "domain": ".school.operator.edu", "path": "/"}],
            "origins": [{"origin": "https://school.operator.edu", "localStorage": [{"name": "token", "value": "SUPER_SECRET_TOKEN"}]}],
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    result = call_tool(
        "live_preflight",
        {"platforms": ["getcourse"], "state_file": str(state_file), "expect_origin": "school.operator.edu"},
    )

    assert result["tool"] == "live_preflight"
    assert result["preflight"]["ready"] is True
    assert result["preflight"]["network_touched"] is False
    rendered = json.dumps(result)
    assert "SUPER_SECRET_COOKIE" not in rendered
    assert "SUPER_SECRET_TOKEN" not in rendered

    plan = call_tool(
        "connected_source_plan",
        {
            "platforms": ["getcourse"],
            "state_file": str(state_file),
            "expect_origin": "school.operator.edu",
            "link_pattern": "*/lessons/*",
            "max_lessons": 7,
            "max_pages": 3,
            "max_sources": 4,
        },
    )

    assert plan["tool"] == "connected_source_plan"
    assert plan["plan"]["ready"] is True
    assert plan["plan"]["link_pattern"] == "*/lessons/*"
    assert plan["plan"]["live_scope"] == "bounded"
    assert plan["plan"]["include_step_sources"] is False
    assert plan["plan"]["max_lessons"] == 7
    assert plan["plan"]["max_pages"] == 3
    assert plan["plan"]["max_sources"] == 4
    assert any("smoke browser-live" in command for command in plan["plan"]["next_commands"])
    assert any("--link-pattern '*/lessons/*'" in command for command in plan["plan"]["next_commands"])
    assert any("--max-lessons 7" in command for command in plan["plan"]["next_commands"])
    assert any("--max-pages 3" in command for command in plan["plan"]["next_commands"])
    assert any("--max-sources 4" in command for command in plan["plan"]["next_commands"])
    assert "calibration connected-run --mode live --allow-network" in plan["plan"]["connected_run_plan"]["command"]
    assert "--link-pattern '*/lessons/*'" in plan["plan"]["connected_run_plan"]["command"]
    assert "--max-lessons 7" in plan["plan"]["connected_run_plan"]["command"]
    assert "--max-pages 3" in plan["plan"]["connected_run_plan"]["command"]
    assert "--max-sources 4" in plan["plan"]["connected_run_plan"]["command"]
    plan = plan["plan"]["browser_auth_plans"][0]
    assert plan["ready"] is True
    assert plan["source_hosts"] == ["school.operator.edu"]
    assert "capture-browser-state getcourse account" in plan["commands"]["capture"]
    assert plan["state_file_candidates"][0]["host"] == "school.operator.edu"
    assert plan["state_file_candidates"][0]["state_file"].endswith("/getcourse/school-operator-edu.storage-state.json")
    assert plan["state_file_candidates"][0]["selected_by_default"] is False
    assert "--expect-origin-contains school.operator.edu" in plan["state_file_candidates"][0]["commands"]["capture"]
    rendered_plan = json.dumps(plan)
    assert "SUPER_SECRET_COOKIE" not in rendered_plan
    assert "SUPER_SECRET_TOKEN" not in rendered_plan

    readiness = call_tool(
        "connector_readiness",
        {
            "platforms": ["getcourse"],
            "state_file": str(state_file),
            "expect_origin": "school.operator.edu",
            "query": "course-specific question",
            "link_pattern": "*/lessons/*",
            "max_lessons": 7,
            "max_pages": 3,
            "max_sources": 4,
            "live_scope": "bounded",
        },
    )
    assert readiness["connected_live_ready"] is True
    assert readiness["connected_live_ready"] == readiness["lanes"]["connected_live_ready"]
    compact_plan = readiness["connected_source_plan"]
    assert compact_plan["link_pattern"] == "*/lessons/*"
    assert compact_plan["live_scope"] == "bounded"
    assert compact_plan["include_step_sources"] is False
    assert compact_plan["max_lessons"] == 7
    assert compact_plan["max_pages"] == 3
    assert compact_plan["max_sources"] == 4
    assert compact_plan["connected_run_plan"]["ready"] is True
    assert "--link-pattern '*/lessons/*'" in compact_plan["connected_run_plan"]["command"]
    assert "--max-lessons 7" in compact_plan["connected_run_plan"]["command"]
    assert "--max-pages 3" in compact_plan["connected_run_plan"]["command"]
    assert "--max-sources 4" in compact_plan["connected_run_plan"]["command"]
    assert any("calibration connected-run --mode live --allow-network" in command for command in readiness["next_commands"])
    assert any("--link-pattern '*/lessons/*'" in command for command in readiness["next_commands"] if "calibration connected-run" in command)
    assert any("--max-lessons 7" in command for command in readiness["next_commands"] if "calibration connected-run" in command)
    assert any("--max-pages 3" in command for command in readiness["next_commands"] if "calibration connected-run" in command)
    assert any("--max-sources 4" in command for command in readiness["next_commands"] if "calibration connected-run" in command)


def test_mcp_jsonrpc_initialize_list_and_call(tmp_path: Path, monkeypatch) -> None:
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

    initialize = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
    })
    unsupported_initialize = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "initialize",
        "params": {"protocolVersion": "1900-01-01", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
    })
    assert initialize["result"]["protocolVersion"] == "2025-11-25"
    assert unsupported_initialize["result"]["protocolVersion"] == "2025-11-25"
    assert initialize["result"]["serverInfo"]["name"] == "aoa-course-connector-mcp"
    assert initialize["result"]["capabilities"]["tools"]["listChanged"] is False
    assert handle_jsonrpc_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None

    listed = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    readiness_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "connector_readiness")
    search_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "search")
    preflight_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "live_preflight")
    connected_plan_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "connected_source_plan")
    profile_run_plan_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "connection_profile_run_plan")
    semantic_provider_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "semantic_provider_preflight")
    browser_snapshot_audit_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "browser_snapshot_audit")
    connected_run_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "connected_run_status")
    evidence_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "evidence_report")
    lesson_context_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "lesson_context")
    refresh_tool = next(tool for tool in listed["result"]["tools"] if tool["name"] == "refresh_plan")
    assert "runs" in readiness_tool["inputSchema"]["properties"]
    assert "link_pattern" in readiness_tool["inputSchema"]["properties"]
    assert readiness_tool["inputSchema"]["properties"]["live_scope"]["enum"] == ["bounded", "full-course"]
    assert "include_step_sources" in readiness_tool["inputSchema"]["properties"]
    assert "max_lessons" in readiness_tool["inputSchema"]["properties"]
    assert "max_pages" in readiness_tool["inputSchema"]["properties"]
    assert "max_sources" in readiness_tool["inputSchema"]["properties"]
    assert search_tool["inputSchema"]["required"] == ["query"]
    assert "platforms" in preflight_tool["inputSchema"]["properties"]
    assert "calibration_run" in connected_plan_tool["inputSchema"]["properties"]
    assert connected_plan_tool["inputSchema"]["properties"]["live_scope"]["enum"] == ["bounded", "full-course"]
    assert "include_step_sources" in connected_plan_tool["inputSchema"]["properties"]
    assert "link_pattern" in connected_plan_tool["inputSchema"]["properties"]
    assert profile_run_plan_tool["inputSchema"]["required"] == ["profile_path"]
    assert profile_run_plan_tool["inputSchema"]["properties"]["platform"]["enum"] == ["getcourse", "skillspace", "stepik"]
    assert "embedding_endpoint" in semantic_provider_tool["inputSchema"]["properties"]
    assert "embedding_token_env" in semantic_provider_tool["inputSchema"]["properties"]
    assert browser_snapshot_audit_tool["inputSchema"]["required"] == ["snapshot_path"]
    assert browser_snapshot_audit_tool["inputSchema"]["properties"]["platform"]["enum"] == ["getcourse", "skillspace"]
    assert connected_run_tool["inputSchema"]["required"] == []
    assert lesson_context_tool["inputSchema"]["required"] == ["query"]
    assert "graph_limit" in lesson_context_tool["inputSchema"]["properties"]
    assert evidence_tool["inputSchema"]["required"] == ["query"]
    assert refresh_tool["inputSchema"]["required"] == ["query"]

    called = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "search", "arguments": {"query": "rollback", "run": "starter-fixture"}},
    })
    result = called["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["tool"] == "search"
    assert result["structuredContent"]["results"]

    evidence = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 31,
        "method": "tools/call",
        "params": {"name": "evidence_report", "arguments": {"query": "rollback", "run": "starter-fixture"}},
    })
    assert evidence["result"]["structuredContent"]["tool"] == "evidence_report"
    assert evidence["result"]["structuredContent"]["evidence_chain"]
    assert evidence["result"]["structuredContent"]["quality"]["ready"] is True

    refresh = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 32,
        "method": "tools/call",
        "params": {"name": "refresh_plan", "arguments": {"query": "rollback", "run": "starter-fixture", "mode": "keyword"}},
    })
    assert refresh["result"]["structuredContent"]["tool"] == "refresh_plan"
    assert refresh["result"]["structuredContent"]["refresh"]["network_touched"] is False
    assert any(
        "lesson-context" in command
        for command in refresh["result"]["structuredContent"]["refresh"]["planned_commands"]["local_query_commands"]
    )

    preflight = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "live_preflight", "arguments": {"platforms": ["stepik"]}},
    })
    preflight_result = preflight["result"]
    assert preflight_result["isError"] is False
    assert preflight_result["structuredContent"]["tool"] == "live_preflight"
    assert preflight_result["structuredContent"]["preflight"]["network_touched"] is False
    semantic_preflight = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 40,
        "method": "tools/call",
        "params": {"name": "semantic_provider_preflight", "arguments": {"run": "starter-fixture"}},
    })
    assert semantic_preflight["result"]["structuredContent"]["tool"] == "semantic_provider_preflight"
    assert semantic_preflight["result"]["structuredContent"]["preflight"]["network_touched"] is False
    snapshot_audit = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 401,
        "method": "tools/call",
        "params": {
            "name": "browser_snapshot_audit",
            "arguments": {
                "snapshot_path": "connector/fixtures/browser/getcourse_starter_snapshot.json",
                "platform": "getcourse",
            },
        },
    })
    snapshot_content = snapshot_audit["result"]["structuredContent"]
    assert snapshot_content["tool"] == "browser_snapshot_audit"
    assert snapshot_content["audit"]["schema"] == "aoa_course_browser_snapshot_audit_v1"
    assert snapshot_content["audit"]["network_touched"] is False
    assert snapshot_content["audit"]["privacy"]["raw_html_included"] is False
    assert "rollback index" not in json.dumps(snapshot_content)
    upsert_source(storage.data, "stepik", "67", "Stepik Public", access_mode="public_api")

    connected_plan = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 41,
        "method": "tools/call",
        "params": {"name": "connected_source_plan", "arguments": {"platforms": ["stepik"], "live_scope": "full-course", "include_step_sources": True}},
    })
    assert connected_plan["result"]["structuredContent"]["tool"] == "connected_source_plan"
    assert connected_plan["result"]["structuredContent"]["plan"]["network_touched"] is False
    assert connected_plan["result"]["structuredContent"]["plan"]["live_scope"] == "full-course"
    assert connected_plan["result"]["structuredContent"]["plan"]["include_step_sources"] is True
    connected_status = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 42,
        "method": "tools/call",
        "params": {"name": "connected_run_status", "arguments": {"run": "missing-connected-run"}},
    })
    assert connected_status["result"]["structuredContent"]["tool"] == "connected_run_status"
    assert connected_status["result"]["structuredContent"]["connected_run"]["status"] == "missing"
    readiness = handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 43,
        "method": "tools/call",
        "params": {
            "name": "connector_readiness",
            "arguments": {
                "runs": ["starter-fixture"],
                "platforms": ["stepik"],
                "live_scope": "full-course",
                "include_step_sources": True,
                "max_lessons": 9,
                "max_pages": 4,
                "max_sources": 2,
            },
        },
    })
    readiness_content = readiness["result"]["structuredContent"]
    assert readiness_content["tool"] == "connector_readiness"
    assert readiness_content["schema"] == "aoa_course_connector_readiness_v1"
    assert readiness_content["runs"][0]["readiness"]["agent_query_ready"] is True
    assert readiness_content["mcp"]["ready"] is True
    compact_plan = readiness_content["connected_source_plan"]
    assert compact_plan["live_scope"] == "full-course"
    assert compact_plan["include_step_sources"] is True
    assert compact_plan["max_lessons"] == 9
    assert compact_plan["max_pages"] == 4
    assert compact_plan["max_sources"] == 2
    assert compact_plan["connected_run_plan"]["ready"] is True
    assert "--live-scope full-course" in compact_plan["connected_run_plan"]["command"]
    assert "--include-step-sources" in compact_plan["connected_run_plan"]["command"]
    assert "--max-lessons 9" in compact_plan["connected_run_plan"]["command"]
    assert "--max-pages 4" in compact_plan["connected_run_plan"]["command"]
    assert "--max-sources 2" in compact_plan["connected_run_plan"]["command"]
