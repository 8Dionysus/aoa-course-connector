#!/usr/bin/env python3
"""Verify a fresh agent can install and run the offline starter route."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="aoa-course-install-") as tmp:
        copy_root = Path(tmp) / "repo"
        ignore = shutil.ignore_patterns(".git", ".connector-state/data/*", ".connector-state/cache/*", ".connector-state/auth/*", ".connector-state/artifacts/*", "__pycache__", ".pytest_cache", "*.egg-info", "dist", "build")
        shutil.copytree(repo_root, copy_root, ignore=ignore)
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        env["AOA_COURSE_INSTANCE_ROOT"] = str(Path(tmp) / "state")
        commands = [
            [sys.executable, "scripts/validate_connector.py"],
            [sys.executable, "-m", "compileall", "-q", "src", "scripts"],
            [sys.executable, "-m", "aoa_course_connector.cli", "doctor"],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "fixture", "--run", "starter-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "starter-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-semantic-index", "--run", "starter-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "starter-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "bootloader unlock rollback", "--run", "starter-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "bootloader rollback", "--run", "starter-fixture", "--mode", "hybrid"],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "stepik-fixture", "--run", "stepik-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "stepik-live", "--help"],
            [sys.executable, "-m", "aoa_course_connector.cli", "discover", "stepik-account", "--from-fixture", "--run", "stepik-account-discovery-fixture", "--register", "--source-limit", "1"],
            [sys.executable, "-m", "aoa_course_connector.cli", "preflight", "live", "--platform", "stepik"],
            [sys.executable, "-m", "aoa_course_connector.cli", "discover", "stepik", "67", "--register", "--title", "Stepik course 67"],
            [sys.executable, "-m", "aoa_course_connector.cli", "sync", "stepik-fixture", "--run", "stepik-sync-fixture", "--build-artifacts"],
            [sys.executable, "-m", "aoa_course_connector.cli", "sync", "status", "--run", "stepik-sync-fixture", "--platform", "stepik"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "stepik-sync"],
            [sys.executable, "-m", "aoa_course_connector.cli", "smoke", "stepik-fixture", "67", "--run", "stepik-smoke-fixture", "--query", "Stepik public API evidence"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "stepik-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-semantic-index", "--run", "stepik-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "stepik-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "Stepik public API evidence", "--run", "stepik-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "clean-api"],
            [sys.executable, "-m", "aoa_course_connector.cli", "discover", "browser-fixture", "--platform", "getcourse", "--run", "getcourse-browser-discovery-fixture", "--register"],
            [sys.executable, "-m", "aoa_course_connector.cli", "discover", "browser-fixture", "--platform", "skillspace", "--run", "skillspace-browser-discovery-fixture", "--register"],
            [sys.executable, "-m", "aoa_course_connector.cli", "sources", "list"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "browser-discovery"],
            [sys.executable, "-m", "aoa_course_connector.cli", "sync", "browser-fixture", "--run", "browser-sync-fixture", "--build-artifacts"],
            [sys.executable, "-m", "aoa_course_connector.cli", "sync", "status", "--run", "browser-sync-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "browser-sync"],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "sync_status", '{"sync_run":"browser-sync-fixture"}'],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "browser-fixture", "--platform", "getcourse", "--run", "getcourse-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "getcourse-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "getcourse-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "GetCourse bootloader rollback evidence", "--run", "getcourse-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "answer-quality"],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "fixture", "--run", "freshness-ranking-fixture", "--fixture", "connector/fixtures/course/freshness_conflict_course.json"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "freshness-ranking-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-semantic-index", "--run", "freshness-ranking-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "freshness-ranking"],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "fixture", "--run", "authority-ranking-fixture", "--fixture", "connector/fixtures/course/authority_conflict_course.json"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "authority-ranking-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-semantic-index", "--run", "authority-ranking-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "authority-ranking"],
            [sys.executable, "-m", "aoa_course_connector.cli", "materialize", "browser-fixture", "--platform", "skillspace", "--run", "skillspace-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "skillspace-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "skillspace-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "Skillspace logcat bugreport evidence", "--run", "skillspace-browser-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "browser-hard-adapters"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "browser-progress-comments"],
            [sys.executable, "-m", "aoa_course_connector.cli", "preflight", "live", "--platform", "getcourse"],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "live_preflight", '{"platforms":["getcourse","stepik"]}'],
            [sys.executable, "-m", "aoa_course_connector.cli", "smoke", "browser-fixture", "--platform", "getcourse", "--run", "getcourse-browser-smoke-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "crawl", "browser-fixture", "--platform", "getcourse", "--run", "getcourse-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "getcourse-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "getcourse-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "GetCourse bootloader rollback evidence", "--run", "getcourse-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "crawl", "browser-fixture", "--platform", "skillspace", "--run", "skillspace-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-index", "--run", "skillspace-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "skillspace-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "Skillspace logcat bugreport evidence", "--run", "skillspace-browser-crawl-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "browser-crawl"],
            [sys.executable, "-m", "aoa_course_connector.cli", "eval", "semantic-index"],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "tools"],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "semantic_search", '{"query":"rollback","run":"starter-fixture"}'],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "call", "hybrid_search", '{"query":"rollback","run":"starter-fixture"}'],
        ]
        if not args.skip_pytest:
            commands.insert(1, [sys.executable, "-m", "pytest", "-q"])
        for command in commands:
            result = subprocess.run(command, cwd=copy_root, env=env, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"failed command: {' '.join(command)}", file=sys.stderr)
                print(result.stdout, file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                return result.returncode
        stdio_requests = "\n".join([
            '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"install-route","version":"0"}}}',
            '{"jsonrpc":"2.0","id":2,"method":"tools/list"}',
            '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search","arguments":{"query":"rollback","run":"starter-fixture"}}}',
            "",
        ])
        result = subprocess.run(
            [sys.executable, "-m", "aoa_course_connector.mcp.server"],
            input=stdio_requests,
            cwd=copy_root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or '"structuredContent"' not in result.stdout:
            print("failed MCP stdio route", file=sys.stderr)
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return result.returncode or 1
    print("agent install route ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
