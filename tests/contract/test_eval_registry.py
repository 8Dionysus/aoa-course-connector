from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from aoa_course_connector import cli
from aoa_course_connector.eval_registry import load_eval_registry, validate_eval_registry


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _suite(suite_id: str) -> dict[str, object]:
    return {
        "schema": "aoa_course_test_eval_suite_v1",
        "suite_id": suite_id,
        "cases": [],
    }


def _entry(suite_id: str, filename: str, command: str) -> dict[str, object]:
    return {
        "suite_id": suite_id,
        "path": f"evals/suites/{filename}",
        "owner": "aoa-course-connector",
        "capability": suite_id,
        "execution": {"argv": ["eval", command]},
    }


def _fixture_registry(tmp_path: Path) -> dict[str, object]:
    suite_root = tmp_path / "evals/suites"
    suite_root.mkdir(parents=True)
    (suite_root / "alpha.json").write_text(json.dumps(_suite("alpha")), encoding="utf-8")
    (suite_root / "beta.json").write_text(json.dumps(_suite("beta")), encoding="utf-8")
    return {
        "schema_version": "aoa_course_eval_registry_v1",
        "owner_repo": "aoa-course-connector",
        "suites": [
            _entry("alpha", "alpha.json", "alpha"),
            _entry("beta", "beta.json", "beta"),
        ],
    }


def test_owner_registry_enumerates_all_active_suites() -> None:
    registry = load_eval_registry(REPO_ROOT)
    entries = registry["suites"]

    assert len(entries) == 18
    assert {entry["suite_id"] for entry in entries} >= {"corpus-integrity"}
    assert "suite_registry: evals/registry.json" in (REPO_ROOT / "evals/PORT.yaml").read_text(encoding="utf-8")


def test_connector_required_files_do_not_duplicate_suite_inventory() -> None:
    from validate_connector import REQUIRED_FILES

    registry = load_eval_registry(REPO_ROOT)
    registered_paths = {entry["path"] for entry in registry["suites"]}

    assert registered_paths.isdisjoint(REQUIRED_FILES)


def test_registry_rejects_deleted_declared_suite(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    (tmp_path / "evals/suites/alpha.json").unlink()

    errors = validate_eval_registry(tmp_path, registry)

    assert any("alpha.json" in error and "unable to load" in error for error in errors)


def test_registry_rejects_unregistered_active_suite(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    (tmp_path / "evals/suites/orphan.json").write_text(json.dumps(_suite("orphan")), encoding="utf-8")

    errors = validate_eval_registry(tmp_path, registry)

    assert "evals/registry.json: unregistered active suite evals/suites/orphan.json" in errors


def test_registry_rejects_duplicate_suite_declaration(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    registry["suites"].append(copy.deepcopy(registry["suites"][0]))

    errors = validate_eval_registry(tmp_path, registry)

    assert any("duplicate suite_id alpha" in error for error in errors)
    assert any("duplicate suite path evals/suites/alpha.json" in error for error in errors)
    assert any("duplicate execution route eval alpha" in error for error in errors)


def test_registry_rejects_suite_path_outside_owner_directory(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    registry["suites"][0]["path"] = "connector/fixtures/alpha.json"

    errors = validate_eval_registry(tmp_path, registry)

    assert any("directly under evals/suites" in error and "connector/fixtures/alpha.json" in error for error in errors)


def test_registry_rejects_path_payload_identity_drift(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    (tmp_path / "evals/suites/alpha.json").write_text(json.dumps(_suite("renamed-alpha")), encoding="utf-8")

    errors = validate_eval_registry(tmp_path, registry)

    assert any("alpha.json payload 'renamed-alpha'" in error for error in errors)


def test_registry_rejects_active_historical_fixture_without_route(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    (tmp_path / "evals/suites/historical.json").write_text(json.dumps(_suite("historical")), encoding="utf-8")
    historical = _entry("historical", "historical.json", "historical")
    historical.pop("execution")
    registry["suites"].append(historical)

    errors = validate_eval_registry(tmp_path, registry)

    assert any("historical.json" in error and "execution.argv" in error for error in errors)


def test_port_route_dispatches_the_registered_direct_case_body(monkeypatch) -> None:
    registry = {
        "owner_repo": "aoa-course-connector",
        "suites": [_entry("corpus-integrity", "corpus_integrity.json", "corpus-integrity")],
    }
    calls: list[str] = []

    def direct_case_body(args) -> int:
        calls.append(args.eval_command)
        return 0

    monkeypatch.setattr(cli, "load_eval_registry", lambda _root: registry)
    monkeypatch.setattr(cli, "cmd_eval_corpus_integrity", direct_case_body)

    assert cli.main(["eval", "run", "corpus-integrity"]) == 0
    assert calls == ["corpus-integrity"]


def test_port_route_reports_unknown_suite_without_traceback(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "load_eval_registry",
        lambda _root: {"owner_repo": "aoa-course-connector", "suites": []},
    )

    assert cli.main(["eval", "run", "does-not-exist"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "error": "evals/registry.json: unknown suite_id does-not-exist",
        "schema": "aoa_course_eval_run_v1",
        "status": "error",
        "suite_id": "does-not-exist",
    }


def test_owner_validator_rejects_non_eval_execution_route(tmp_path: Path) -> None:
    from validate_connector import _check_eval_registry

    registry = _fixture_registry(tmp_path)
    registry["suites"][0]["execution"]["argv"] = ["doctor"]
    registry["suites"][1]["execution"]["argv"] = ["eval", "corpus-integrity"]
    (tmp_path / "evals/registry.json").write_text(json.dumps(registry), encoding="utf-8")
    errors: list[str] = []

    _check_eval_registry(tmp_path, errors)

    assert any("must stay under aoa-course eval: doctor" in error for error in errors)
