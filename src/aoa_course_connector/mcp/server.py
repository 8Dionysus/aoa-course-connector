"""Small dependency-free MCP-shaped tool dispatcher.

The full runtime registration belongs in abyss-stack. This module keeps the
tool contract testable from the public repository.
"""

from __future__ import annotations

import json
import sys

from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.query import freshness_report, graph_neighbors, query_keyword_index, render_answer_packet
from aoa_course_connector.sources import load_registry
from aoa_course_connector.sync import load_sync_status


TOOLS = [
    {"name": "list_sources", "description": "List configured course sources."},
    {"name": "ingest_status", "description": "Inspect local ingest run status."},
    {"name": "sync_status", "description": "Inspect source sync checkpoints."},
    {"name": "search", "description": "Search indexed course knowledge."},
    {"name": "lesson_context", "description": "Return source-backed lesson context for a query."},
    {"name": "graph_neighbors", "description": "Traverse course graph neighborhoods."},
    {"name": "freshness_report", "description": "Report result freshness states."},
]


def tools_manifest() -> dict[str, object]:
    return {"schema": "aoa_course_mcp_tools_v1", "server": "aoa-course-connector-mcp", "tools": TOOLS}


def call_tool(name: str, arguments: dict[str, object] | None = None) -> dict[str, object]:
    args = arguments or {}
    roots = StorageRoots.from_env(find_repo_root())
    run_id = str(args.get("run") or "starter-fixture")
    if name == "list_sources":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "registry": load_registry(roots.data)}
    if name == "ingest_status":
        return _ingest_status(roots, run_id)
    if name == "sync_status":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "sync": load_sync_status(roots, sync_run_id=str(args.get("sync_run") or ""), platform=str(args.get("platform") or ""))}
    if name == "search":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "results": query_keyword_index(roots, str(args.get("query") or ""), run_id, int(args.get("limit") or 5))}
    if name == "lesson_context":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "answer_packet": render_answer_packet(roots, str(args.get("query") or ""), run_id, int(args.get("limit") or 5))}
    if name == "graph_neighbors":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "graph": graph_neighbors(roots, str(args.get("node_id") or ""), run_id, int(args.get("limit") or 20))}
    if name == "freshness_report":
        return {"schema": "aoa_course_mcp_result_v1", "tool": name, "freshness": freshness_report(roots, run_id)}
    raise ValueError(f"unknown MCP tool: {name}")


def main() -> int:
    if sys.stdin.isatty():
        print(json.dumps(tools_manifest(), indent=2, sort_keys=True))
        return 0
    for line in sys.stdin:
        request = json.loads(line)
        name = request.get("tool") or request.get("name")
        arguments = request.get("arguments") or {}
        try:
            result = call_tool(str(name), arguments)
            print(json.dumps({"status": "ok", "result": result}, sort_keys=True), flush=True)
        except Exception as exc:  # pragma: no cover - server safety net
            print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), flush=True)
    return 0


def _ingest_status(roots: StorageRoots, run_id: str) -> dict[str, object]:
    data_dir = roots.data / "runs" / run_id
    artifact_dir = roots.artifact / "runs" / run_id
    return {
        "schema": "aoa_course_ingest_status_v1",
        "tool": "ingest_status",
        "run_id": run_id,
        "normalized_exists": (data_dir / "normalized" / "course_bundle.json").exists(),
        "index_exists": (artifact_dir / "indexes" / "keyword_index.json").exists(),
        "graph_exists": (artifact_dir / "graphs" / "course_graph.json").exists(),
    }


if __name__ == "__main__":
    raise SystemExit(main())
