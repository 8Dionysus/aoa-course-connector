from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


VALIDATOR_PATH = Path("scripts/validate_connector.py")


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_connector", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_connector_validator_passes() -> None:
    result = subprocess.run([sys.executable, "scripts/validate_connector.py"], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_agent_install_route_rejects_platform_narrowed_bootstrap() -> None:
    validator = load_validator_module()
    errors: list[str] = []

    validator._check_agent_install_route_commands(
        "\n".join(
            [
                "Run `aoa-course bootstrap fixture --run starter-fixture --connected-run connected-calibration --platform stepik`.",
                "Run `aoa-course readiness --run starter-fixture` and inspect `connector_readiness`.",
            ]
        ),
        errors,
    )

    assert "Agent install route missing exact fixture bootstrap command" in errors
    assert "Agent install route must not narrow fixture bootstrap plan with --platform" in errors


def test_agent_install_route_rejects_platform_before_required_bootstrap_args() -> None:
    validator = load_validator_module()
    errors: list[str] = []

    validator._check_agent_install_route_commands(
        "\n".join(
            [
                "Run `aoa-course bootstrap fixture --platform stepik --run starter-fixture --connected-run connected-calibration`.",
                "Run `aoa-course readiness --run starter-fixture` and inspect `connector_readiness`.",
            ]
        ),
        errors,
    )

    assert "Agent install route missing exact fixture bootstrap command" in errors
    assert "Agent install route must not narrow fixture bootstrap plan with --platform" in errors


def test_kag_provider_validator_reports_non_list_record_classes(monkeypatch) -> None:
    validator = load_validator_module()
    original_read_json = validator._read_json

    def read_json_with_bad_record_classes(path: Path, errors: list[str]):
        payload = original_read_json(path, errors)
        if path == Path("kag/manifest.json") and isinstance(payload, dict):
            payload = dict(payload)
            payload["record_classes"] = None
        return payload

    monkeypatch.setattr(validator, "_read_json", read_json_with_bad_record_classes)
    errors: list[str] = []

    validator._check_kag_provider(Path("."), errors)

    assert "KAG manifest record_classes must be a list" in errors
