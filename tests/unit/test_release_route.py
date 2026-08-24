from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "release.py"


def _release_module():
    spec = importlib.util.spec_from_file_location("course_release_route", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manifest(version: str = "0.1.1") -> dict[str, object]:
    return {
        "schema_version": "aoa_course_connector_release_manifest_v1",
        "repository": "8Dionysus/aoa-course-connector",
        "version": version,
        "tag": f"v{version}",
        "canonical_changelog": "CHANGELOG.md",
        "reconciliation_ledger": f"docs/RELEASE_RECONCILIATION_{version}.md",
        "previous_release": {
            "version": "0.1.0",
            "tag": "v0.1.0",
            "commit": "181abe0e11a96f45c4b465ef10282ff35480c3da",
        },
        "version_sources": [
            "pyproject.toml",
            "src/aoa_course_connector/__init__.py",
            "src/aoa_course_connector/mcp/server.py",
            "CHANGELOG.md",
        ],
        "provider_prerequisites": [
            {
                "repository": "8Dionysus/aoa-kag",
                "tag": "v0.5.0",
        "commit": "f46f146cc79a26fa81ad0f400b9c5774df293e57",
            }
        ],
        "workflow_pins": {
            "aoa_kag_repo_local_action": {"ref": "kag-action-pin"},
            "aoa_stats_checkout": {"ref": "stats-checkout-pin"},
        },
        "publication": {
            "kind": "github_source_release",
            "assets": [],
            "package_registry": {"published": False},
        },
    }


def _write_target_surfaces(root: Path, version: str = "0.1.1") -> None:
    (root / "release").mkdir()
    (root / "src/aoa_course_connector/mcp").mkdir(parents=True)
    (root / "src/aoa_course_connector").mkdir(exist_ok=True)
    (root / "pyproject.toml").write_text(f'version = "{version}"\n', encoding="utf-8")
    (root / "src/aoa_course_connector/__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    (root / "src/aoa_course_connector/mcp/server.py").write_text(f'SERVER_VERSION = "{version}"\n', encoding="utf-8")
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## {version} - 2026-08-22\n\n### Fixed\n\n- Corrective route.\n\n## 0.1.0 - 2026-08-22\n\n- Prior release.\n",
        encoding="utf-8",
    )
    (root / ".github/workflows").mkdir(parents=True)
    (root / ".github/workflows/validate.yml").write_text("kag-action-pin\nstats-checkout-pin\n", encoding="utf-8")
    (root / "release/release-manifest.json").write_text(json.dumps(_manifest(version), indent=2), encoding="utf-8")


def test_release_route_reads_target_identity_from_manifest(tmp_path: Path) -> None:
    module = _release_module()
    _write_target_surfaces(tmp_path)

    config = module.load_release_config(tmp_path)
    errors: list[str] = []
    checks: dict[str, object] = {}
    module.check_manifest(tmp_path, config, errors, checks)
    module.check_version_markers(tmp_path, config, errors, checks)
    module.check_workflow_pins(tmp_path, config, errors, checks)

    assert not errors
    assert config.version == "0.1.1"
    assert config.tag == "v0.1.1"
    assert module.changelog_notes(tmp_path, config) == "### Fixed\n\n- Corrective route.\n"


def test_release_route_rejects_manifest_target_tag_mismatch(tmp_path: Path) -> None:
    module = _release_module()
    _write_target_surfaces(tmp_path)
    manifest_path = tmp_path / "release/release-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["tag"] = "v0.1.0"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    config = module.load_release_config(tmp_path)
    errors: list[str] = []
    module.check_manifest(tmp_path, config, errors, {})

    assert "release manifest tag mismatch: 'v0.1.0'" in errors


def test_release_route_requires_previous_release_for_later_patch(tmp_path: Path) -> None:
    module = _release_module()
    _write_target_surfaces(tmp_path, version="0.1.2")
    manifest_path = tmp_path / "release/release-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload.pop("previous_release")
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    config = module.load_release_config(tmp_path)
    errors: list[str] = []
    module.check_manifest(tmp_path, config, errors, {})

    assert "release manifest must identify the previous stable release for sequential releases" in errors


def test_current_provider_contract_keeps_release_and_action_identities_separate() -> None:
    manifest = json.loads((REPO_ROOT / "release/release-manifest.json").read_text(encoding="utf-8"))
    providers = {item["repository"]: item for item in manifest["provider_prerequisites"]}
    workflow_pins = manifest["workflow_pins"]

    assert providers["8Dionysus/aoa-kag"] == {
        "repository": "8Dionysus/aoa-kag",
        "tag": "v0.5.0",
        "commit": "f46f146cc79a26fa81ad0f400b9c5774df293e57",
    }
    assert providers["8Dionysus/aoa-stats"] == {
        "repository": "8Dionysus/aoa-stats",
        "tag": "v0.2.0",
        "commit": "88ff38b1b38eef939f2c5b4541cbe8363a05fc8d",
    }
    assert workflow_pins["aoa_stats_checkout"] == {
        "tag": "v0.2.0",
        "ref": "88ff38b1b38eef939f2c5b4541cbe8363a05fc8d",
    }
    action_ref = workflow_pins["aoa_kag_repo_local_action"]["ref"]
    assert action_ref == "6a79e62c7d20b6b11406dee78f409ada4a51bb3f"
    assert action_ref != providers["8Dionysus/aoa-kag"]["commit"]
