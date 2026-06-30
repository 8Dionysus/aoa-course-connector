from __future__ import annotations

import subprocess
import sys


def test_connector_validator_passes() -> None:
    result = subprocess.run([sys.executable, "scripts/validate_connector.py"], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
