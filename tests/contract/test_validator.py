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


def test_markdown_hygiene_rejects_command_fence_outside_agents(tmp_path: Path) -> None:
    validator = load_validator_module()
    (tmp_path / "README.md").write_text(
        "# Readme\n\n```bash\npython scripts/validate_connector.py\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text(
        "# AGENTS.md\n\n```bash\npython scripts/validate_connector.py\n```\n",
        encoding="utf-8",
    )
    errors: list[str] = []

    validator._check_markdown_command_hygiene(tmp_path, errors)

    assert errors == ["command block outside AGENTS.md: README.md:3"]


def test_markdown_hygiene_rejects_unterminated_fence(tmp_path: Path) -> None:
    validator = load_validator_module()
    (tmp_path / "docs.md").write_text("# Broken\n\n```json\n{}\n", encoding="utf-8")
    errors: list[str] = []

    validator._check_markdown_command_hygiene(tmp_path, errors)

    assert errors == ["unterminated Markdown fence: docs.md:3"]


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
