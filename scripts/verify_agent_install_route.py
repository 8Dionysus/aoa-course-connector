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
            [sys.executable, "-m", "aoa_course_connector.cli", "build-graph", "--run", "starter-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "answer", "bootloader unlock rollback", "--run", "starter-fixture"],
            [sys.executable, "-m", "aoa_course_connector.cli", "mcp", "tools"],
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
    print("agent install route ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
