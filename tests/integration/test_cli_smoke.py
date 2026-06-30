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
