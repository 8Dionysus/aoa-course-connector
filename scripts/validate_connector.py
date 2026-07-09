#!/usr/bin/env python3
"""Validate the GitHub-publishable course connector repository."""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path


BOOTSTRAP_FIXTURE_INSTALL_COMMAND = "aoa-course bootstrap fixture --run starter-fixture --connected-run connected-calibration"
PLATFORM_NARROWED_BOOTSTRAP_ERROR = "Agent install route must not narrow fixture bootstrap plan with --platform"
COMMAND_SPAN_RE = re.compile(r"`([^`\n]+)`")
PUBLIC_STATUS_GETCOURSE_SOURCE_ID_RE = re.compile(r"source:getcourse:[0-9a-f]{10,}")

REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    "CHARTER.md",
    "BOUNDARIES.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "pyproject.toml",
    ".env.example",
    ".gitignore",
    ".github/workflows/validate.yml",
    ".connector-state/AGENTS.md",
    ".connector-state/README.md",
    "connector/SOURCE_POLICY.md",
    "connector/STORAGE_POLICY.md",
    "connector/manifests/connector_manifest.yaml",
    "connector/manifests/route_allowlist.yaml",
    "connector/manifests/artifact_classes.yaml",
    "connector/profiles/starter-course.yaml",
    "connector/fixtures/course/starter_course.json",
    "connector/fixtures/course/freshness_conflict_course.json",
    "connector/fixtures/course/authority_conflict_course.json",
    "connector/fixtures/browser/getcourse_starter_snapshot.json",
    "connector/fixtures/browser/skillspace_starter_snapshot.json",
    "connector/fixtures/browser/getcourse_catalog_snapshot.json",
    "connector/fixtures/browser/skillspace_catalog_snapshot.json",
    "connector/fixtures/stepik/account_courses.json",
    "connector/fixtures/stepik/starter_stepik_course.json",
    "connector/schemas/connection_profile.schema.json",
    "docs/ARCHITECTURE.md",
    "docs/INSTALL.md",
    "docs/AGENT_INSTALL_ROUTE.md",
    "docs/STORAGE_CONTRACT.md",
    "docs/AUTH_SESSION.md",
    "docs/BROWSER_SESSION.md",
    "docs/ADAPTER_GUIDE.md",
    "docs/GETCOURSE.md",
    "docs/SKILLSPACE.md",
    "docs/CLEAN_API_ADAPTERS.md",
    "docs/STEPIK.md",
    "docs/CLI_USAGE.md",
    "docs/LIVE_CALIBRATION.md",
    "docs/MCP_USAGE.md",
    "docs/QUERY_MODEL.md",
    "docs/GRAPH_MODEL.md",
    "docs/RUNTIME_CONTRACT.md",
    "docs/PRIVACY_SECURITY.md",
    "docs/TROUBLESHOOTING.md",
    "docs/STARTER_PROOF.md",
    "docs/STATUS.md",
    "docs/decisions/README.md",
    "docs/decisions/AOA-COURSE-D-0001-course-knowledge-not-downloader.md",
    "evals/AGENTS.md",
    "evals/PORT.yaml",
    "evals/README.md",
    "evals/intake/README.md",
    "evals/reports/README.md",
    "evals/suites/README.md",
    "evals/suites/retrieval-loop.suite.md",
    "evals/suites/retrieval_loop.json",
    "evals/suites/answer-quality.suite.md",
    "evals/suites/answer_quality_packets.json",
    "evals/suites/freshness-ranking.suite.md",
    "evals/suites/freshness_ranking.json",
    "evals/suites/authority-ranking.suite.md",
    "evals/suites/authority_ranking.json",
    "evals/suites/adapter-authority.suite.md",
    "evals/suites/adapter_authority_metadata.json",
    "evals/suites/live-calibration.suite.md",
    "evals/suites/live_calibration_packet.json",
    "evals/suites/browser-transcripts.suite.md",
    "evals/suites/browser_transcripts_answer_packets.json",
    "evals/suites/starter_course_answer_packets.json",
    "evals/suites/browser_hard_adapter_answer_packets.json",
    "evals/suites/browser_progress_comments_answer_packets.json",
    "evals/suites/browser_crawl_answer_packets.json",
    "evals/suites/browser_discovery_sources.json",
    "evals/suites/browser_sync_checkpoints.json",
    "evals/suites/stepik_clean_api_answer_packets.json",
    "kag/AGENTS.md",
    "kag/README.md",
    "kag/edges/source_routes_to_storage_boundary.json",
    "kag/indexes/source_inventory.json",
    "kag/indexes/source_surface_index.json",
    "kag/manifest.json",
    "kag/nodes/source_home.json",
    "kag/nodes/storage_boundary.json",
    "kag/projections/source_return.json",
    "kag/receipts/validation_receipt.json",
    "src/aoa_course_connector/bootstrap.py",
    "src/aoa_course_connector/cli.py",
    "src/aoa_course_connector/connection_profile.py",
    "src/aoa_course_connector/calibration/__init__.py",
    "src/aoa_course_connector/adapters/browser/crawl.py",
    "src/aoa_course_connector/adapters/browser/discovery.py",
    "src/aoa_course_connector/adapters/browser/snapshot.py",
    "src/aoa_course_connector/discover/browser_session.py",
    "src/aoa_course_connector/discover/stepik.py",
    "src/aoa_course_connector/adapters/stepik/client.py",
    "src/aoa_course_connector/ingest/browser_session.py",
    "src/aoa_course_connector/ingest/stepik.py",
    "src/aoa_course_connector/normalize/browser_session.py",
    "src/aoa_course_connector/normalize/stepik.py",
    "src/aoa_course_connector/mcp/server.py",
    "src/aoa_course_connector/refresh.py",
    "src/aoa_course_connector/readiness.py",
    "src/aoa_course_connector/status.py",
    "src/aoa_course_connector/smoke/__init__.py",
    "src/aoa_course_connector/smoke/browser_session.py",
    "src/aoa_course_connector/smoke/stepik.py",
    "src/aoa_course_connector/sync/browser_session.py",
    "src/aoa_course_connector/sync/checkpoints.py",
    "src/aoa_course_connector/sync/stepik.py",
    "scripts/validate_connector.py",
    "scripts/verify_agent_install_route.py",
]

REQUIRED_DIRS = [
    ".connector-state",
    ".connector-state/data",
    ".connector-state/cache",
    ".connector-state/auth",
    ".connector-state/artifacts",
    ".github/workflows",
    "connector/schemas",
    "src/aoa_course_connector/adapters",
    "src/aoa_course_connector/adapters/browser",
    "src/aoa_course_connector/adapters/stepik",
    "src/aoa_course_connector/auth",
    "src/aoa_course_connector/calibration",
    "src/aoa_course_connector/core",
    "src/aoa_course_connector/discover",
    "src/aoa_course_connector/evidence",
    "src/aoa_course_connector/graph",
    "src/aoa_course_connector/index",
    "src/aoa_course_connector/ingest",
    "src/aoa_course_connector/mcp",
    "src/aoa_course_connector/normalize",
    "src/aoa_course_connector/query",
    "src/aoa_course_connector/smoke",
    "src/aoa_course_connector/storage",
    "src/aoa_course_connector/sync",
    "tests/unit",
    "tests/contract",
    "tests/integration",
    "evals/intake",
    "evals/reports",
    "kag",
    "kag/edges",
    "kag/indexes",
    "kag/nodes",
    "kag/projections",
    "kag/receipts",
]

REQUIRED_SCHEMAS = [
    "course.schema.json",
    "course_source.schema.json",
    "module.schema.json",
    "lesson.schema.json",
    "step.schema.json",
    "asset.schema.json",
    "transcript.schema.json",
    "assignment.schema.json",
    "comment_thread.schema.json",
    "comment.schema.json",
    "progress.schema.json",
    "entity.schema.json",
    "topic.schema.json",
    "evidence.schema.json",
    "ingest_run.schema.json",
    "sync_checkpoint.schema.json",
    "normalized_course_bundle.schema.json",
    "index_manifest.schema.json",
    "graph_node.schema.json",
    "graph_edge.schema.json",
    "answer_packet.schema.json",
    "lesson_context_packet.schema.json",
    "refresh_cycle.schema.json",
    "source_registry.schema.json",
    "connection_profile.schema.json",
]

REQUIRED_GITIGNORE = [
    ".connector-state/*",
    "!.connector-state/auth/",
    "AOA_COURSE_AUTH_ROOT",
    "data/",
    "cache/",
    "auth/",
    "artifacts/",
    "raw/",
    "indexes/",
    "vectors/",
    "graphs/",
    "*.sqlite",
    "*.parquet",
    "*.storage-state.json",
    "*.cookies.json",
    "!kag/indexes/",
    "!kag/indexes/*.json",
]

FORBIDDEN_HEAVY_ROOTS = {"data", "cache", "auth", "artifacts", "raw", "indexes", "vectors", "graphs", "exports"}
FORBIDDEN_GENERATED_GIT_FILES: set[str] = set()
IGNORED_LOCAL_CACHE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv"}
KAG_RECORD_FILES = {
    "node": [
        "kag/nodes/source_home.json",
        "kag/nodes/storage_boundary.json",
    ],
    "edge": [
        "kag/edges/source_routes_to_storage_boundary.json",
    ],
    "index": [
        "kag/indexes/source_inventory.json",
    ],
    "projection": [
        "kag/projections/source_return.json",
    ],
    "receipt": [
        "kag/receipts/validation_receipt.json",
    ],
}
KAG_REQUIRED_RECORD_CLASSES = set(KAG_RECORD_FILES)


def _documented_commands(text: str) -> list[str]:
    commands = [match.strip() for match in COMMAND_SPAN_RE.findall(text)]
    commands.extend(line.strip() for line in text.splitlines() if line.strip().startswith("aoa-course "))
    return commands


def _has_exact_documented_command(text: str, command: str) -> bool:
    return command in _documented_commands(text)


def _command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _is_fixture_bootstrap_command(command: str) -> bool:
    tokens = _command_tokens(command)
    return tokens[:3] == ["aoa-course", "bootstrap", "fixture"]


def _check_agent_install_route_commands(agent_install_raw: str, errors: list[str]) -> None:
    if "aoa-course readiness --run starter-fixture" not in agent_install_raw or "connector_readiness" not in agent_install_raw:
        errors.append("Agent install route missing connector readiness check")
    if not _has_exact_documented_command(agent_install_raw, BOOTSTRAP_FIXTURE_INSTALL_COMMAND):
        errors.append("Agent install route missing exact fixture bootstrap command")
    for command in _documented_commands(agent_install_raw):
        if _is_fixture_bootstrap_command(command) and "--platform" in _command_tokens(command):
            if PLATFORM_NARROWED_BOOTSTRAP_ERROR not in errors:
                errors.append(PLATFORM_NARROWED_BOOTSTRAP_ERROR)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    errors: list[str] = []
    warnings: list[str] = []
    for rel in REQUIRED_FILES:
        if not (repo_root / rel).is_file():
            errors.append(f"missing required file: {rel}")
    for rel in REQUIRED_DIRS:
        if not (repo_root / rel).is_dir():
            errors.append(f"missing required directory: {rel}")
    for name in REQUIRED_SCHEMAS:
        path = repo_root / "connector" / "schemas" / name
        if not path.is_file():
            errors.append(f"missing schema: connector/schemas/{name}")
        else:
            _load_json(path, errors)
    for path in [*repo_root.glob("connector/fixtures/**/*.json"), *repo_root.glob("evals/suites/**/*.json"), *repo_root.glob("kag/**/*.json")]:
        _load_json(path, errors)
    gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8") if (repo_root / ".gitignore").exists() else ""
    env_example = (repo_root / ".env.example").read_text(encoding="utf-8") if (repo_root / ".env.example").exists() else ""
    for pattern in REQUIRED_GITIGNORE:
        if pattern.startswith("AOA_"):
            if pattern not in env_example:
                errors.append(f".env.example missing storage variable: {pattern}")
        elif pattern not in gitignore:
            errors.append(f".gitignore missing heavy/private pattern: {pattern}")
    for rel in FORBIDDEN_HEAVY_ROOTS:
        if (repo_root / rel).exists():
            errors.append(f"heavy/private artifact path exists inside repository root: {rel}")
    tracked_files = set(_tracked_files(repo_root, errors))
    for rel in FORBIDDEN_GENERATED_GIT_FILES:
        if rel in tracked_files:
            errors.append(f"generated KAG file must stay out of git: {rel}")
    for path in repo_root.rglob("*"):
        if ".git" in path.parts:
            continue
        rel_parts = path.relative_to(repo_root).parts
        if any(part in IGNORED_LOCAL_CACHE_DIR_NAMES for part in rel_parts):
            continue
        if rel_parts and rel_parts[0] == ".connector-state":
            continue
        if path.is_dir() and rel_parts and rel_parts[0] in FORBIDDEN_HEAVY_ROOTS and not _is_allowed_kag_indexes(rel_parts):
            errors.append(f"forbidden generated/private directory exists inside repository: {path.relative_to(repo_root)}")
    _check_kag_provider(repo_root, errors)
    _check_text(repo_root, errors, warnings)
    payload = {
        "schema": "aoa_course_connector_validation_v1",
        "status": "ok" if not errors else "error",
        "repo_root": str(repo_root),
        "errors": errors,
        "warnings": warnings,
        "checked": {
            "required_files": len(REQUIRED_FILES),
            "required_dirs": len(REQUIRED_DIRS),
            "schemas": len(REQUIRED_SCHEMAS),
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1


def _load_json(path: Path, errors: list[str]) -> None:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid json {path}: {exc}")


def _read_json(path: Path, errors: list[str]) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid json {path}: {exc}")
    except OSError as exc:
        errors.append(f"unable to read json {path}: {exc}")
    return {}


def _tracked_files(repo_root: Path, errors: list[str]) -> list[str]:
    if not (repo_root / ".git").exists():
        return []
    try:
        import subprocess

        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:  # pragma: no cover - defensive validator path
        errors.append(f"unable to list tracked files: {exc}")
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _check_kag_provider(repo_root: Path, errors: list[str]) -> None:
    manifest = _read_json(repo_root / "kag" / "manifest.json", errors)
    if not isinstance(manifest, dict):
        errors.append("KAG manifest must be a JSON object")
        return
    if manifest.get("schema_version") != "aoa-local-kag-manifest-v1":
        errors.append("KAG manifest schema_version must be aoa-local-kag-manifest-v1")
    if manifest.get("repo") != "aoa-course-connector":
        errors.append("KAG manifest repo must be aoa-course-connector")
    if manifest.get("owner_surface") != "kag/AGENTS.md":
        errors.append("KAG manifest owner_surface must be kag/AGENTS.md")
    record_classes = manifest.get("record_classes")
    if not isinstance(record_classes, list):
        errors.append("KAG manifest record_classes must be a list")
    else:
        declared_record_classes = {record_class for record_class in record_classes if isinstance(record_class, str)}
        if declared_record_classes != KAG_REQUIRED_RECORD_CLASSES or len(declared_record_classes) != len(record_classes):
            errors.append("KAG manifest must declare node, edge, index, projection, and receipt classes")
    source_surfaces = manifest.get("source_surfaces")
    if not isinstance(source_surfaces, list) or len(source_surfaces) < 4:
        errors.append("KAG manifest must keep source_surfaces for source, boundary, route, and validation owners")
        source_surface_paths: set[str] = set()
    else:
        source_surface_paths = {
            str(surface.get("path"))
            for surface in source_surfaces
            if isinstance(surface, dict) and surface.get("path")
        }
    for required_surface in [
        "connector/README.md",
        "BOUNDARIES.md",
        "connector/SOURCE_POLICY.md",
        "connector/STORAGE_POLICY.md",
        "docs/RUNTIME_CONTRACT.md",
        "scripts/validate_connector.py",
    ]:
        if required_surface not in source_surface_paths:
            errors.append(f"KAG manifest missing source surface: {required_surface}")
    records = []
    seen_ids: set[str] = set()
    node_ids: set[str] = set()
    for expected_class, rels in KAG_RECORD_FILES.items():
        for rel in rels:
            payload = _read_json(repo_root / rel, errors)
            if not isinstance(payload, dict):
                errors.append(f"KAG record must be a JSON object: {rel}")
                continue
            _check_kag_record(repo_root, rel, payload, expected_class, errors)
            local_id = payload.get("local_id")
            if isinstance(local_id, str):
                if local_id in seen_ids:
                    errors.append(f"KAG record local_id repeated: {local_id}")
                seen_ids.add(local_id)
                if expected_class == "node":
                    node_ids.add(local_id)
            records.append((rel, expected_class, payload))
    for rel, expected_class, payload in records:
        if expected_class == "edge":
            for key in ("from_id", "to_id"):
                if payload.get(key) not in node_ids:
                    errors.append(f"KAG edge {rel} {key} must reference a local node")
            if not payload.get("edge_trace"):
                errors.append(f"KAG edge {rel} must keep edge_trace")
        if expected_class in {"index", "projection"}:
            ids = payload.get("source_record_ids")
            if not isinstance(ids, list) or not ids:
                errors.append(f"KAG {expected_class} record {rel} must keep source_record_ids")
            else:
                missing = [str(record_id) for record_id in ids if record_id not in seen_ids]
                if missing:
                    errors.append(f"KAG {expected_class} record {rel} references unknown records: {', '.join(missing)}")
        if expected_class == "receipt" and not payload.get("fallback_route"):
            errors.append(f"KAG receipt {rel} must keep fallback_route")


def _check_kag_record(repo_root: Path, rel: str, payload: dict[str, object], expected_class: str, errors: list[str]) -> None:
    if payload.get("schema_version") != "aoa-local-kag-record-v1":
        errors.append(f"KAG record {rel} schema_version must be aoa-local-kag-record-v1")
    if payload.get("repo") != "aoa-course-connector":
        errors.append(f"KAG record {rel} repo must be aoa-course-connector")
    if payload.get("record_class") != expected_class:
        errors.append(f"KAG record {rel} class must be {expected_class}")
    if not isinstance(payload.get("local_id"), str) or not payload.get("local_id"):
        errors.append(f"KAG record {rel} must keep local_id")
    _check_source_refs(repo_root, rel, payload.get("source_refs"), errors)
    freshness = payload.get("freshness")
    if not isinstance(freshness, dict):
        errors.append(f"KAG record {rel} must keep freshness")
    elif not freshness.get("checked_ref"):
        errors.append(f"KAG record {rel} freshness must keep checked_ref")


def _check_source_refs(repo_root: Path, rel: str, source_refs: object, errors: list[str]) -> None:
    if not isinstance(source_refs, list) or not source_refs:
        errors.append(f"KAG record {rel} must keep source_refs")
        return
    for source_ref in source_refs:
        if not isinstance(source_ref, dict):
            errors.append(f"KAG record {rel} source_refs entries must be objects")
            continue
        path = source_ref.get("path")
        if not isinstance(path, str) or not path:
            errors.append(f"KAG record {rel} source_ref missing path")
        elif not (repo_root / path).exists():
            errors.append(f"KAG record {rel} source_ref missing local file: {path}")


def _check_text(repo_root: Path, errors: list[str], warnings: list[str]) -> None:
    agents = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    source_policy = (repo_root / "connector" / "SOURCE_POLICY.md").read_text(encoding="utf-8").casefold()
    storage_policy = (repo_root / "connector" / "STORAGE_POLICY.md").read_text(encoding="utf-8")
    readme_raw = (repo_root / "README.md").read_text(encoding="utf-8")
    readme = readme_raw.casefold()
    cli_usage_raw = (repo_root / "docs" / "CLI_USAGE.md").read_text(encoding="utf-8")
    agent_install_raw = (repo_root / "docs" / "AGENT_INSTALL_ROUTE.md").read_text(encoding="utf-8")
    status_doc_raw = (repo_root / "docs" / "STATUS.md").read_text(encoding="utf-8")
    readiness_raw = (repo_root / "src" / "aoa_course_connector" / "readiness.py").read_text(encoding="utf-8")
    cli_raw = (repo_root / "src" / "aoa_course_connector" / "cli.py").read_text(encoding="utf-8")
    connection_profile_raw = (repo_root / "src" / "aoa_course_connector" / "connection_profile.py").read_text(encoding="utf-8")
    status_raw = (repo_root / "src" / "aoa_course_connector" / "status.py").read_text(encoding="utf-8")
    mcp_server_raw = (repo_root / "src" / "aoa_course_connector" / "mcp" / "server.py").read_text(encoding="utf-8")
    browser_state_raw = (repo_root / "src" / "aoa_course_connector" / "auth" / "browser_state.py").read_text(encoding="utf-8")
    bootstrap_raw = (repo_root / "src" / "aoa_course_connector" / "bootstrap.py").read_text(encoding="utf-8")
    adapters_raw = (repo_root / "src" / "aoa_course_connector" / "adapters" / "__init__.py").read_text(encoding="utf-8").casefold()
    sources_raw = (repo_root / "src" / "aoa_course_connector" / "sources.py").read_text(encoding="utf-8").casefold()
    manifest_raw = (repo_root / "connector" / "manifests" / "connector_manifest.yaml").read_text(encoding="utf-8").casefold()
    architecture_doc = (repo_root / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8").casefold()
    clean_api_doc = (repo_root / "docs" / "CLEAN_API_ADAPTERS.md").read_text(encoding="utf-8").casefold()
    mcp = (repo_root / "docs" / "MCP_USAGE.md").read_text(encoding="utf-8")
    if "build-semantic-index --run stepik-fixture" not in agents:
        errors.append("AGENTS route missing Stepik semantic index build before hybrid answer-quality eval")
    if PUBLIC_STATUS_GETCOURSE_SOURCE_ID_RE.search(status_doc_raw):
        errors.append("docs/STATUS.md must not expose deterministic runtime-only GetCourse source IDs")
    if "build-semantic-index --help" not in agents:
        errors.append("AGENTS route missing semantic provider option help check")
    if "eval live-calibration" not in agents or "calibration build" not in agents or "calibration intake" not in agents or "calibration connected-run" not in agents or "calibration status" not in agents or "calibration query" not in agents:
        errors.append("AGENTS route missing live calibration packet/intake validation")
    for line in agents.splitlines():
        if "calibration connected-run --mode live" in line and "--allow-network" in line:
            errors.append("AGENTS validation must not require live connected-run --allow-network")
    portable_packet_path = "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/connected-live-calibration/calibration/live_calibration_packet.json"
    fixture_packet_path = "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/live-calibration-fixture/calibration/live_calibration_packet.json"
    if fixture_packet_path not in agents:
        errors.append("AGENTS route missing portable fixture live-calibration packet path")
    for label, text in [
        ("README live calibration route", readme_raw),
        ("CLI usage live calibration route", cli_usage_raw),
    ]:
        if portable_packet_path not in text:
            errors.append(f"{label} missing portable connected-live-calibration packet path")
    if "calibration connected-run --mode fixture" not in agent_install_raw or "calibration connected-run --mode live --allow-network" not in agent_install_raw or "connected_run_query" not in agent_install_raw:
        errors.append("Agent install route missing executable connected-run plan")
    if "ARTIFACT_ROOT_EXPR" not in readiness_raw or "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}" not in readiness_raw:
        errors.append("Connected-source plan code missing portable artifact root expression")
    if "runs/{calibration_run}/calibration/live_calibration_packet.json" not in readiness_raw:
        errors.append("Connected-source plan code missing runs/<run> calibration artifact path")
    for token in ["mcp_tool_call", "mcp_command", "_mcp_call_command"]:
        if token not in readiness_raw:
            errors.append(f"Connected-source plan code missing MCP connected-run plan token: {token}")
    for token in ["state_file_candidates", "_host_state_file_candidates", "source_id_flags"]:
        if token not in readiness_raw:
            errors.append(f"Readiness code missing per-host auth candidate token: {token}")
    if "preflight connected-plan --live-scope bounded" not in agents or "connected_source_plan" not in agents:
        errors.append("AGENTS route missing connected-source launch plan validation")
    if "mcp call live_preflight '{}'" not in agents or "connected_source_plan '{\"live_scope\":\"bounded\"}'" not in agents:
        errors.append("AGENTS route missing default all-priority MCP connected-source validation")
    if "readiness --run starter-fixture" not in agents or "connector_readiness" not in agents:
        errors.append("AGENTS route missing connector readiness validation")
    if "connect profile --name operator-live" not in agents or "connect inspect" not in agents or "connect status" not in agents or "connect apply" not in agents:
        errors.append("AGENTS route missing connection profile validation")
    if "mcp call connection_profile_inspect" not in agents:
        errors.append("AGENTS route missing MCP connection_profile_inspect validation")
    if "mcp call connection_profile_status" not in agents:
        errors.append("AGENTS route missing MCP connection_profile_status validation")
    if "bootstrap fixture --run starter-fixture --connected-run connected-calibration" not in agents:
        errors.append("AGENTS route missing fixture bootstrap validation")
    if "aoa-course connect profile" not in agent_install_raw or "aoa_course_connection_profile_v1" not in agent_install_raw or "connection_profile_inspect" not in agent_install_raw or "connection_profile_status" not in agent_install_raw or "aoa_course_connection_profile_status_v1" not in agent_install_raw:
        errors.append("Agent install route missing connection profile plan")
    if "--expect-origin-contains" not in agent_install_raw or "expected_origin_matched" not in agent_install_raw:
        errors.append("Agent install route missing capture expected-origin plan")
    _check_agent_install_route_commands(agent_install_raw, errors)
    if "refresh query" not in agents or "refresh_plan" not in agents:
        errors.append("AGENTS route missing refresh query/refresh_plan validation")
    if "eval browser-transcripts" not in agents:
        errors.append("AGENTS route missing browser transcript/caption eval")
    if "preflight semantic-provider --run starter-fixture --require-ready" not in agents:
        errors.append("AGENTS route missing semantic provider preflight validation")
    for token in ["mcp call graph_neighbors", "mcp call freshness_report", "mcp call evidence_report", "mcp call connected_run", "mcp call connected_run_status", "mcp call connected_run_query", "mcp call ingest_status", "mcp call semantic_provider_preflight"]:
        if token not in agents:
            errors.append(f"AGENTS route missing MCP evidence/graph token: {token}")
    for token in ["getcourse", "skillspace", "coursera", "teachable", "thinkific", "kajabi", "browser_session", "api_token", "offline_export", "drm", "authorized", "write actions"]:
        if token not in source_policy:
            errors.append(f"source policy missing boundary token: {token}")
    for token in ["getcourse", "skillspace", "stepik", "moodle", "canvas", "coursera", "teachable", "thinkific", "kajabi"]:
        if token not in adapters_raw:
            errors.append(f"adapter registry missing platform: {token}")
        if token not in sources_raw:
            errors.append(f"source registry platform set missing platform: {token}")
        if token not in manifest_raw:
            errors.append(f"connector manifest missing platform: {token}")
    for token in ["coursera", "teachable", "thinkific", "kajabi", "future platform"]:
        if token not in architecture_doc:
            errors.append(f"Architecture doc missing future platform topology token: {token}")
        if token not in clean_api_doc:
            errors.append(f"Clean API adapter doc missing future platform topology token: {token}")
    for var in ["AOA_COURSE_DATA_ROOT", "AOA_COURSE_CACHE_ROOT", "AOA_COURSE_AUTH_ROOT", "AOA_COURSE_ARTIFACT_ROOT"]:
        if var not in storage_policy:
            errors.append(f"storage policy missing variable: {var}")
    for token in ["index", "graph", "evidence", "mcp", "getcourse", "skillspace", "stepik"]:
        if token not in readme:
            warnings.append(f"README weakly covers token: {token}")
    if "aoa-course-connector-mcp" not in mcp:
        errors.append("MCP usage missing server package name")
    for token in ["json-rpc", "stdio", "tools/list", "tools/call", "structuredcontent"]:
        if token not in mcp.casefold():
            errors.append(f"MCP usage missing stdio token: {token}")
    for token in ["graph_neighbors", "freshness_report", "evidence_report", "refresh_plan", "ingest_status", "connector_readiness", "connection_profile_inspect", "connection_profile_status", "semantic_provider_preflight", "aoa_course_connector_readiness_v1", "aoa_course_connection_profile_v1", "aoa_course_connection_profile_inspection_v1", "aoa_course_connection_profile_status_v1", "aoa_course_connection_profile_readiness_v1", "aoa_course_semantic_provider_preflight_v1", "operational_ready", "connected_live_ready", "semantic provider", "agent_query_ready", "source url", "authority report", "refresh report", "refresh_hint"]:
        if token not in mcp.casefold():
            errors.append(f"MCP usage missing evidence/graph token: {token}")
    for token in ["live_preflight", "connected_source_plan", "connected_run", "connected_run_status", "connected_run_query", "source_answer", "sources_answer", "aoa_course_connected_run_query_packet_v1", "aoa_course_source_answer_packet_v1", "aoa_course_sources_answer_packet_v1", "connected_run_plan", "mcp_tool_call", "mcp_command", "source_selection", "query_plan", "repair_lanes", "mcp_commands", "link_pattern", "live_scope", "include_step_sources", "full-course", "network_touched", "secret values", "structuredcontent", "full priority set", "fixture_or_example_source", "operator_live_candidate", "source_ids", "selected_source_ids"]:
        if token not in mcp.casefold():
            errors.append(f"MCP usage missing live preflight token: {token}")
    for token in ["unsupported protocol version", "2025-11-25"]:
        if token not in mcp.casefold():
            errors.append(f"MCP usage missing protocol negotiation token: {token}")
    for label, text in [
        ("README connection profile route", readme_raw),
        ("CLI usage connection profile route", cli_usage_raw),
        ("connection profile code", connection_profile_raw),
        ("MCP server connection profile route", mcp_server_raw),
    ]:
        for token in ["aoa_course_connection_profile_v1", "connection_profile_inspect", "connection_profile_status", "aoa_course_connection_profile_status_v1", "ready_for_connected_run", "network_touched", "token"]:
            if token not in text:
                errors.append(f"{label} missing connection profile token: {token}")
    query_doc = (repo_root / "docs" / "QUERY_MODEL.md").read_text(encoding="utf-8").casefold()
    for token in [
        "build-semantic-index",
        "semantic",
        "hybrid",
        "local_hashing_v1",
        "http_json_v1",
        "provider_config",
        "embedding-token-env",
        "token value",
        "semantic_search",
        "hybrid_search",
        "source id",
        "answer-quality",
        "rank_score",
        "freshness-ranking",
        "authority-ranking",
        "adapter-authority",
        "authority_tier",
        "refresh_hint",
        "refresh_report",
        "refresh query",
        "aoa_course_refresh_cycle_v1",
        "local_rebuild_commands",
        "preflight connected-plan",
        "registry_match",
        "--source-id",
    ]:
        if token not in query_doc:
            errors.append(f"Query model doc missing token: {token}")
    cli_usage_doc = (repo_root / "docs" / "CLI_USAGE.md").read_text(encoding="utf-8").casefold()
    for token in ["sync stepik-fixture", "sync browser-fixture", "--source-id", "source_ids", "selected_source_ids", "--expect-origin-contains", "expected_origin_matched", "large source registry", "calibration connected-run", "calibration query", "aoa_course_connected_run_query_packet_v1", "mcp call connected_run", "mcp_tool_call", "mcp_command", "connected_run_plan", "calibration status", "repair_lanes", "partial connected-run", "fixture bootstrap", "--mode fixture", "--allow-network", "--link-pattern", "--max-lessons", "--max-pages", "--max-sources", "--live-scope", "--include-step-sources", "bootstrap fixture", "aoa_course_fixture_bootstrap_receipt_v1", "getcourse, skillspace, and stepik", "cover getcourse, skillspace, and stepik together", "readiness --run starter-fixture", "preflight semantic-provider", "semantic_provider_preflight", "aoa_course_semantic_provider_preflight_v1", "embedding_token_env", "token_env_present", "token_value_logged", "aoa_course_connector_readiness_v1", "operational_ready", "connected_live_ready", "semantic_provider_ready"]:
        if token not in cli_usage_doc:
            errors.append(f"CLI usage doc missing source-scoped sync token: {token}")
    verifier_raw = (repo_root / "scripts" / "verify_agent_install_route.py").read_text(encoding="utf-8")
    if "connector_readiness" not in verifier_raw or "connected_source_plan" not in verifier_raw:
        errors.append("Agent install verifier missing connector readiness/plan route")
    if '"eval", "install-route"' not in verifier_raw:
        errors.append("Agent install verifier missing executable install-route eval")
    if '"mcp", "call", "answer"' not in verifier_raw or '"name":"answer"' not in verifier_raw:
        errors.append("Agent install verifier missing direct MCP answer proof")
    if '"mcp", "call", "connected_run"' not in verifier_raw or '"name":"connected_run"' not in verifier_raw:
        errors.append("Agent install verifier missing MCP connected-run proof")
    if '"mcp", "call", "connected_run_query"' not in verifier_raw or '"name":"connected_run_query"' not in verifier_raw:
        errors.append("Agent install verifier missing MCP connected-run query proof")
    connected_run_raw = (repo_root / "src" / "aoa_course_connector" / "calibration" / "connected_run.py").read_text(encoding="utf-8")
    for token in ["query_connected_calibration", "aoa_course_connected_run_query_packet_v1", "_evidence_report_from_answer", "repair_lanes", "repair_lane_count", "network_gate", "source_auth_or_readiness", "source_selection", "source_sync", "live_smoke_or_selector", "calibration_packet_intake"]:
        if token not in connected_run_raw:
            errors.append(f"Connected-run code missing repair lane token: {token}")
    for token in [
        "def connector_readiness",
        "aoa_course_connector_readiness_v1",
        "operational_ready",
        "connected_live_ready",
        "REQUIRED_MCP_TOOLS",
        "load_connected_calibration_status",
        "connected_source_plan",
        "connected_run",
        "connected_run_plan",
        "connected_run_query",
        "link_pattern",
        "max_lessons",
        "max_pages",
        "max_sources",
        "live_scope",
        "include_step_sources",
        "semantic_provider_preflight",
        "semantic_provider_ready",
        "aoa_course_semantic_provider_preflight_v1",
        "source_ids",
        "selected_source_ids",
        "network_touched",
        "_connected_run_repair_commands",
        "repair_lanes",
        "calibration status --run",
    ]:
        if token not in status_raw:
            errors.append(f"Connector status code missing readiness token: {token}")
    for token in [
        "expected_origin_contains",
        "expected_origin_matched",
        "capture_command += f\" --expect-origin-contains",
        "inspect_browser_state(resolved_state, expect_origin_contains=expected_origin or None, platform=platform)",
        "STRICT_AUTH_SIGNAL_PLATFORMS",
    ]:
        if token not in browser_state_raw:
            errors.append(f"Browser auth state code missing expected-origin token: {token}")
    for token in [
        "def bootstrap_fixture",
        "aoa_course_fixture_bootstrap_receipt_v1",
        "materialize_fixture",
        "build_keyword_index",
        "build_semantic_index",
        "build_graph",
        "run_connected_calibration",
        "connector_readiness",
        "network_touched",
    ]:
        if token not in bootstrap_raw:
            errors.append(f"Bootstrap code missing route token: {token}")
    eval_readme = (repo_root / "evals" / "README.md").read_text(encoding="utf-8").casefold()
    for token in ["aoa-evals", "verdict", "scoring", "regression", "proof doctrine", "answer-quality", "freshness-ranking", "authority-ranking", "adapter-authority", "live-calibration", "browser-transcripts"]:
        if token not in eval_readme:
            errors.append(f"Eval README missing token: {token}")
    live_calibration_raw = (repo_root / "docs" / "LIVE_CALIBRATION.md").read_text(encoding="utf-8")
    live_calibration_doc = live_calibration_raw.casefold()
    if portable_packet_path not in live_calibration_raw:
        errors.append("Live calibration doc missing portable connected-live-calibration packet path")
    if "$AOA_COURSE_ARTIFACT_ROOT/<run>" in live_calibration_raw:
        errors.append("Live calibration doc uses non-runtime artifact path without runs/<run>")
    for token in [
        "aoa_course_live_calibration_packet_v1",
        "aoa_course_connected_source_plan_v1",
        "aoa_course_live_calibration_intake_v1",
        "aoa_course_connected_calibration_run_receipt_v1",
        "aoa_course_connected_calibration_run_status_v1",
        "aoa_course_connected_run_query_packet_v1",
        "source_selection",
        "execution_options",
        "query_plan",
        "repair_lanes",
        "mcp_commands",
        "connected_run_query",
        "lesson_context",
        "evidence_report",
        "connected_run_plan",
        "link-pattern",
        "account.storage-state.json",
        "preflight connected-plan",
        "calibration connected-run",
        "connected_run_status",
        "allow-network",
        "live-scope bounded",
        "full-course",
        "include-step-sources",
        "calibration build",
        "calibration intake",
        "eval live-calibration",
        "smoke browser-live",
        "smoke stepik-live",
        "preflight live",
        "connected_source_plan",
        "do not commit",
        "raw_paths_are_local_runtime_state",
        "contains_secret_values",
        "transcript_count_total",
        "caption_sidecar_count_total",
        "caption_resource_error_count_total",
        "browser_reports_with_transcripts",
        "aoa-evals",
    ]:
        if token not in live_calibration_doc:
            errors.append(f"Live calibration doc missing token: {token}")
    stepik_doc = (repo_root / "docs" / "STEPIK.md").read_text(encoding="utf-8").casefold()
    for token in [
        "stepik-live",
        "stepik-fixture",
        "course -> sections -> units -> lessons -> steps",
        "stepik_api_token",
        "--full-course",
        "--batch-size",
        "--include-step-sources",
        "ids[]",
        "meta.has_next",
        "discover stepik",
        "discover stepik-account",
        "account discovery",
        "preflight live",
        "preflight connected-plan",
        "live-scope bounded",
        "sync stepik-fixture",
        "sync stepik-live",
        "sync status --run stepik-sync-fixture --platform stepik",
        "public_api",
        "sync-ready without `stepik_api_token`",
        "inactive or deleted enrollments",
        "smoke stepik-fixture",
        "smoke stepik-live",
        "aoa_course_stepik_smoke_report_v1",
    ]:
        if token not in stepik_doc:
            errors.append(f"Stepik doc missing token: {token}")
    browser_doc = (repo_root / "docs" / "BROWSER_SESSION.md").read_text(encoding="utf-8").casefold()
    for token in [
        "browser-fixture",
        "browser-snapshot",
        "browser-live",
        "crawl browser-fixture",
        "crawl browser-live",
        "discover browser-fixture",
        "discover browser-live",
        "sync browser-fixture",
        "sync browser-live",
        "smoke browser-fixture",
        "smoke browser-snapshot",
        "smoke browser-live",
        "browser-transcripts",
        "transcript/caption",
        "caption sidecar",
        "resources[]",
        "transcript_count",
        "preflight live",
        "preflight connected-plan",
        "live-scope bounded",
        "source_ids",
        "sync status",
        "--register",
        "checkpoint",
        "progress",
        "comments",
        "pagination",
        "max-lessons",
        "max-sources",
        "max-pages",
        "getcourse",
        "skillspace",
        "playwright",
        "each source host",
        "pagination links before applying a custom",
        "fixture_or_example_source",
        "operator_live_candidate",
        "connected_run_plan.source_ids",
        "expected_origin_matched",
        "state_file_candidates",
        "per-host",
    ]:
        if token not in browser_doc:
            errors.append(f"Browser session doc missing token: {token}")


def _is_allowed_kag_indexes(rel_parts: tuple[str, ...]) -> bool:
    return len(rel_parts) == 2 and rel_parts[0] == "kag" and rel_parts[1] == "indexes"


if __name__ == "__main__":
    raise SystemExit(main())
