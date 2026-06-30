"""Fixture-safe bootstrap routes for fresh connector installs."""

from __future__ import annotations

from pathlib import Path

from aoa_course_connector.calibration.connected_run import run_connected_calibration
from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index, build_semantic_index
from aoa_course_connector.ingest import materialize_fixture
from aoa_course_connector.status import connector_readiness
from aoa_course_connector.storage import create_storage_roots


DEFAULT_BOOTSTRAP_RUN = "starter-fixture"
DEFAULT_BOOTSTRAP_CONNECTED_RUN = "connected-calibration"


def bootstrap_fixture(
    repo_root: Path,
    roots: StorageRoots,
    *,
    run_id: str = DEFAULT_BOOTSTRAP_RUN,
    fixture: Path | None = None,
    connected_run: str = DEFAULT_BOOTSTRAP_CONNECTED_RUN,
    platforms: list[str] | None = None,
    query: str | None = None,
    skip_connected: bool = False,
    mcp_tool_names: list[str] | set[str] | None = None,
) -> dict[str, object]:
    """Build the local starter proof and optional fixture connected-run receipt."""

    created = create_storage_roots(roots)
    materialize = materialize_fixture(roots, run_id=run_id, fixture=fixture)
    keyword_path = build_keyword_index(roots, run_id=run_id)
    semantic_path = build_semantic_index(roots, run_id=run_id)
    graph_path = build_graph(roots, run_id=run_id)
    connected_receipt: dict[str, object] | None = None
    if not skip_connected:
        connected_receipt = run_connected_calibration(
            roots,
            run_id=connected_run,
            mode="fixture",
            platforms=platforms,
            query=query,
        )
    readiness = connector_readiness(
        repo_root,
        roots,
        runs=[run_id],
        platforms=platforms,
        connected_run=connected_run,
        query=query,
        mcp_tool_names=mcp_tool_names,
    )
    return {
        "schema": "aoa_course_fixture_bootstrap_receipt_v1",
        "status": "ok" if readiness.get("operational_ready") else "partial",
        "run_id": run_id,
        "connected_run": connected_run,
        "network_touched": False,
        "read_only": False,
        "storage": {
            "created": created,
            "mode": roots.mode,
            "roots": roots.as_dict(),
        },
        "materialize": _compact_mapping(
            materialize,
            [
                "schema",
                "status",
                "run_id",
                "receipt_path",
                "raw_path",
                "normalized_path",
                "course_count",
                "evidence_count",
                "network_touched",
            ],
        ),
        "artifacts": {
            "keyword_index_path": str(keyword_path),
            "semantic_index_path": str(semantic_path),
            "graph_path": str(graph_path),
        },
        "connected_receipt": _compact_connected_receipt(connected_receipt) if connected_receipt else None,
        "readiness": readiness,
        "next_commands": _next_commands(readiness, run_id=run_id, connected_run=connected_run),
    }


def _compact_mapping(payload: dict[str, object], keys: list[str]) -> dict[str, object]:
    return {key: payload.get(key) for key in keys if key in payload}


def _compact_connected_receipt(receipt: dict[str, object]) -> dict[str, object]:
    artifacts = receipt.get("artifacts") if isinstance(receipt.get("artifacts"), dict) else {}
    return {
        "schema": receipt.get("schema"),
        "status": receipt.get("status"),
        "run_id": receipt.get("run_id"),
        "mode": receipt.get("mode"),
        "platforms": receipt.get("platforms", []),
        "network_touched": bool(receipt.get("network_touched")),
        "stage_count": receipt.get("stage_count"),
        "receipt_path": receipt.get("receipt_path"),
        "packet_path": artifacts.get("packet_path"),
        "intake_path": artifacts.get("intake_path"),
        "plan_path": artifacts.get("plan_path"),
        "runbook_path": artifacts.get("runbook_path"),
    }


def _next_commands(readiness: dict[str, object], *, run_id: str, connected_run: str) -> list[str]:
    commands = [
        f'aoa-course answer "course-specific question" --run {run_id}',
        f"aoa-course calibration status --run {connected_run}",
        f'aoa-course mcp call connector_readiness \'{{"runs":["{run_id}"],"connected_run":"{connected_run}"}}\'',
    ]
    if not readiness.get("operational_ready"):
        commands.extend([str(command) for command in readiness.get("next_commands", []) if str(command)])
    return list(dict.fromkeys(commands))
