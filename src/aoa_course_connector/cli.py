"""Command line interface for the AoA course connector."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aoa_course_connector.adapters import adapter_list
from aoa_course_connector.auth import browser_state_plan, capture_browser_state, default_browser_state_path, inspect_browser_state
from aoa_course_connector.calibration import build_live_calibration_packet, load_json_report, write_live_calibration_packet
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.discover import (
    discover_browser_fixture as discover_browser_fixture_route,
    discover_browser_live as discover_browser_live_route,
    discover_browser_snapshot as discover_browser_snapshot_route,
    discover_stepik_account_fixture as discover_stepik_account_fixture_route,
    discover_stepik_account_live as discover_stepik_account_live_route,
)
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index, build_semantic_index
from aoa_course_connector.ingest import (
    capture_browser_live,
    crawl_browser_fixture,
    crawl_browser_live,
    crawl_browser_snapshot,
    materialize_browser_fixture,
    materialize_browser_snapshot,
    materialize_fixture,
    materialize_stepik_fixture,
    materialize_stepik_live,
)
from aoa_course_connector.mcp.server import call_tool, tools_manifest
from aoa_course_connector.query import graph_neighbors, query_index, render_answer_packet, write_answer_packet
from aoa_course_connector.readiness import connected_source_plan, live_preflight
from aoa_course_connector.smoke import (
    smoke_browser_fixture as smoke_browser_fixture_route,
    smoke_browser_live as smoke_browser_live_route,
    smoke_browser_snapshot as smoke_browser_snapshot_route,
    smoke_stepik_fixture as smoke_stepik_fixture_route,
    smoke_stepik_live as smoke_stepik_live_route,
)
from aoa_course_connector.sources import load_registry, registry_path, upsert_source
from aoa_course_connector.storage import create_storage_roots, run_data_dir, storage_status
from aoa_course_connector.sync import (
    load_sync_status,
    sync_browser_fixture_sources,
    sync_browser_live_sources,
    sync_stepik_fixture_sources,
    sync_stepik_live_sources,
)


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

    preflight = sub.add_parser("preflight")
    preflight_sub = preflight.add_subparsers(dest="preflight_command", required=True)
    preflight_live = preflight_sub.add_parser("live")
    preflight_live.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"], action="append")
    preflight_live.add_argument("--stepik-token-env", default="STEPIK_API_TOKEN")
    preflight_live.add_argument("--state-file", type=Path)
    preflight_live.add_argument("--expect-origin")
    preflight_live.add_argument("--include-disabled", action="store_true")
    preflight_live.add_argument("--require-ready", action="store_true")
    preflight_live.set_defaults(func=cmd_preflight_live)
    preflight_plan = preflight_sub.add_parser("connected-plan")
    preflight_plan.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"], action="append")
    preflight_plan.add_argument("--stepik-token-env", default="STEPIK_API_TOKEN")
    preflight_plan.add_argument("--state-file", type=Path)
    preflight_plan.add_argument("--expect-origin")
    preflight_plan.add_argument("--include-disabled", action="store_true")
    preflight_plan.add_argument("--query")
    preflight_plan.add_argument("--max-lessons", type=int, default=50)
    preflight_plan.add_argument("--max-pages", type=int, default=5)
    preflight_plan.add_argument("--max-sources", type=int, default=50)
    preflight_plan.add_argument("--calibration-run", default="connected-live-calibration")
    preflight_plan.add_argument("--require-ready", action="store_true")
    preflight_plan.set_defaults(func=cmd_preflight_connected_plan)

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
    capture = auth_sub.add_parser("capture-browser-state")
    capture.add_argument("platform")
    capture.add_argument("source_ref")
    capture.add_argument("--login-url", required=True)
    capture.add_argument("--state-file", type=Path)
    capture.add_argument("--headless", action="store_true")
    capture.add_argument("--no-prompt", action="store_true")
    capture.add_argument("--wait-until", default="domcontentloaded")
    capture.add_argument("--timeout-ms", type=int, default=120_000)
    capture.set_defaults(func=cmd_auth_capture_browser_state)
    inspect_state = auth_sub.add_parser("inspect-browser-state")
    inspect_state.add_argument("state_file", nargs="?", type=Path)
    inspect_state.add_argument("--platform")
    inspect_state.add_argument("--source-ref")
    inspect_state.add_argument("--expect-origin-contains")
    inspect_state.set_defaults(func=cmd_auth_inspect_browser_state)

    discover = sub.add_parser("discover")
    discover_sub = discover.add_subparsers(dest="discover_command", required=True)
    discover_fixture = discover_sub.add_parser("fixture")
    discover_fixture.add_argument("--run", default=DEFAULT_RUN)
    discover_fixture.set_defaults(func=cmd_discover_fixture)
    discover_stepik = discover_sub.add_parser("stepik")
    discover_stepik.add_argument("course_id", type=int)
    discover_stepik.add_argument("--from-fixture", action="store_true")
    discover_stepik.add_argument("--register", action="store_true")
    discover_stepik.add_argument("--title")
    discover_stepik.add_argument("--access-mode", choices=["public_api", "api_token", "oauth"], default="public_api")
    discover_stepik.set_defaults(func=cmd_discover_stepik)
    discover_stepik_account = discover_sub.add_parser("stepik-account")
    discover_stepik_account.add_argument("--from-fixture", action="store_true")
    discover_stepik_account.add_argument("--fixture", type=Path)
    discover_stepik_account.add_argument("--register", action="store_true")
    discover_stepik_account.add_argument("--run", default="stepik-account-discovery")
    discover_stepik_account.add_argument("--token-env", default="STEPIK_API_TOKEN")
    discover_stepik_account.add_argument("--max-pages", type=int, default=5)
    discover_stepik_account.add_argument("--batch-size", type=int, default=20)
    discover_stepik_account.add_argument("--source-limit", type=int)
    discover_stepik_account.add_argument("--access-mode", choices=["api_token", "oauth"], default="api_token")
    discover_stepik_account.set_defaults(func=cmd_discover_stepik_account)
    discover_browser = discover_sub.add_parser("browser-fixture")
    discover_browser.add_argument("--platform", choices=["getcourse", "skillspace"], required=True)
    discover_browser.add_argument("--run")
    discover_browser.add_argument("--fixture", type=Path)
    discover_browser.add_argument("--max-sources", type=int, default=50)
    discover_browser.add_argument("--link-pattern")
    discover_browser.add_argument("--register", action="store_true")
    discover_browser.set_defaults(func=cmd_discover_browser_fixture)
    discover_browser_snapshot = discover_sub.add_parser("browser-snapshot")
    discover_browser_snapshot.add_argument("snapshot", type=Path)
    discover_browser_snapshot.add_argument("--platform", choices=["getcourse", "skillspace"])
    discover_browser_snapshot.add_argument("--run")
    discover_browser_snapshot.add_argument("--max-sources", type=int, default=50)
    discover_browser_snapshot.add_argument("--link-pattern")
    discover_browser_snapshot.add_argument("--register", action="store_true")
    discover_browser_snapshot.set_defaults(func=cmd_discover_browser_snapshot)
    discover_browser_live = discover_sub.add_parser("browser-live")
    discover_browser_live.add_argument("url")
    discover_browser_live.add_argument("--platform", choices=["getcourse", "skillspace"], required=True)
    discover_browser_live.add_argument("--run")
    discover_browser_live.add_argument("--state-file", type=Path)
    discover_browser_live.add_argument("--wait-until", default="networkidle")
    discover_browser_live.add_argument("--max-sources", type=int, default=50)
    discover_browser_live.add_argument("--max-pages", type=int, default=5)
    discover_browser_live.add_argument("--link-pattern")
    discover_browser_live.add_argument("--register", action="store_true")
    discover_browser_live.set_defaults(func=cmd_discover_browser_live)

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
    stepik_live.add_argument("--batch-size", type=int, default=20)
    stepik_live.add_argument("--include-step-sources", action="store_true")
    stepik_live.add_argument("--full-course", action="store_true")
    stepik_live.set_defaults(func=cmd_materialize_stepik_live)
    browser_fixture = materialize_sub.add_parser("browser-fixture")
    browser_fixture.add_argument("--platform", choices=["getcourse", "skillspace"], required=True)
    browser_fixture.add_argument("--run")
    browser_fixture.add_argument("--fixture", type=Path)
    browser_fixture.set_defaults(func=cmd_materialize_browser_fixture)
    browser_snapshot = materialize_sub.add_parser("browser-snapshot")
    browser_snapshot.add_argument("snapshot", type=Path)
    browser_snapshot.add_argument("--platform", choices=["getcourse", "skillspace"])
    browser_snapshot.add_argument("--run")
    browser_snapshot.set_defaults(func=cmd_materialize_browser_snapshot)
    browser_live = materialize_sub.add_parser("browser-live")
    browser_live.add_argument("url")
    browser_live.add_argument("--platform", choices=["getcourse", "skillspace"], required=True)
    browser_live.add_argument("--run")
    browser_live.add_argument("--state-file", type=Path)
    browser_live.add_argument("--wait-until", default="networkidle")
    browser_live.set_defaults(func=cmd_materialize_browser_live)

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
    ingest_browser_fixture = ingest_sub.add_parser("browser-fixture")
    ingest_browser_fixture.add_argument("--platform", choices=["getcourse", "skillspace"], required=True)
    ingest_browser_fixture.add_argument("--run")
    ingest_browser_fixture.add_argument("--fixture", type=Path)
    ingest_browser_fixture.set_defaults(func=cmd_materialize_browser_fixture)

    crawl = sub.add_parser("crawl")
    crawl_sub = crawl.add_subparsers(dest="crawl_command", required=True)
    crawl_fixture = crawl_sub.add_parser("browser-fixture")
    crawl_fixture.add_argument("--platform", choices=["getcourse", "skillspace"], required=True)
    crawl_fixture.add_argument("--run")
    crawl_fixture.add_argument("--fixture", type=Path)
    crawl_fixture.add_argument("--max-lessons", type=int, default=20)
    crawl_fixture.add_argument("--link-pattern")
    crawl_fixture.set_defaults(func=cmd_crawl_browser_fixture)
    crawl_snapshot = crawl_sub.add_parser("browser-snapshot")
    crawl_snapshot.add_argument("snapshot", type=Path)
    crawl_snapshot.add_argument("--platform", choices=["getcourse", "skillspace"])
    crawl_snapshot.add_argument("--run")
    crawl_snapshot.add_argument("--max-lessons", type=int, default=20)
    crawl_snapshot.add_argument("--link-pattern")
    crawl_snapshot.set_defaults(func=cmd_crawl_browser_snapshot)
    crawl_live = crawl_sub.add_parser("browser-live")
    crawl_live.add_argument("url")
    crawl_live.add_argument("--platform", choices=["getcourse", "skillspace"], required=True)
    crawl_live.add_argument("--run")
    crawl_live.add_argument("--state-file", type=Path)
    crawl_live.add_argument("--wait-until", default="networkidle")
    crawl_live.add_argument("--max-lessons", type=int, default=20)
    crawl_live.add_argument("--link-pattern")
    crawl_live.set_defaults(func=cmd_crawl_browser_live)

    sync = sub.add_parser("sync")
    sync_sub = sync.add_subparsers(dest="sync_command", required=True)
    sync_fixture = sync_sub.add_parser("browser-fixture")
    sync_fixture.add_argument("--run", default="browser-sync-fixture")
    sync_fixture.add_argument("--platform", choices=["getcourse", "skillspace"], action="append")
    sync_fixture.add_argument("--max-lessons", type=int, default=20)
    sync_fixture.add_argument("--link-pattern")
    sync_fixture.add_argument("--source-limit", type=int)
    sync_fixture.add_argument("--build-artifacts", action="store_true")
    sync_fixture.set_defaults(func=cmd_sync_browser_fixture)
    sync_live = sync_sub.add_parser("browser-live")
    sync_live.add_argument("--run", default="browser-live-sync")
    sync_live.add_argument("--platform", choices=["getcourse", "skillspace"], action="append")
    sync_live.add_argument("--state-file", type=Path)
    sync_live.add_argument("--wait-until", default="networkidle")
    sync_live.add_argument("--max-lessons", type=int, default=20)
    sync_live.add_argument("--link-pattern")
    sync_live.add_argument("--source-limit", type=int)
    sync_live.add_argument("--build-artifacts", action="store_true")
    sync_live.set_defaults(func=cmd_sync_browser_live)
    sync_stepik_fixture = sync_sub.add_parser("stepik-fixture")
    sync_stepik_fixture.add_argument("--run", default="stepik-sync-fixture")
    sync_stepik_fixture.add_argument("--source-limit", type=int)
    sync_stepik_fixture.add_argument("--build-artifacts", action="store_true")
    sync_stepik_fixture.set_defaults(func=cmd_sync_stepik_fixture)
    sync_stepik_live = sync_sub.add_parser("stepik-live")
    sync_stepik_live.add_argument("--run", default="stepik-live-sync")
    sync_stepik_live.add_argument("--token-env", default="STEPIK_API_TOKEN")
    sync_stepik_live.add_argument("--max-sections", type=int, default=1)
    sync_stepik_live.add_argument("--max-units-per-section", type=int, default=2)
    sync_stepik_live.add_argument("--max-steps-per-lesson", type=int, default=5)
    sync_stepik_live.add_argument("--batch-size", type=int, default=20)
    sync_stepik_live.add_argument("--include-step-sources", action="store_true")
    sync_stepik_live.add_argument("--full-course", action="store_true")
    sync_stepik_live.add_argument("--source-limit", type=int)
    sync_stepik_live.add_argument("--build-artifacts", action="store_true")
    sync_stepik_live.set_defaults(func=cmd_sync_stepik_live)
    sync_status = sync_sub.add_parser("status")
    sync_status.add_argument("--run")
    sync_status.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"])
    sync_status.set_defaults(func=cmd_sync_status)

    smoke = sub.add_parser("smoke")
    smoke_sub = smoke.add_subparsers(dest="smoke_command", required=True)
    smoke_fixture = smoke_sub.add_parser("browser-fixture")
    smoke_fixture.add_argument("--platform", choices=["getcourse", "skillspace"], required=True)
    smoke_fixture.add_argument("--run")
    smoke_fixture.add_argument("--query")
    smoke_fixture.add_argument("--register", action="store_true")
    smoke_fixture.add_argument("--skip-artifacts", action="store_true")
    smoke_fixture.set_defaults(func=cmd_smoke_browser_fixture)
    smoke_snapshot = smoke_sub.add_parser("browser-snapshot")
    smoke_snapshot.add_argument("--platform", choices=["getcourse", "skillspace"], required=True)
    smoke_snapshot.add_argument("--run")
    smoke_snapshot.add_argument("--catalog-snapshot", type=Path)
    smoke_snapshot.add_argument("--course-snapshot", type=Path)
    smoke_snapshot.add_argument("--query")
    smoke_snapshot.add_argument("--register", action="store_true")
    smoke_snapshot.add_argument("--skip-artifacts", action="store_true")
    smoke_snapshot.set_defaults(func=cmd_smoke_browser_snapshot)
    smoke_live = smoke_sub.add_parser("browser-live")
    smoke_live.add_argument("--platform", choices=["getcourse", "skillspace"], required=True)
    smoke_live.add_argument("--run")
    smoke_live.add_argument("--catalog-url")
    smoke_live.add_argument("--course-url")
    smoke_live.add_argument("--state-file", type=Path)
    smoke_live.add_argument("--wait-until", default="networkidle")
    smoke_live.add_argument("--max-sources", type=int, default=50)
    smoke_live.add_argument("--max-pages", type=int, default=5)
    smoke_live.add_argument("--max-lessons", type=int, default=20)
    smoke_live.add_argument("--link-pattern")
    smoke_live.add_argument("--query")
    smoke_live.add_argument("--register", action="store_true")
    smoke_live.add_argument("--skip-artifacts", action="store_true")
    smoke_live.set_defaults(func=cmd_smoke_browser_live)
    smoke_stepik_fixture = smoke_sub.add_parser("stepik-fixture")
    smoke_stepik_fixture.add_argument("course_id", type=int)
    smoke_stepik_fixture.add_argument("--run")
    smoke_stepik_fixture.add_argument("--title")
    smoke_stepik_fixture.add_argument("--query")
    smoke_stepik_fixture.add_argument("--skip-artifacts", action="store_true")
    smoke_stepik_fixture.set_defaults(func=cmd_smoke_stepik_fixture)
    smoke_stepik_live = smoke_sub.add_parser("stepik-live")
    smoke_stepik_live.add_argument("course_id", type=int)
    smoke_stepik_live.add_argument("--run")
    smoke_stepik_live.add_argument("--title")
    smoke_stepik_live.add_argument("--access-mode", choices=["public_api", "api_token", "oauth"], default="public_api")
    smoke_stepik_live.add_argument("--token-env", default="STEPIK_API_TOKEN")
    smoke_stepik_live.add_argument("--max-sections", type=int, default=1)
    smoke_stepik_live.add_argument("--max-units-per-section", type=int, default=2)
    smoke_stepik_live.add_argument("--max-steps-per-lesson", type=int, default=5)
    smoke_stepik_live.add_argument("--batch-size", type=int, default=20)
    smoke_stepik_live.add_argument("--include-step-sources", action="store_true")
    smoke_stepik_live.add_argument("--full-course", action="store_true")
    smoke_stepik_live.add_argument("--query")
    smoke_stepik_live.add_argument("--skip-artifacts", action="store_true")
    smoke_stepik_live.set_defaults(func=cmd_smoke_stepik_live)

    calibration = sub.add_parser("calibration")
    calibration_sub = calibration.add_subparsers(dest="calibration_command", required=True)
    calibration_build = calibration_sub.add_parser("build")
    calibration_build.add_argument("--run", default="live-calibration")
    calibration_build.add_argument("--report", action="append", type=Path, required=True)
    calibration_build.add_argument("--preflight-report", action="append", type=Path)
    calibration_build.set_defaults(func=cmd_calibration_build)

    build_index = sub.add_parser("build-index")
    build_index.add_argument("--run", default=DEFAULT_RUN)
    build_index.set_defaults(func=cmd_build_index)

    build_semantic = sub.add_parser("build-semantic-index")
    build_semantic.add_argument("--run", default=DEFAULT_RUN)
    build_semantic.add_argument("--dimensions", type=int, default=256)
    build_semantic.set_defaults(func=cmd_build_semantic_index)

    build_graph_parser = sub.add_parser("build-graph")
    build_graph_parser.add_argument("--run", default=DEFAULT_RUN)
    build_graph_parser.set_defaults(func=cmd_build_graph)

    query = sub.add_parser("query")
    query.add_argument("query")
    query.add_argument("--run", default=DEFAULT_RUN)
    query.add_argument("--limit", type=int, default=5)
    query.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="keyword")
    query.set_defaults(func=cmd_query)

    answer = sub.add_parser("answer")
    answer.add_argument("query")
    answer.add_argument("--run", default=DEFAULT_RUN)
    answer.add_argument("--limit", type=int, default=5)
    answer.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="keyword")
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
    inspect.add_argument("--limit", type=int, default=5)
    inspect.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="keyword")
    inspect.set_defaults(func=cmd_evidence_inspect)

    eval_parser = sub.add_parser("eval")
    eval_sub = eval_parser.add_subparsers(dest="eval_command", required=True)
    eval_sub.add_parser("answer-packets").set_defaults(func=cmd_eval_answer_packets)
    eval_sub.add_parser("answer-quality").set_defaults(func=cmd_eval_answer_quality)
    eval_sub.add_parser("freshness-ranking").set_defaults(func=cmd_eval_freshness_ranking)
    eval_sub.add_parser("authority-ranking").set_defaults(func=cmd_eval_authority_ranking)
    eval_sub.add_parser("adapter-authority").set_defaults(func=cmd_eval_adapter_authority)
    eval_sub.add_parser("live-calibration").set_defaults(func=cmd_eval_live_calibration)
    eval_sub.add_parser("clean-api").set_defaults(func=cmd_eval_clean_api)
    eval_sub.add_parser("browser-hard-adapters").set_defaults(func=cmd_eval_browser_hard_adapters)
    eval_sub.add_parser("browser-crawl").set_defaults(func=cmd_eval_browser_crawl)
    eval_sub.add_parser("browser-progress-comments").set_defaults(func=cmd_eval_browser_progress_comments)
    eval_sub.add_parser("browser-transcripts").set_defaults(func=cmd_eval_browser_transcripts)
    eval_sub.add_parser("browser-discovery").set_defaults(func=cmd_eval_browser_discovery)
    eval_sub.add_parser("browser-sync").set_defaults(func=cmd_eval_browser_sync)
    eval_sub.add_parser("stepik-sync").set_defaults(func=cmd_eval_stepik_sync)
    eval_sub.add_parser("semantic-index").set_defaults(func=cmd_eval_semantic_index)

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


def cmd_preflight_live(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    report = live_preflight(
        roots,
        platforms=args.platform,
        stepik_token_env=args.stepik_token_env,
        browser_state_file=args.state_file,
        expect_origin_contains=args.expect_origin,
        include_disabled=args.include_disabled,
    )
    _emit(report)
    return 0 if bool(report.get("ready")) or not args.require_ready else 1


def cmd_preflight_connected_plan(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    plan = connected_source_plan(
        roots,
        platforms=args.platform,
        stepik_token_env=args.stepik_token_env,
        browser_state_file=args.state_file,
        expect_origin_contains=args.expect_origin,
        include_disabled=args.include_disabled,
        query=args.query,
        max_lessons=args.max_lessons,
        max_pages=args.max_pages,
        max_sources=args.max_sources,
        calibration_run=args.calibration_run,
    )
    _emit(plan)
    return 0 if bool(plan.get("ready")) or not args.require_ready else 1


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


def cmd_auth_capture_browser_state(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    create_storage_roots(roots)
    pause = None if args.no_prompt else _prompt_for_browser_login
    try:
        receipt = capture_browser_state(
            roots.auth,
            args.platform,
            args.source_ref,
            args.login_url,
            state_file=args.state_file,
            headless=args.headless,
            wait_until=args.wait_until,
            timeout_ms=args.timeout_ms,
            pause=pause,
        )
    except Exception as exc:
        state_file = args.state_file or default_browser_state_path(roots.auth, args.platform, args.source_ref)
        network_touched = "Install the browser extra first" not in str(exc)
        _emit({
            "schema": "aoa_course_browser_state_capture_receipt_v1",
            "status": "error",
            "platform": args.platform,
            "source_ref": args.source_ref,
            "state_file": str(state_file),
            "error": str(exc),
            "network_touched": network_touched,
        })
        return 2
    _emit(receipt)
    return 0 if receipt.get("status") in {"ok", "warning"} else 1


def cmd_auth_inspect_browser_state(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    if args.state_file:
        state_file = args.state_file
    elif args.platform and args.source_ref:
        state_file = default_browser_state_path(roots.auth, args.platform, args.source_ref)
    else:
        _emit({
            "schema": "aoa_course_browser_state_status_v1",
            "status": "error",
            "error": "provide state_file or both --platform and --source-ref",
            "usable": False,
        })
        return 2
    status = inspect_browser_state(state_file, expect_origin_contains=args.expect_origin_contains)
    _emit(status)
    return 0 if status.get("usable") else 1


def _prompt_for_browser_login(page_info: dict[str, object]) -> None:
    print(
        "Log in with your authorized account in the opened browser window, "
        "then press Enter here to save Playwright storage state.",
        file=sys.stderr,
    )
    print(f"Opened: {page_info.get('url')}", file=sys.stderr)
    print(f"State file: {page_info.get('state_file')}", file=sys.stderr)
    input()


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
    roots = StorageRoots.from_env(repo_root)
    registered: dict[str, object] | None = None
    if args.from_fixture:
        fixture_path = repo_root / "connector/fixtures/stepik/starter_stepik_course.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        course = fixture.get("course", {})
        sections = fixture.get("sections", [])
        course_title = (
            args.title
            or (course.get("title") if isinstance(course, dict) else None)
            or f"Stepik course {args.course_id}"
        )
        if args.register:
            create_storage_roots(roots)
            source, path, state = upsert_source(
                roots.data,
                platform="stepik",
                source_ref=str(args.course_id),
                title=course_title,
                access_mode=args.access_mode,
            )
            registered = {"state": state, "registry_path": str(path), "source": source}
        _emit(
            {
                "schema": "aoa_course_stepik_discovery_receipt_v1",
                "status": "ok",
                "source_mode": "stepik_fixture",
                "course_id": args.course_id,
                "course_title": course_title,
                "section_count": len(sections) if isinstance(sections, list) else 0,
                "fixture": str(fixture_path),
                "registered": registered,
                "network_touched": False,
            }
        )
        return 0
    if args.register:
        create_storage_roots(roots)
        source, path, state = upsert_source(
            roots.data,
            platform="stepik",
            source_ref=str(args.course_id),
            title=args.title or f"Stepik course {args.course_id}",
            access_mode=args.access_mode,
        )
        registered = {"state": state, "registry_path": str(path), "source": source}
    _emit(
        {
            "schema": "aoa_course_stepik_discovery_receipt_v1",
            "status": "planned",
            "source_mode": "stepik_live",
            "course_id": args.course_id,
            "next_command": f"aoa-course materialize stepik-live {args.course_id} --run stepik-course-{args.course_id}",
            "sync_command": "aoa-course sync stepik-live --run stepik-live-sync",
            "registered": registered,
            "network_touched": False,
        }
    )
    return 0


def cmd_discover_stepik_account(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    try:
        if args.from_fixture:
            receipt = discover_stepik_account_fixture_route(
                roots,
                run_id=args.run,
                fixture=args.fixture,
                register=args.register,
                access_mode=args.access_mode,
                source_limit=args.source_limit,
            )
        else:
            receipt = discover_stepik_account_live_route(
                roots,
                run_id=args.run,
                token_env=args.token_env,
                max_pages=args.max_pages,
                batch_size=args.batch_size,
                register=args.register,
                access_mode=args.access_mode,
                source_limit=args.source_limit,
            )
    except Exception as exc:
        _emit({
            "schema": "aoa_course_stepik_account_discovery_receipt_v1",
            "status": "error",
            "run_id": args.run,
            "source_mode": "stepik_account_fixture" if args.from_fixture else "stepik_account_live",
            "error": str(exc),
            "network_touched": False if args.from_fixture or str(exc).startswith("Stepik account discovery requires token env") else True,
        })
        return 2
    _emit(receipt)
    return 0 if receipt.get("status") == "ok" else 1


def cmd_discover_browser_fixture(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = discover_browser_fixture_route(
        roots,
        platform=args.platform,
        run_id=args.run,
        fixture=args.fixture,
        max_sources=args.max_sources,
        link_pattern=args.link_pattern,
        register=args.register,
    )
    _emit(receipt)
    return 0


def cmd_discover_browser_snapshot(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = discover_browser_snapshot_route(
        roots,
        snapshot_path=args.snapshot,
        platform=args.platform,
        run_id=args.run,
        max_sources=args.max_sources,
        link_pattern=args.link_pattern,
        register=args.register,
    )
    _emit(receipt)
    return 0


def cmd_discover_browser_live(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    run_id = args.run or f"{args.platform}-browser-live-discovery"
    try:
        receipt = discover_browser_live_route(
            roots,
            url=args.url,
            platform=args.platform,
            run_id=run_id,
            state_file=args.state_file,
            wait_until=args.wait_until,
            max_sources=args.max_sources,
            max_pages=args.max_pages,
            link_pattern=args.link_pattern,
            register=args.register,
        )
    except RuntimeError as exc:
        _emit({"schema": "aoa_course_browser_discovery_receipt_v1", "status": "error", "error": str(exc), "network_touched": False})
        return 2
    _emit(receipt)
    return 0


def cmd_materialize_fixture(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = materialize_fixture(roots, run_id=args.run, fixture=args.fixture)
    _emit(receipt)
    return 0


def cmd_materialize_browser_fixture(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = materialize_browser_fixture(roots, platform=args.platform, run_id=args.run, fixture=args.fixture)
    _emit(receipt)
    return 0


def cmd_materialize_browser_snapshot(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = materialize_browser_snapshot(roots, snapshot_path=args.snapshot, platform=args.platform, run_id=args.run)
    _emit(receipt)
    return 0


def cmd_materialize_browser_live(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    run_id = args.run or f"{args.platform}-browser-live"
    try:
        receipt = capture_browser_live(roots, url=args.url, platform=args.platform, run_id=run_id, state_file=args.state_file, wait_until=args.wait_until)
    except RuntimeError as exc:
        _emit({"schema": "aoa_course_browser_live_receipt_v1", "status": "error", "error": str(exc), "network_touched": False})
        return 2
    _emit(receipt)
    return 0


def cmd_crawl_browser_fixture(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = crawl_browser_fixture(
        roots,
        platform=args.platform,
        run_id=args.run,
        fixture=args.fixture,
        max_lessons=args.max_lessons,
        link_pattern=args.link_pattern,
    )
    _emit(receipt)
    return 0


def cmd_crawl_browser_snapshot(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = crawl_browser_snapshot(
        roots,
        snapshot_path=args.snapshot,
        platform=args.platform,
        run_id=args.run,
        max_lessons=args.max_lessons,
        link_pattern=args.link_pattern,
    )
    _emit(receipt)
    return 0


def cmd_crawl_browser_live(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    run_id = args.run or f"{args.platform}-browser-live-crawl"
    try:
        receipt = crawl_browser_live(
            roots,
            url=args.url,
            platform=args.platform,
            run_id=run_id,
            state_file=args.state_file,
            wait_until=args.wait_until,
            max_lessons=args.max_lessons,
            link_pattern=args.link_pattern,
        )
    except RuntimeError as exc:
        _emit({"schema": "aoa_course_browser_crawl_receipt_v1", "status": "error", "error": str(exc), "network_touched": False})
        return 2
    _emit(receipt)
    return 0


def cmd_sync_browser_fixture(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = sync_browser_fixture_sources(
        roots,
        sync_run_id=args.run,
        platforms=args.platform,
        max_lessons=args.max_lessons,
        link_pattern=args.link_pattern,
        source_limit=args.source_limit,
        build_artifacts=args.build_artifacts,
    )
    _emit(receipt)
    return 0 if receipt.get("status") in {"ok", "partial"} else 1


def cmd_sync_browser_live(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = sync_browser_live_sources(
        roots,
        sync_run_id=args.run,
        platforms=args.platform,
        state_file=args.state_file,
        wait_until=args.wait_until,
        max_lessons=args.max_lessons,
        link_pattern=args.link_pattern,
        source_limit=args.source_limit,
        build_artifacts=args.build_artifacts,
    )
    _emit(receipt)
    return 0 if receipt.get("status") in {"ok", "partial"} else 1


def cmd_sync_stepik_fixture(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = sync_stepik_fixture_sources(
        roots,
        sync_run_id=args.run,
        source_limit=args.source_limit,
        build_artifacts=args.build_artifacts,
    )
    _emit(receipt)
    return 0 if receipt.get("status") in {"ok", "partial"} else 1


def cmd_sync_stepik_live(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    max_sections = None if args.full_course else args.max_sections
    max_units = None if args.full_course else args.max_units_per_section
    max_steps = None if args.full_course else args.max_steps_per_lesson
    receipt = sync_stepik_live_sources(
        roots,
        sync_run_id=args.run,
        token_env=args.token_env,
        max_sections=max_sections,
        max_units_per_section=max_units,
        max_steps_per_lesson=max_steps,
        batch_size=args.batch_size,
        include_step_sources=args.include_step_sources,
        source_limit=args.source_limit,
        build_artifacts=args.build_artifacts,
    )
    _emit(receipt)
    return 0 if receipt.get("status") in {"ok", "partial"} else 1


def cmd_sync_status(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    _emit(load_sync_status(roots, sync_run_id=args.run, platform=args.platform))
    return 0


def cmd_smoke_browser_fixture(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    report = smoke_browser_fixture_route(
        roots,
        platform=args.platform,
        run_id=args.run or f"{args.platform}-browser-smoke-fixture",
        query=args.query,
        register=args.register,
        build_artifacts=not args.skip_artifacts,
    )
    _emit(report)
    return 0 if report.get("status") == "ok" else 1


def cmd_smoke_browser_snapshot(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    try:
        report = smoke_browser_snapshot_route(
            roots,
            platform=args.platform,
            run_id=args.run or f"{args.platform}-browser-smoke-snapshot",
            catalog_snapshot=args.catalog_snapshot,
            course_snapshot=args.course_snapshot,
            query=args.query,
            register=args.register,
            build_artifacts=not args.skip_artifacts,
        )
    except ValueError as exc:
        _emit({"schema": "aoa_course_browser_smoke_report_v1", "status": "error", "error": str(exc), "network_touched": False})
        return 2
    _emit(report)
    return 0 if report.get("status") == "ok" else 1


def cmd_smoke_browser_live(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    try:
        report = smoke_browser_live_route(
            roots,
            platform=args.platform,
            run_id=args.run or f"{args.platform}-browser-smoke-live",
            catalog_url=args.catalog_url,
            course_url=args.course_url,
            state_file=args.state_file,
            wait_until=args.wait_until,
            max_sources=args.max_sources,
            max_pages=args.max_pages,
            max_lessons=args.max_lessons,
            link_pattern=args.link_pattern,
            query=args.query,
            register=args.register,
            build_artifacts=not args.skip_artifacts,
        )
    except (RuntimeError, ValueError) as exc:
        _emit({"schema": "aoa_course_browser_smoke_report_v1", "status": "error", "error": str(exc), "network_touched": False})
        return 2
    _emit(report)
    return 0 if report.get("status") == "ok" else 1


def cmd_smoke_stepik_fixture(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    report = smoke_stepik_fixture_route(
        roots,
        course_id=args.course_id,
        run_id=args.run or f"stepik-{args.course_id}-smoke-fixture",
        title=args.title,
        query=args.query,
        build_artifacts=not args.skip_artifacts,
    )
    _emit(report)
    return 0 if report.get("status") == "ok" else 1


def cmd_smoke_stepik_live(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    max_sections = None if args.full_course else args.max_sections
    max_units = None if args.full_course else args.max_units_per_section
    max_steps = None if args.full_course else args.max_steps_per_lesson
    report = smoke_stepik_live_route(
        roots,
        course_id=args.course_id,
        run_id=args.run or f"stepik-{args.course_id}-smoke-live",
        title=args.title,
        access_mode=args.access_mode,
        token_env=args.token_env,
        max_sections=max_sections,
        max_units_per_section=max_units,
        max_steps_per_lesson=max_steps,
        batch_size=args.batch_size,
        include_step_sources=args.include_step_sources,
        query=args.query,
        build_artifacts=not args.skip_artifacts,
    )
    _emit(report)
    return 0 if report.get("status") == "ok" else 1


def cmd_calibration_build(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    smoke_reports = [load_json_report(path) for path in args.report]
    preflight_reports = [load_json_report(path) for path in args.preflight_report or []]
    packet = build_live_calibration_packet(run_id=args.run, smoke_reports=smoke_reports, preflight_reports=preflight_reports)
    packet_path = write_live_calibration_packet(roots, packet, run_id=args.run)
    _emit({**packet, "packet_path": str(packet_path)})
    return 0 if packet.get("status") == "ok" else 1


def cmd_materialize_stepik_fixture(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    receipt = materialize_stepik_fixture(roots, run_id=args.run, fixture=args.fixture)
    _emit(receipt)
    return 0


def cmd_materialize_stepik_live(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    run_id = args.run or f"stepik-course-{args.course_id}"
    max_sections = None if args.full_course else args.max_sections
    max_units = None if args.full_course else args.max_units_per_section
    max_steps = None if args.full_course else args.max_steps_per_lesson
    receipt = materialize_stepik_live(
        roots,
        course_id=args.course_id,
        run_id=run_id,
        token_env=args.token_env,
        max_sections=max_sections,
        max_units_per_section=max_units,
        max_steps_per_lesson=max_steps,
        batch_size=args.batch_size,
        include_step_sources=args.include_step_sources,
    )
    _emit(receipt)
    return 0


def cmd_build_index(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    path = build_keyword_index(roots, run_id=args.run)
    _emit({"schema": "aoa_course_build_index_receipt_v1", "status": "ok", "run_id": args.run, "index_path": str(path)})
    return 0


def cmd_build_semantic_index(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    path = build_semantic_index(roots, run_id=args.run, dimensions=args.dimensions)
    _emit({"schema": "aoa_course_build_semantic_index_receipt_v1", "status": "ok", "run_id": args.run, "semantic_index_path": str(path)})
    return 0


def cmd_build_graph(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    path = build_graph(roots, run_id=args.run)
    _emit({"schema": "aoa_course_build_graph_receipt_v1", "status": "ok", "run_id": args.run, "graph_path": str(path)})
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    _emit(
        {
            "schema": "aoa_course_query_result_v1",
            "run_id": args.run,
            "query": args.query,
            "mode": args.mode,
            "results": query_index(roots, args.query, args.run, args.limit, args.mode),
        }
    )
    return 0


def cmd_answer(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    packet = render_answer_packet(roots, args.query, args.run, args.limit, args.mode)
    path = write_answer_packet(packet, roots, args.run)
    _emit({"status": "ok", "answer_path": str(path), **packet})
    return 0


def cmd_graph_neighbors(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    _emit(graph_neighbors(roots, args.node_id, args.run, args.limit))
    return 0


def cmd_evidence_inspect(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    packet = render_answer_packet(roots, args.query, args.run, args.limit, args.mode)
    _emit(
        {
            "schema": "aoa_course_evidence_inspect_v1",
            "run_id": args.run,
            "query": args.query,
            "mode": args.mode,
            "result_count": packet["result_count"],
            "evidence_chain": packet["evidence_chain"],
            "freshness_report": packet["freshness_report"],
            "authority_report": packet["authority_report"],
        }
    )
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


def cmd_eval_answer_quality(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    suite_path = find_repo_root() / "evals" / "suites" / "answer_quality_packets.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    failures = []
    case_results = []
    for case in suite.get("cases", []):
        if not isinstance(case, dict):
            continue
        packet = render_answer_packet(
            roots,
            str(case.get("query") or ""),
            str(case.get("run") or DEFAULT_RUN),
            int(case.get("limit") or 5),
            str(case.get("mode") or "keyword"),
        )
        case_failures = _answer_quality_failures(packet, case)
        case_results.append(
            {
                "query": case.get("query"),
                "run": case.get("run") or DEFAULT_RUN,
                "mode": case.get("mode") or "keyword",
                "result_count": packet.get("result_count"),
                "top_doc_id": packet.get("results", [{}])[0].get("doc_id") if packet.get("results") else "",
                "failure_count": len(case_failures),
            }
        )
        failures.extend(case_failures)
    _emit(
        {
            "schema": "aoa_course_eval_answer_quality_v1",
            "suite_id": suite.get("suite_id"),
            "status": "ok" if not failures else "error",
            "case_results": case_results,
            "failures": failures,
        }
    )
    return 0 if not failures else 1


def _answer_quality_failures(packet: dict[str, object], case: dict[str, object]) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    context = {"run": case.get("run") or DEFAULT_RUN, "query": case.get("query"), "mode": case.get("mode") or "keyword"}
    results = [item for item in packet.get("results", []) if isinstance(item, dict)] if isinstance(packet.get("results"), list) else []
    evidence_chain = [item for item in packet.get("evidence_chain", []) if isinstance(item, dict)] if isinstance(packet.get("evidence_chain"), list) else []
    min_results = int(case.get("min_results") or 1)
    if len(results) < min_results:
        failures.append({**context, "missing": "minimum results", "expected": min_results, "actual": len(results)})
        return failures
    top = results[0]
    for key, field in [
        ("expected_top_kind", "kind"),
        ("expected_top_platform", "platform"),
        ("expected_top_source_id", "source_id"),
    ]:
        expected = case.get(key)
        if expected is not None and str(top.get(field) or "") != str(expected):
            failures.append({**context, "field": field, "expected": expected, "actual": top.get(field)})
    for term in _list_of_strings(case.get("expected_top_path_terms")):
        if term.casefold() not in " / ".join(str(item) for item in top.get("path", []) if item).casefold():
            failures.append({**context, "missing_top_path_term": term, "top_path": top.get("path")})
    for term in _list_of_strings(case.get("expected_top_snippet_terms")):
        if term.casefold() not in str(top.get("snippet") or "").casefold():
            failures.append({**context, "missing_top_snippet_term": term, "top_doc_id": top.get("doc_id")})
    required_kind = case.get("must_include_kind")
    if required_kind and not any(result.get("kind") == required_kind for result in results):
        failures.append({**context, "missing_result_kind": required_kind})
    freshness_report = packet.get("freshness_report") if isinstance(packet.get("freshness_report"), dict) else {}
    freshness_states = {str(item) for item in freshness_report.get("states", [])} if isinstance(freshness_report.get("states"), list) else set()
    for state in _list_of_strings(case.get("expected_freshness_states")):
        if state not in freshness_states:
            failures.append({**context, "missing_freshness_state": state, "actual_states": sorted(freshness_states)})
    if not freshness_report.get("has_source_timestamps"):
        failures.append({**context, "missing": "source timestamps"})
    required_fields = _list_of_strings(case.get("required_evidence_fields"))
    if not evidence_chain:
        failures.append({**context, "missing": "evidence_chain"})
    for index, evidence in enumerate(evidence_chain):
        for field in required_fields:
            if not evidence.get(field):
                failures.append({**context, "evidence_index": index, "missing_evidence_field": field})
    return failures


def cmd_eval_freshness_ranking(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    suite_path = find_repo_root() / "evals" / "suites" / "freshness_ranking.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    failures = []
    case_results = []
    for case in suite.get("cases", []):
        if not isinstance(case, dict):
            continue
        packet = render_answer_packet(
            roots,
            str(case.get("query") or ""),
            str(case.get("run") or DEFAULT_RUN),
            int(case.get("limit") or 5),
            str(case.get("mode") or "keyword"),
        )
        case_failures = _freshness_ranking_failures(packet, case)
        results = [item for item in packet.get("results", []) if isinstance(item, dict)] if isinstance(packet.get("results"), list) else []
        case_results.append(
            {
                "query": case.get("query"),
                "run": case.get("run") or DEFAULT_RUN,
                "mode": case.get("mode") or "keyword",
                "result_count": packet.get("result_count"),
                "top_doc_id": results[0].get("doc_id") if results else "",
                "top_rank_score": results[0].get("rank_score") if results else None,
                "failure_count": len(case_failures),
            }
        )
        failures.extend(case_failures)
    _emit(
        {
            "schema": "aoa_course_eval_freshness_ranking_v1",
            "suite_id": suite.get("suite_id"),
            "status": "ok" if not failures else "error",
            "case_results": case_results,
            "failures": failures,
        }
    )
    return 0 if not failures else 1


def _freshness_ranking_failures(packet: dict[str, object], case: dict[str, object]) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    context = {"run": case.get("run") or DEFAULT_RUN, "query": case.get("query"), "mode": case.get("mode") or "keyword"}
    results = [item for item in packet.get("results", []) if isinstance(item, dict)] if isinstance(packet.get("results"), list) else []
    min_results = int(case.get("min_results") or 1)
    if len(results) < min_results:
        return [{**context, "missing": "minimum results", "expected": min_results, "actual": len(results)}]
    by_doc = {str(result.get("doc_id")): result for result in results}
    top = results[0]
    expected_top_doc_id = case.get("expected_top_doc_id")
    if expected_top_doc_id is not None and str(top.get("doc_id") or "") != str(expected_top_doc_id):
        failures.append({**context, "field": "top_doc_id", "expected": expected_top_doc_id, "actual": top.get("doc_id")})
    expected_top_freshness = case.get("expected_top_freshness_state")
    if expected_top_freshness is not None and str(top.get("freshness_state") or "") != str(expected_top_freshness):
        failures.append(
            {
                **context,
                "field": "top_freshness_state",
                "expected": expected_top_freshness,
                "actual": top.get("freshness_state"),
            }
        )
    current = by_doc.get(str(case.get("current_doc_id") or ""))
    stale = by_doc.get(str(case.get("stale_doc_id") or ""))
    if case.get("expect_current_ranked_above_stale"):
        if not current or not stale:
            failures.append({**context, "missing": "current/stale comparison docs", "available_doc_ids": list(by_doc)})
        else:
            current_index = results.index(current)
            stale_index = results.index(stale)
            if current_index >= stale_index:
                failures.append({**context, "expected_order": "current before stale", "actual_order": [item.get("doc_id") for item in results]})
            if float(current.get("rank_score") or 0.0) <= float(stale.get("rank_score") or 0.0):
                failures.append(
                    {
                        **context,
                        "expected": "current rank_score above stale",
                        "current_rank_score": current.get("rank_score"),
                        "stale_rank_score": stale.get("rank_score"),
                    }
                )
    if case.get("expect_equal_relevance_score") and current and stale and float(current.get("score") or 0.0) != float(stale.get("score") or 0.0):
        failures.append({**context, "expected": "equal base relevance score", "current_score": current.get("score"), "stale_score": stale.get("score")})
    required_fields = _list_of_strings(case.get("required_evidence_fields"))
    evidence_chain = [item for item in packet.get("evidence_chain", []) if isinstance(item, dict)] if isinstance(packet.get("evidence_chain"), list) else []
    if not evidence_chain:
        failures.append({**context, "missing": "evidence_chain"})
    for index, evidence in enumerate(evidence_chain):
        for field in required_fields:
            if not evidence.get(field):
                failures.append({**context, "evidence_index": index, "missing_evidence_field": field})
    return failures


def cmd_eval_authority_ranking(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    suite_path = find_repo_root() / "evals" / "suites" / "authority_ranking.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    failures = []
    case_results = []
    for case in suite.get("cases", []):
        if not isinstance(case, dict):
            continue
        packet = render_answer_packet(
            roots,
            str(case.get("query") or ""),
            str(case.get("run") or DEFAULT_RUN),
            int(case.get("limit") or 5),
            str(case.get("mode") or "keyword"),
        )
        case_failures = _authority_ranking_failures(packet, case)
        results = [item for item in packet.get("results", []) if isinstance(item, dict)] if isinstance(packet.get("results"), list) else []
        top = results[0] if results else {}
        case_results.append(
            {
                "query": case.get("query"),
                "run": case.get("run") or DEFAULT_RUN,
                "mode": case.get("mode") or "keyword",
                "result_count": packet.get("result_count"),
                "top_doc_id": top.get("doc_id"),
                "top_authority_tier": top.get("authority_tier"),
                "top_rank_score": top.get("rank_score"),
                "failure_count": len(case_failures),
            }
        )
        failures.extend(case_failures)
    _emit(
        {
            "schema": "aoa_course_eval_authority_ranking_v1",
            "suite_id": suite.get("suite_id"),
            "status": "ok" if not failures else "error",
            "case_results": case_results,
            "failures": failures,
        }
    )
    return 0 if not failures else 1


def _authority_ranking_failures(packet: dict[str, object], case: dict[str, object]) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    context = {"run": case.get("run") or DEFAULT_RUN, "query": case.get("query"), "mode": case.get("mode") or "keyword"}
    results = [item for item in packet.get("results", []) if isinstance(item, dict)] if isinstance(packet.get("results"), list) else []
    min_results = int(case.get("min_results") or 1)
    if len(results) < min_results:
        return [{**context, "missing": "minimum results", "expected": min_results, "actual": len(results)}]
    by_doc = {str(result.get("doc_id")): result for result in results}
    top = results[0]
    expected_top_doc_id = case.get("expected_top_doc_id")
    if expected_top_doc_id is not None and str(top.get("doc_id") or "") != str(expected_top_doc_id):
        failures.append({**context, "field": "top_doc_id", "expected": expected_top_doc_id, "actual": top.get("doc_id")})
    expected_top_tier = case.get("expected_top_authority_tier")
    if expected_top_tier is not None and str(top.get("authority_tier") or "") != str(expected_top_tier):
        failures.append({**context, "field": "top_authority_tier", "expected": expected_top_tier, "actual": top.get("authority_tier")})

    preferred = by_doc.get(str(case.get("preferred_doc_id") or ""))
    lower = by_doc.get(str(case.get("lower_authority_doc_id") or ""))
    if case.get("expect_preferred_ranked_above_lower"):
        if not preferred or not lower:
            failures.append({**context, "missing": "preferred/lower-authority comparison docs", "available_doc_ids": list(by_doc)})
        else:
            preferred_index = results.index(preferred)
            lower_index = results.index(lower)
            if preferred_index >= lower_index:
                failures.append({**context, "expected_order": "preferred before lower authority", "actual_order": [item.get("doc_id") for item in results]})
            if float(preferred.get("rank_score") or 0.0) <= float(lower.get("rank_score") or 0.0):
                failures.append(
                    {
                        **context,
                        "expected": "preferred rank_score above lower authority",
                        "preferred_rank_score": preferred.get("rank_score"),
                        "lower_rank_score": lower.get("rank_score"),
                    }
                )
    if case.get("expect_equal_relevance_score") and preferred and lower and float(preferred.get("score") or 0.0) != float(lower.get("score") or 0.0):
        failures.append({**context, "expected": "equal base relevance score", "preferred_score": preferred.get("score"), "lower_score": lower.get("score")})
    for result in results:
        rank_features = result.get("rank_features") if isinstance(result.get("rank_features"), dict) else {}
        for field in _list_of_strings(case.get("required_rank_features")):
            if field not in rank_features:
                failures.append({**context, "doc_id": result.get("doc_id"), "missing_rank_feature": field})
    required_fields = _list_of_strings(case.get("required_evidence_fields"))
    evidence_chain = [item for item in packet.get("evidence_chain", []) if isinstance(item, dict)] if isinstance(packet.get("evidence_chain"), list) else []
    if not evidence_chain:
        failures.append({**context, "missing": "evidence_chain"})
    for index, evidence in enumerate(evidence_chain):
        for field in required_fields:
            if not evidence.get(field):
                failures.append({**context, "evidence_index": index, "missing_evidence_field": field})
    return failures


def cmd_eval_adapter_authority(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    suite_path = find_repo_root() / "evals" / "suites" / "adapter_authority_metadata.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    failures = []
    case_results = []
    for case in suite.get("cases", []):
        if not isinstance(case, dict):
            continue
        case_failures = _adapter_authority_failures(roots, case)
        case_results.append(
            {
                "case_id": case.get("case_id"),
                "run": case.get("run") or DEFAULT_RUN,
                "query": case.get("query"),
                "failure_count": len(case_failures),
            }
        )
        failures.extend(case_failures)
    _emit(
        {
            "schema": "aoa_course_eval_adapter_authority_v1",
            "suite_id": suite.get("suite_id"),
            "status": "ok" if not failures else "error",
            "case_results": case_results,
            "failures": failures,
        }
    )
    return 0 if not failures else 1


def _adapter_authority_failures(roots: StorageRoots, case: dict[str, object]) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    run_id = str(case.get("run") or DEFAULT_RUN)
    context = {"case_id": case.get("case_id"), "run": run_id}
    bundle_path = run_data_dir(roots, run_id) / "normalized" / "course_bundle.json"
    if not bundle_path.exists():
        return [{**context, "missing": "normalized bundle", "path": str(bundle_path)}]
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    normalized_path = case.get("normalized_path")
    if isinstance(normalized_path, list):
        item = _value_at_path(bundle, normalized_path)
        if not isinstance(item, dict):
            failures.append({**context, "missing": "normalized item", "normalized_path": normalized_path})
        else:
            expected_fields = case.get("expected_normalized_fields")
            field_items = expected_fields.items() if isinstance(expected_fields, dict) else []
            for field, expected in field_items:
                actual = item.get(str(field))
                if actual != expected:
                    failures.append({**context, "field": field, "expected": expected, "actual": actual})
    query = case.get("query")
    if query:
        packet = render_answer_packet(
            roots,
            str(query),
            run_id,
            int(case.get("limit") or 5),
            str(case.get("mode") or "keyword"),
        )
        results = [item for item in packet.get("results", []) if isinstance(item, dict)] if isinstance(packet.get("results"), list) else []
        if not results:
            failures.append({**context, "query": query, "missing": "query results"})
        else:
            top = results[0]
            expected_result = case.get("expected_top_result") if isinstance(case.get("expected_top_result"), dict) else {}
            for field, expected in expected_result.items():
                actual = top.get(str(field))
                if actual != expected:
                    failures.append({**context, "query": query, "top_doc_id": top.get("doc_id"), "field": field, "expected": expected, "actual": actual})
            expected_matching_result = case.get("expected_result") if isinstance(case.get("expected_result"), dict) else {}
            if expected_matching_result and not _has_matching_result(results, expected_matching_result):
                failures.append({**context, "query": query, "missing": "matching query result", "expected_result": expected_matching_result, "available": _compact_result_fields(results)})
            if not packet.get("evidence_chain"):
                failures.append({**context, "query": query, "missing": "evidence_chain"})
    return failures


def _has_matching_result(results: list[dict[str, object]], expected: dict[object, object]) -> bool:
    for result in results:
        if all(result.get(str(field)) == value for field, value in expected.items()):
            return True
    return False


def _compact_result_fields(results: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "doc_id": result.get("doc_id"),
            "kind": result.get("kind"),
            "authority_tier": result.get("authority_tier"),
            "authority_label": result.get("authority_label"),
        }
        for result in results
    ]


def _value_at_path(root: object, path: list[object]) -> object:
    current = root
    for part in path:
        if isinstance(current, dict):
            current = current.get(str(part))
        elif isinstance(current, list) and isinstance(part, int) and 0 <= part < len(current):
            current = current[part]
        else:
            return None
    return current


def _list_of_strings(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def cmd_eval_live_calibration(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    suite_path = find_repo_root() / "evals" / "suites" / "live_calibration_packet.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    browser_getcourse = smoke_browser_fixture_route(roots, platform="getcourse", run_id="getcourse-live-calibration-fixture", register=True)
    browser_skillspace = smoke_browser_fixture_route(roots, platform="skillspace", run_id="skillspace-live-calibration-fixture", register=True)
    stepik = smoke_stepik_fixture_route(
        roots,
        course_id=67,
        run_id="stepik-live-calibration-fixture",
        title="Stepik live calibration fixture",
        query="Stepik public API evidence",
    )
    preflight = live_preflight(roots, platforms=["stepik"])
    packet = build_live_calibration_packet(
        run_id="live-calibration-fixture",
        smoke_reports=[browser_getcourse, browser_skillspace, stepik],
        preflight_reports=[preflight],
    )
    packet_path = write_live_calibration_packet(roots, packet, run_id="live-calibration-fixture")
    failures = _live_calibration_failures(packet, suite)
    _emit(
        {
            "schema": "aoa_course_eval_live_calibration_v1",
            "suite_id": suite.get("suite_id"),
            "status": "ok" if not failures else "error",
            "packet_path": str(packet_path),
            "packet_status": packet.get("status"),
            "report_count": packet.get("report_count"),
            "platforms": packet.get("platforms"),
            "quality": packet.get("quality"),
            "failures": failures,
        }
    )
    return 0 if not failures else 1


def _live_calibration_failures(packet: dict[str, object], suite: dict[str, object]) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    if packet.get("status") != "ok":
        failures.append({"field": "packet_status", "expected": "ok", "actual": packet.get("status"), "packet_failures": packet.get("failures")})
    expected_report_count = int(suite.get("expected_report_count") or 0)
    if expected_report_count and int(packet.get("report_count") or 0) != expected_report_count:
        failures.append({"field": "report_count", "expected": expected_report_count, "actual": packet.get("report_count")})
    expected_platforms = sorted(_list_of_strings(suite.get("expected_platforms")))
    actual_platforms = sorted(_list_of_strings(packet.get("platforms")))
    if expected_platforms and actual_platforms != expected_platforms:
        failures.append({"field": "platforms", "expected": expected_platforms, "actual": actual_platforms})
    quality = packet.get("quality") if isinstance(packet.get("quality"), dict) else {}
    privacy = packet.get("privacy") if isinstance(packet.get("privacy"), dict) else {}
    min_result_count = int(suite.get("min_answer_result_count_total") or 0)
    if int(quality.get("answer_result_count_total") or 0) < min_result_count:
        failures.append({"field": "quality.answer_result_count_total", "expected_min": min_result_count, "actual": quality.get("answer_result_count_total")})
    min_evidence_count = int(suite.get("min_answer_evidence_count_total") or 0)
    if int(quality.get("answer_evidence_count_total") or 0) < min_evidence_count:
        failures.append({"field": "quality.answer_evidence_count_total", "expected_min": min_evidence_count, "actual": quality.get("answer_evidence_count_total")})
    min_transcript_count = int(suite.get("min_transcript_count_total") or 0)
    if int(quality.get("transcript_count_total") or 0) < min_transcript_count:
        failures.append({"field": "quality.transcript_count_total", "expected_min": min_transcript_count, "actual": quality.get("transcript_count_total")})
    min_caption_sidecar_count = int(suite.get("min_caption_sidecar_count_total") or 0)
    if int(quality.get("caption_sidecar_count_total") or 0) < min_caption_sidecar_count:
        failures.append({"field": "quality.caption_sidecar_count_total", "expected_min": min_caption_sidecar_count, "actual": quality.get("caption_sidecar_count_total")})
    transcript_source_authority_counts = quality.get("transcript_source_authority_counts") if isinstance(quality.get("transcript_source_authority_counts"), dict) else {}
    for source_authority in _list_of_strings(suite.get("required_transcript_source_authorities")):
        if int(transcript_source_authority_counts.get(source_authority) or 0) < 1:
            failures.append(
                {
                    "field": f"quality.transcript_source_authority_counts.{source_authority}",
                    "expected_min": 1,
                    "actual": transcript_source_authority_counts.get(source_authority),
                }
            )
    for field in _list_of_strings(suite.get("required_privacy_true_fields")):
        if privacy.get(field) is not True:
            failures.append({"field": f"privacy.{field}", "expected": True, "actual": privacy.get(field)})
    for field in _list_of_strings(suite.get("required_privacy_false_fields")):
        if privacy.get(field) is not False:
            failures.append({"field": f"privacy.{field}", "expected": False, "actual": privacy.get(field)})
    for field in _list_of_strings(suite.get("required_quality_true_fields")):
        if quality.get(field) is not True:
            failures.append({"field": f"quality.{field}", "expected": True, "actual": quality.get(field)})
    return failures


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


def cmd_eval_browser_hard_adapters(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    failures = []
    cases = [
        ("getcourse-browser-fixture", "GetCourse bootloader rollback evidence", ["getcourse", "bootloader", "rollback"]),
        ("skillspace-browser-fixture", "Skillspace logcat bugreport evidence", ["skillspace", "logcat", "bugreport"]),
    ]
    for run_id, query, terms in cases:
        packet = render_answer_packet(roots, query, run_id, 5)
        text = json.dumps(packet).casefold()
        missing_terms = [term for term in terms if term not in text]
        if missing_terms or not packet.get("evidence_chain"):
            failures.append({"run_id": run_id, "query": query, "missing_terms": missing_terms, "has_evidence": bool(packet.get("evidence_chain"))})
    _emit({"schema": "aoa_course_eval_browser_hard_adapters_v1", "status": "ok" if not failures else "error", "failures": failures})
    return 0 if not failures else 1


def cmd_eval_browser_crawl(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    failures = []
    cases = [
        ("getcourse-browser-crawl-fixture", "GetCourse bootloader rollback evidence", ["getcourse", "bootloader", "rollback"]),
        ("skillspace-browser-crawl-fixture", "Skillspace logcat bugreport evidence", ["skillspace", "logcat", "bugreport"]),
    ]
    for run_id, query, terms in cases:
        packet = render_answer_packet(roots, query, run_id, 5)
        text = json.dumps(packet).casefold()
        missing_terms = [term for term in terms if term not in text]
        if missing_terms or not packet.get("evidence_chain"):
            failures.append({"run_id": run_id, "query": query, "missing_terms": missing_terms, "has_evidence": bool(packet.get("evidence_chain"))})
    _emit({"schema": "aoa_course_eval_browser_crawl_v1", "status": "ok" if not failures else "error", "failures": failures})
    return 0 if not failures else 1


def cmd_eval_browser_progress_comments(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    failures = []
    cases = [
        ("getcourse-browser-fixture", "mentor anti-rollback vendor boot", ["mentor", "anti-rollback", "vendor", "boot"], "comment"),
        ("getcourse-browser-fixture", "2 of 4 lessons completed in_progress", ["2", "completed", "in_progress"], "progress"),
        ("skillspace-browser-fixture", "timestamp window reproduction step", ["timestamp", "reproduction", "mentor"], "comment"),
        ("skillspace-browser-fixture", "75 percent reviewed", ["75", "reviewed"], "progress"),
    ]
    for run_id, query, terms, expected_kind in cases:
        packet = render_answer_packet(roots, query, run_id, 5)
        text = json.dumps(packet).casefold()
        missing_terms = [term for term in terms if term.casefold() not in text]
        has_kind = any(isinstance(result, dict) and result.get("kind") == expected_kind for result in packet.get("results", []))
        if missing_terms or not has_kind or not packet.get("evidence_chain"):
            failures.append(
                {
                    "run_id": run_id,
                    "query": query,
                    "expected_kind": expected_kind,
                    "missing_terms": missing_terms,
                    "has_expected_kind": has_kind,
                    "has_evidence": bool(packet.get("evidence_chain")),
                }
            )
    _emit({"schema": "aoa_course_eval_browser_progress_comments_v1", "status": "ok" if not failures else "error", "failures": failures})
    return 0 if not failures else 1


def cmd_eval_browser_transcripts(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    failures = []
    cases = [
        ("getcourse-browser-fixture", "transcript excerpt vendor boot recovery plan", ["transcript", "vendor", "recovery"], "transcript", "browser_visible_transcript"),
        ("getcourse-browser-fixture", "sidecar caption safe mode recovery logs", ["sidecar", "safe", "recovery"], "transcript", "browser_caption_sidecar"),
        ("skillspace-browser-fixture", "caption bugreport timeline", ["caption", "bugreport", "timeline"], "transcript", "browser_visible_transcript"),
        ("skillspace-browser-fixture", "sidecar subtitle ANR tombstone evidence", ["sidecar", "anr", "tombstone"], "transcript", "browser_caption_sidecar"),
    ]
    for run_id, query, terms, expected_kind, expected_source_authority in cases:
        packet = render_answer_packet(roots, query, run_id, 5)
        text = json.dumps(packet).casefold()
        missing_terms = [term for term in terms if term.casefold() not in text]
        matching_results = [result for result in packet.get("results", []) if isinstance(result, dict) and result.get("kind") == expected_kind]
        has_source_authority = any(result.get("source_authority") == expected_source_authority for result in matching_results)
        if missing_terms or not matching_results or not has_source_authority or not packet.get("evidence_chain"):
            failures.append(
                {
                    "run_id": run_id,
                    "query": query,
                    "expected_kind": expected_kind,
                    "expected_source_authority": expected_source_authority,
                    "missing_terms": missing_terms,
                    "has_expected_kind": bool(matching_results),
                    "has_expected_source_authority": has_source_authority,
                    "has_evidence": bool(packet.get("evidence_chain")),
                }
            )
    _emit({"schema": "aoa_course_eval_browser_transcripts_v1", "status": "ok" if not failures else "error", "failures": failures})
    return 0 if not failures else 1


def cmd_eval_browser_discovery(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    registry = load_registry(roots.data)
    sources = registry.get("sources", [])
    failures = []
    for platform, term in [("getcourse", "stream/view"), ("skillspace", "/course/")]:
        matches = [
            source
            for source in sources
            if isinstance(source, dict)
            and source.get("platform") == platform
            and source.get("access_mode") == "browser_session"
            and term in str(source.get("source_ref") or "")
        ]
        if not matches:
            failures.append({"platform": platform, "missing_registered_source_hint": term})
    _emit({"schema": "aoa_course_eval_browser_discovery_v1", "status": "ok" if not failures else "error", "failures": failures})
    return 0 if not failures else 1


def cmd_eval_browser_sync(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    status = load_sync_status(roots, sync_run_id="browser-sync-fixture")
    checkpoints = status.get("checkpoints", [])
    failures = []
    for platform in ["getcourse", "skillspace"]:
        matches = [
            item
            for item in checkpoints
            if isinstance(item, dict)
            and item.get("platform") == platform
            and item.get("status") == "ok"
            and item.get("normalized_path")
            and item.get("index_path")
            and item.get("graph_path")
        ]
        if not matches:
            failures.append({"platform": platform, "missing": "ok checkpoint with normalized/index/graph paths"})
    _emit({"schema": "aoa_course_eval_browser_sync_v1", "status": "ok" if not failures else "error", "failures": failures})
    return 0 if not failures else 1


def cmd_eval_stepik_sync(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    status = load_sync_status(roots, sync_run_id="stepik-sync-fixture", platform="stepik")
    checkpoints = status.get("checkpoints", [])
    failures = []
    matches = [
        item
        for item in checkpoints
        if isinstance(item, dict)
        and item.get("platform") == "stepik"
        and item.get("status") == "ok"
        and item.get("normalized_path")
        and item.get("index_path")
        and item.get("graph_path")
    ]
    if not matches:
        failures.append(
            {
                "platform": "stepik",
                "missing": "ok checkpoint with normalized/index/graph paths",
            }
        )
    _emit({"schema": "aoa_course_eval_stepik_sync_v1", "status": "ok" if not failures else "error", "failures": failures})
    return 0 if not failures else 1


def cmd_eval_semantic_index(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    failures = []
    packet = render_answer_packet(roots, "bootloader rollback", DEFAULT_RUN, 5, "hybrid")
    text = json.dumps(packet).casefold()
    for term in ["bootloader", "rollback"]:
        if term not in text:
            failures.append({"missing_term": term})
    if not packet.get("evidence_chain"):
        failures.append({"missing": "evidence_chain"})
    if packet.get("mode") != "hybrid":
        failures.append({"missing": "hybrid mode"})
    _emit({"schema": "aoa_course_eval_semantic_index_v1", "status": "ok" if not failures else "error", "failures": failures})
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
