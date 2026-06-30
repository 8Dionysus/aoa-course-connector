"""Command line interface for the AoA course connector."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aoa_course_connector.adapters import adapter_list
from aoa_course_connector.auth import browser_state_plan
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index
from aoa_course_connector.ingest import materialize_fixture, materialize_stepik_fixture, materialize_stepik_live
from aoa_course_connector.mcp.server import call_tool, tools_manifest
from aoa_course_connector.query import graph_neighbors, query_keyword_index, render_answer_packet, write_answer_packet
from aoa_course_connector.sources import load_registry, registry_path, upsert_source
from aoa_course_connector.storage import create_storage_roots, storage_status


DEFAULT_RUN = "starter-fixture"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aoa-course")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor")
    doctor.set_defaults(func=cmd_doctor)

    init = sub.add_parser("init")
    init.set_defaults(func=cmd_init)

    storage = sub.add_parser("storage")
    storage_sub = storage.add_subparsers(dest="storage_command", required=True)
    status = storage_sub.add_parser("status")
    status.add_argument("--measure", action="store_true")
    status.set_defaults(func=cmd_storage_status)

    adapters = sub.add_parser("adapters")
    adapters_sub = adapters.add_subparsers(dest="adapters_command", required=True)
    adapters_sub.add_parser("list").set_defaults(func=cmd_adapters_list)

    sources = sub.add_parser("sources")
    sources_sub = sources.add_subparsers(dest="sources_command", required=True)
    sources_add = sources_sub.add_parser("add")
    sources_add.add_argument("source_ref")
    sources_add.add_argument("--platform", required=True)
    sources_add.add_argument("--title")
    sources_add.add_argument("--access-mode")
    sources_add.add_argument("--disabled", action="store_true")
    sources_add.set_defaults(func=cmd_sources_add)
    sources_sub.add_parser("list").set_defaults(func=cmd_sources_list)

    auth = sub.add_parser("auth")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)
    browser = auth_sub.add_parser("plan-browser-state")
    browser.add_argument("platform")
    browser.add_argument("source_ref")
    browser.set_defaults(func=cmd_auth_plan_browser_state)

    discover = sub.add_parser("discover")
    discover_sub = discover.add_subparsers(dest="discover_command", required=True)
    discover_fixture = discover_sub.add_parser("fixture")
    discover_fixture.add_argument("--run", default=DEFAULT_RUN)
    discover_fixture.set_defaults(func=cmd_discover_fixture)
    discover_stepik = discover_sub.add_parser("stepik")
    discover_stepik.add_argument("course_id", type=int)
    discover_stepik.add_argument("--from-fixture", action="store_true")
    discover_stepik.set_defaults(func=cmd_discover_stepik)

    materialize = sub.add_parser("materialize")
    materialize_sub = materialize.add_subparsers(dest="materialize_command", required=True)
    fixture = materialize_sub.add_parser("fixture")
    fixture.add_argument("--run", default=DEFAULT_RUN)
    fixture.add_argument("--fixture", type=Path)
    fixture.set_defaults(func=cmd_materialize_fixture)
    stepik_fixture = materialize_sub.add_parser("stepik-fixture")
    stepik_fixture.add_argument("--run", default="stepik-fixture")
    stepik_fixture.add_argument("--fixture", type=Path)
    stepik_fixture.set_defaults(func=cmd_materialize_stepik_fixture)
    stepik_live = materialize_sub.add_parser("stepik-live")
    stepik_live.add_argument("course_id", type=int)
    stepik_live.add_argument("--run")
    stepik_live.add_argument("--token-env", default="STEPIK_API_TOKEN")
    stepik_live.add_argument("--max-sections", type=int, default=1)
    stepik_live.add_argument("--max-units-per-section", type=int, default=2)
    stepik_live.add_argument("--max-steps-per-lesson", type=int, default=5)
    stepik_live.set_defaults(func=cmd_materialize_stepik_live)

    ingest = sub.add_parser("ingest")
    ingest_sub = ingest.add_subparsers(dest="ingest_command", required=True)
    ingest_fixture = ingest_sub.add_parser("fixture")
    ingest_fixture.add_argument("--run", default=DEFAULT_RUN)
    ingest_fixture.add_argument("--fixture", type=Path)
    ingest_fixture.set_defaults(func=cmd_materialize_fixture)
    ingest_stepik_fixture = ingest_sub.add_parser("stepik-fixture")
    ingest_stepik_fixture.add_argument("--run", default="stepik-fixture")
    ingest_stepik_fixture.add_argument("--fixture", type=Path)
    ingest_stepik_fixture.set_defaults(func=cmd_materialize_stepik_fixture)

    build_index = sub.add_parser("build-index")
    build_index.add_argument("--run", default=DEFAULT_RUN)
    build_index.set_defaults(func=cmd_build_index)

    build_graph_parser = sub.add_parser("build-graph")
    build_graph_parser.add_argument("--run", default=DEFAULT_RUN)
    build_graph_parser.set_defaults(func=cmd_build_graph)

    query = sub.add_parser("query")
    query.add_argument("query")
    query.add_argument("--run", default=DEFAULT_RUN)
    query.add_argument("--limit", type=int, default=5)
    query.set_defaults(func=cmd_query)

    answer = sub.add_parser("answer")
    answer.add_argument("query")
    answer.add_argument("--run", default=DEFAULT_RUN)
    answer.add_argument("--limit", type=int, default=5)
    answer.set_defaults(func=cmd_answer)

    graph = sub.add_parser("graph")
    graph_sub = graph.add_subparsers(dest="graph_command", required=True)
    neighbors = graph_sub.add_parser("neighbors")
    neighbors.add_argument("node_id")
    neighbors.add_argument("--run", default=DEFAULT_RUN)
    neighbors.add_argument("--limit", type=int, default=20)
    neighbors.set_defaults(func=cmd_graph_neighbors)

    evidence = sub.add_parser("evidence")
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    inspect = evidence_sub.add_parser("inspect")
    inspect.add_argument("query")
    inspect.add_argument("--run", default=DEFAULT_RUN)
    inspect.set_defaults(func=cmd_evidence_inspect)

    eval_parser = sub.add_parser("eval")
    eval_sub = eval_parser.add_subparsers(dest="eval_command", required=True)
    eval_sub.add_parser("answer-packets").set_defaults(func=cmd_eval_answer_packets)
    eval_sub.add_parser("clean-api").set_defaults(func=cmd_eval_clean_api)

    mcp = sub.add_parser("mcp")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    mcp_sub.add_parser("tools").set_defaults(func=cmd_mcp_tools)
    mcp_call = mcp_sub.add_parser("call")
    mcp_call.add_argument("tool")
    mcp_call.add_argument("arguments", nargs="?", default="{}")
    mcp_call.set_defaults(func=cmd_mcp_call)
    return parser


def cmd_doctor(_args: argparse.Namespace) -> int:
    repo_root = find_repo_root()
    required = [
        "AGENTS.md",
        "README.md",
        "connector/SOURCE_POLICY.md",
        "connector/STORAGE_POLICY.md",
        "connector/fixtures/course/starter_course.json",
        "docs/ARCHITECTURE.md",
        "docs/MCP_USAGE.md",
        "docs/GETCOURSE.md",
        "docs/SKILLSPACE.md",
    ]
    missing = [rel for rel in required if not (repo_root / rel).exists()]
    roots = StorageRoots.from_env(repo_root)
    _emit(
        {
            "schema": "aoa_course_doctor_v1",
            "status": "ok" if not missing else "error",
            "repo_root": str(repo_root),
            "missing": missing,
            "storage": storage_status(repo_root, roots),
            "adapters": adapter_list(),
            "network_touched": False,
            "read_only": True,
        }
    )
    return 0 if not missing else 1


def cmd_init(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    _emit({"schema": "aoa_course_init_v1", "status": "ok", "created": create_storage_roots(roots), "network_touched": False})
    return 0


def cmd_storage_status(args: argparse.Namespace) -> int:
    repo_root = find_repo_root()
    _emit(storage_status(repo_root, StorageRoots.from_env(repo_root), measure=args.measure))
    return 0


def cmd_adapters_list(_args: argparse.Namespace) -> int:
    _emit({"schema": "aoa_course_adapters_v1", "adapters": adapter_list()})
    return 0


def cmd_sources_add(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    create_storage_roots(roots)
    try:
        source, path, state = upsert_source(
            roots.data,
            platform=args.platform,
            source_ref=args.source_ref,
            title=args.title,
            access_mode=args.access_mode,
            enabled=not args.disabled,
        )
    except ValueError as exc:
        _emit({"schema": "aoa_course_source_registry_receipt_v1", "status": "error", "error": str(exc)})
        return 2
    _emit({"schema": "aoa_course_source_registry_receipt_v1", "status": "ok", "state": state, "registry_path": str(path), "source": source})
    return 0


def cmd_sources_list(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    _emit({"schema": "aoa_course_source_registry_list_v1", "registry_path": str(registry_path(roots.data)), "registry": load_registry(roots.data)})
    return 0


def cmd_auth_plan_browser_state(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    create_storage_roots(roots)
    _emit(browser_state_plan(roots.auth, args.platform, args.source_ref))
    return 0


def cmd_discover_fixture(args: argparse.Namespace) -> int:
    repo_root = find_repo_root()
    fixture_path = repo_root / "connector/fixtures/course/starter_course.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    _emit(
        {
            "schema": "aoa_course_discovery_receipt_v1",
            "status": "ok",
            "run_id": args.run,
            "source_mode": "offline_fixture",
            "course_count": len(fixture.get("courses", [])),
            "fixture": str(fixture_path),
            "network_touched": False,
        }
    )
    return 0


def cmd_discover_stepik(args: argparse.Namespace) -> int:
    repo_root = find_repo_root()
    if args.from_fixture:
        fixture_path = repo_root / "connector/fixtures/stepik/starter_stepik_course.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        course = fixture.get("course", {})
        sections = fixture.get("sections", [])
        _emit(
            {
                "schema": "aoa_course_stepik_discovery_receipt_v1",
                "status": "ok",
                "source_mode": "stepik_fixture",
                "course_id": args.course_id,
                "course_title": course.get("title") if isinstance(course, dict) else None,
                "section_count": len(sections) if isinstance(sections, list) else 0,
                "fixture": str(fixture_path),
                "network_touched": False,
            }
        )
        return 0
    _emit(
        {
            "schema": "aoa_course_stepik_discovery_receipt_v1",
            "status": "planned",
            "source_mode": "stepik_live",
            "course_id": args.course_id,
            "next_command": f"aoa-course materialize stepik-live {args.course_id} --run stepik-course-{args.course_id}",
            "network_touched": False,
        }
    )
    return 0


def cmd_materialize_fixture(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = materialize_fixture(roots, run_id=args.run, fixture=args.fixture)
    _emit(receipt)
    return 0


def cmd_materialize_stepik_fixture(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = materialize_stepik_fixture(roots, run_id=args.run, fixture=args.fixture)
    _emit(receipt)
    return 0


def cmd_materialize_stepik_live(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    run_id = args.run or f"stepik-course-{args.course_id}"
    receipt = materialize_stepik_live(
        roots,
        course_id=args.course_id,
        run_id=run_id,
        token_env=args.token_env,
        max_sections=args.max_sections,
        max_units_per_section=args.max_units_per_section,
        max_steps_per_lesson=args.max_steps_per_lesson,
    )
    _emit(receipt)
    return 0


def cmd_build_index(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    path = build_keyword_index(roots, run_id=args.run)
    _emit({"schema": "aoa_course_build_index_receipt_v1", "status": "ok", "run_id": args.run, "index_path": str(path)})
    return 0


def cmd_build_graph(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    path = build_graph(roots, run_id=args.run)
    _emit({"schema": "aoa_course_build_graph_receipt_v1", "status": "ok", "run_id": args.run, "graph_path": str(path)})
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    _emit({"schema": "aoa_course_query_result_v1", "run_id": args.run, "query": args.query, "results": query_keyword_index(roots, args.query, args.run, args.limit)})
    return 0


def cmd_answer(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    packet = render_answer_packet(roots, args.query, args.run, args.limit)
    path = write_answer_packet(packet, roots, args.run)
    _emit({"status": "ok", "answer_path": str(path), **packet})
    return 0


def cmd_graph_neighbors(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    _emit(graph_neighbors(roots, args.node_id, args.run, args.limit))
    return 0


def cmd_evidence_inspect(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    packet = render_answer_packet(roots, args.query, args.run, 5)
    _emit({"schema": "aoa_course_evidence_inspect_v1", "run_id": args.run, "query": args.query, "evidence_chain": packet["evidence_chain"]})
    return 0


def cmd_eval_answer_packets(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    failures = []
    for query, terms in [
        ("bootloader unlock rollback", ["rollback", "bootloader"]),
        ("answer packet source evidence", ["evidence", "source"]),
    ]:
        packet = render_answer_packet(roots, query, DEFAULT_RUN, 5)
        text = json.dumps(packet).casefold()
        missing_terms = [term for term in terms if term not in text]
        if missing_terms or not packet.get("evidence_chain"):
            failures.append({"query": query, "missing_terms": missing_terms, "has_evidence": bool(packet.get("evidence_chain"))})
    _emit({"schema": "aoa_course_eval_answer_packets_v1", "status": "ok" if not failures else "error", "failures": failures})
    return 0 if not failures else 1


def cmd_eval_clean_api(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    failures = []
    packet = render_answer_packet(roots, "Stepik public API source evidence", "stepik-fixture", 5)
    text = json.dumps(packet).casefold()
    for term in ["stepik", "api", "evidence"]:
        if term not in text:
            failures.append({"missing_term": term})
    if not packet.get("evidence_chain"):
        failures.append({"missing": "evidence_chain"})
    _emit({"schema": "aoa_course_eval_clean_api_v1", "status": "ok" if not failures else "error", "failures": failures})
    return 0 if not failures else 1


def cmd_mcp_tools(_args: argparse.Namespace) -> int:
    _emit(tools_manifest())
    return 0


def cmd_mcp_call(args: argparse.Namespace) -> int:
    try:
        arguments = json.loads(args.arguments)
    except json.JSONDecodeError as exc:
        _emit({"schema": "aoa_course_mcp_call_v1", "status": "error", "error": f"invalid JSON arguments: {exc}"})
        return 2
    try:
        _emit({"schema": "aoa_course_mcp_call_v1", "status": "ok", "result": call_tool(args.tool, arguments)})
    except ValueError as exc:
        _emit({"schema": "aoa_course_mcp_call_v1", "status": "error", "error": str(exc)})
        return 2
    return 0


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
