from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run_cli(tmp_path: Path, *args: str) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["AOA_COURSE_DATA_ROOT"] = str(tmp_path / "data")
    env["AOA_COURSE_CACHE_ROOT"] = str(tmp_path / "cache")
    env["AOA_COURSE_AUTH_ROOT"] = str(tmp_path / "auth")
    env["AOA_COURSE_ARTIFACT_ROOT"] = str(tmp_path / "artifacts")
    result = subprocess.run([sys.executable, "-m", "aoa_course_connector.cli", *args], check=False, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_cli_starter_flow(tmp_path: Path) -> None:
    assert run_cli(tmp_path, "doctor")["status"] == "ok"
    run_cli(tmp_path, "init")
    run_cli(tmp_path, "materialize", "fixture", "--run", "starter-fixture")
    run_cli(tmp_path, "build-index", "--run", "starter-fixture")
    run_cli(tmp_path, "build-graph", "--run", "starter-fixture")
    answer = run_cli(tmp_path, "answer", "bootloader unlock rollback", "--run", "starter-fixture")
    assert answer["result_count"] >= 1
    assert answer["evidence_chain"]
    tools = run_cli(tmp_path, "mcp", "tools")
    assert tools["server"] == "aoa-course-connector-mcp"


def test_cli_stepik_fixture_flow(tmp_path: Path) -> None:
    run_cli(tmp_path, "materialize", "stepik-fixture", "--run", "stepik-fixture")
    run_cli(tmp_path, "build-index", "--run", "stepik-fixture")
    run_cli(tmp_path, "build-graph", "--run", "stepik-fixture")
    answer = run_cli(tmp_path, "answer", "Stepik public API evidence", "--run", "stepik-fixture")
    assert answer["result_count"] >= 1
    assert answer["evidence_chain"]


def test_cli_browser_hard_adapter_fixture_flow(tmp_path: Path) -> None:
    for platform, query in [
        ("getcourse", "GetCourse bootloader rollback evidence"),
        ("skillspace", "Skillspace logcat bugreport evidence"),
    ]:
        run_id = f"{platform}-browser-fixture"
        run_cli(tmp_path, "materialize", "browser-fixture", "--platform", platform, "--run", run_id)
        run_cli(tmp_path, "build-index", "--run", run_id)
        run_cli(tmp_path, "build-graph", "--run", run_id)
        answer = run_cli(tmp_path, "answer", query, "--run", run_id)
        assert answer["result_count"] >= 1
        assert answer["evidence_chain"]
    eval_result = run_cli(tmp_path, "eval", "browser-hard-adapters")
    assert eval_result["status"] == "ok"


def test_cli_browser_course_tree_crawl_fixture_flow(tmp_path: Path) -> None:
    for platform, query in [
        ("getcourse", "GetCourse bootloader rollback evidence"),
        ("skillspace", "Skillspace logcat bugreport evidence"),
    ]:
        run_id = f"{platform}-browser-crawl-fixture"
        receipt = run_cli(tmp_path, "crawl", "browser-fixture", "--platform", platform, "--run", run_id)
        assert receipt["crawl"]["discovered_lesson_count"] == 2
        run_cli(tmp_path, "build-index", "--run", run_id)
        run_cli(tmp_path, "build-graph", "--run", run_id)
        answer = run_cli(tmp_path, "answer", query, "--run", run_id)
        assert answer["result_count"] >= 1
        assert answer["evidence_chain"]
    eval_result = run_cli(tmp_path, "eval", "browser-crawl")
    assert eval_result["status"] == "ok"


def test_cli_browser_account_discovery_registers_sources(tmp_path: Path) -> None:
    for platform in ["getcourse", "skillspace"]:
        receipt = run_cli(
            tmp_path,
            "discover",
            "browser-fixture",
            "--platform",
            platform,
            "--run",
            f"{platform}-browser-discovery-fixture",
            "--register",
        )
        assert receipt["course_count"] == 2
        assert len(receipt["registered_sources"]) == 2
    registry = run_cli(tmp_path, "sources", "list")["registry"]
    assert len(registry["sources"]) == 4
    eval_result = run_cli(tmp_path, "eval", "browser-discovery")
    assert eval_result["status"] == "ok"


def test_cli_browser_source_sync_checkpoint_flow(tmp_path: Path) -> None:
    for platform in ["getcourse", "skillspace"]:
        run_cli(
            tmp_path,
            "discover",
            "browser-fixture",
            "--platform",
            platform,
            "--run",
            f"{platform}-browser-discovery-fixture",
            "--register",
        )
    receipt = run_cli(tmp_path, "sync", "browser-fixture", "--run", "browser-sync-fixture", "--build-artifacts")
    assert receipt["status"] == "ok"
    assert receipt["synced_count"] == 4
    status = run_cli(tmp_path, "sync", "status", "--run", "browser-sync-fixture")
    assert status["ok_count"] == 4
    eval_result = run_cli(tmp_path, "eval", "browser-sync")
    assert eval_result["status"] == "ok"
    mcp_status = run_cli(tmp_path, "mcp", "call", "sync_status", '{"sync_run":"browser-sync-fixture"}')
    assert mcp_status["result"]["sync"]["ok_count"] == 4
