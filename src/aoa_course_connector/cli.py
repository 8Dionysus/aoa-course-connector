"""Command line interface for the AoA course connector."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from aoa_course_connector.adapters import adapter_list
from aoa_course_connector.adapters.browser import audit_browser_snapshot_file
from aoa_course_connector.auth import (
    browser_state_plan,
    capture_browser_state,
    default_browser_state_path,
    import_firefox_browser_state,
    inspect_browser_state,
)
from aoa_course_connector.bootstrap import bootstrap_fixture
from aoa_course_connector.calibration import (
    build_live_calibration_intake,
    build_live_calibration_packet,
    load_json_report,
    write_live_calibration_intake,
    write_live_calibration_packet,
)
from aoa_course_connector.calibration.connected_run import (
    load_connected_calibration_status,
    query_connected_calibration,
    query_connected_calibration_matrix,
    run_connected_calibration,
)
from aoa_course_connector.connection_profile import (
    apply_connection_profile,
    build_connection_profile,
    connection_profile_run_plan,
    connection_profile_status,
    default_connection_profile_path,
    inspect_connection_profile,
    load_connection_profile,
    write_connection_profile,
)
from aoa_course_connector.config import StorageRoots, find_repo_root
from aoa_course_connector.discover import (
    discover_browser_fixture as discover_browser_fixture_route,
    discover_browser_live as discover_browser_live_route,
    discover_browser_snapshot as discover_browser_snapshot_route,
    discover_stepik_account_browser_state as discover_stepik_account_browser_state_route,
    discover_stepik_account_fixture as discover_stepik_account_fixture_route,
    discover_stepik_account_live as discover_stepik_account_live_route,
)
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import HTTP_JSON_PROVIDER, LOCAL_HASHING_PROVIDER, build_keyword_index, build_semantic_index
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
from aoa_course_connector.query import graph_neighbors, query_index, render_answer_packet, render_lesson_context_packet, write_answer_packet
from aoa_course_connector.readiness import connected_source_plan, live_preflight, semantic_provider_preflight
from aoa_course_connector.refresh import refresh_query_cycle
from aoa_course_connector.smoke import (
    smoke_browser_fixture as smoke_browser_fixture_route,
    smoke_browser_live as smoke_browser_live_route,
    smoke_browser_snapshot as smoke_browser_snapshot_route,
    smoke_stepik_fixture as smoke_stepik_fixture_route,
    smoke_stepik_live as smoke_stepik_live_route,
)
from aoa_course_connector.sources import load_registry, upsert_source
from aoa_course_connector.stepik_options import (
    DEFAULT_MAX_STEP_SOURCES,
    DEFAULT_STEP_SOURCE_TIMEOUT,
    normalize_max_step_sources,
    normalize_step_source_timeout,
)
from aoa_course_connector.status import connector_readiness, source_registry_catalog
from aoa_course_connector.storage import create_storage_roots, run_data_dir, storage_status
from aoa_course_connector.sync import (
    load_sync_status,
    sync_browser_fixture_sources,
    sync_browser_live_sources,
    sync_stepik_fixture_sources,
    sync_stepik_live_sources,
)


DEFAULT_RUN = "starter-fixture"


def _step_source_limit(value: str) -> int | None:
    try:
        return normalize_max_step_sources(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aoa-course")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor")
    doctor.set_defaults(func=cmd_doctor)

    readiness = sub.add_parser("readiness")
    readiness.add_argument("--run", action="append")
    readiness.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"], action="append")
    readiness.add_argument("--source-id", action="append")
    readiness.add_argument("--connected-run", default="connected-calibration")
    readiness.add_argument("--stepik-token-env", default="STEPIK_API_TOKEN")
    readiness.add_argument("--state-file", type=Path)
    readiness.add_argument("--expect-origin")
    readiness.add_argument("--include-disabled", action="store_true")
    readiness.add_argument("--query")
    readiness.add_argument("--max-lessons", type=int, default=50)
    readiness.add_argument("--max-pages", type=int, default=5)
    readiness.add_argument("--max-sources", type=int, default=50)
    readiness.add_argument("--link-pattern")
    readiness.add_argument("--live-scope", choices=["bounded", "full-course"], default="bounded")
    readiness.add_argument("--include-step-sources", action="store_true")
    readiness.add_argument("--max-step-sources", type=_step_source_limit, default=DEFAULT_MAX_STEP_SOURCES)
    readiness.add_argument("--step-source-timeout", type=float, default=DEFAULT_STEP_SOURCE_TIMEOUT)
    readiness.add_argument("--semantic-provider", choices=[LOCAL_HASHING_PROVIDER, HTTP_JSON_PROVIDER], default=LOCAL_HASHING_PROVIDER)
    readiness.add_argument("--dimensions", type=int, default=256)
    readiness.add_argument("--embedding-endpoint")
    readiness.add_argument("--embedding-model")
    readiness.add_argument("--embedding-token-env", default="AOA_COURSE_EMBEDDING_TOKEN")
    readiness.add_argument("--embedding-batch-size", type=int, default=32)
    readiness.add_argument("--embedding-timeout-seconds", type=float, default=30.0)
    readiness.add_argument("--require-ready", action="store_true")
    readiness.set_defaults(func=cmd_readiness)

    init = sub.add_parser("init")
    init.set_defaults(func=cmd_init)

    bootstrap = sub.add_parser("bootstrap")
    bootstrap_sub = bootstrap.add_subparsers(dest="bootstrap_command", required=True)
    bootstrap_fixture_parser = bootstrap_sub.add_parser("fixture")
    bootstrap_fixture_parser.add_argument("--run", default=DEFAULT_RUN)
    bootstrap_fixture_parser.add_argument("--fixture", type=Path)
    bootstrap_fixture_parser.add_argument("--connected-run", default="connected-calibration")
    bootstrap_fixture_parser.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"], action="append")
    bootstrap_fixture_parser.add_argument("--query")
    bootstrap_fixture_parser.add_argument("--skip-connected", action="store_true")
    bootstrap_fixture_parser.set_defaults(func=cmd_bootstrap_fixture)

    storage = sub.add_parser("storage")
    storage_sub = storage.add_subparsers(dest="storage_command", required=True)
    status = storage_sub.add_parser("status")
    status.add_argument("--measure", action="store_true")
    status.set_defaults(func=cmd_storage_status)

    adapters = sub.add_parser("adapters")
    adapters_sub = adapters.add_subparsers(dest="adapters_command", required=True)
    adapters_sub.add_parser("list").set_defaults(func=cmd_adapters_list)

    connect = sub.add_parser("connect")
    connect_sub = connect.add_subparsers(dest="connect_command", required=True)
    connect_profile = connect_sub.add_parser("profile")
    connect_profile.add_argument("--name", default="operator-connection")
    connect_profile.add_argument("--getcourse-url", action="append")
    connect_profile.add_argument("--skillspace-url", action="append")
    connect_profile.add_argument("--stepik-course-id", action="append")
    connect_profile.add_argument("--getcourse-state-file", type=Path)
    connect_profile.add_argument("--skillspace-state-file", type=Path)
    connect_profile.add_argument("--stepik-token-env", default="STEPIK_API_TOKEN")
    connect_profile.add_argument("--run", default="connected-calibration")
    connect_profile.add_argument("--query")
    connect_profile.add_argument("--live-scope", choices=["bounded", "full-course"], default="bounded")
    connect_profile.add_argument("--include-step-sources", action="store_true")
    connect_profile.add_argument("--max-step-sources", type=_step_source_limit, default=DEFAULT_MAX_STEP_SOURCES)
    connect_profile.add_argument("--step-source-timeout", type=float, default=DEFAULT_STEP_SOURCE_TIMEOUT)
    connect_profile.add_argument("--max-lessons", type=int, default=50)
    connect_profile.add_argument("--max-pages", type=int, default=5)
    connect_profile.add_argument("--max-sources", type=int, default=50)
    connect_profile.add_argument("--link-pattern")
    connect_profile.add_argument("--semantic-provider", choices=[LOCAL_HASHING_PROVIDER, HTTP_JSON_PROVIDER], default=LOCAL_HASHING_PROVIDER)
    connect_profile.add_argument("--dimensions", type=int, default=256)
    connect_profile.add_argument("--embedding-endpoint")
    connect_profile.add_argument("--embedding-model")
    connect_profile.add_argument("--embedding-token-env", default="AOA_COURSE_EMBEDDING_TOKEN")
    connect_profile.add_argument("--embedding-batch-size", type=int, default=32)
    connect_profile.add_argument("--embedding-timeout-seconds", type=float, default=30.0)
    connect_profile.add_argument("--write", type=Path)
    connect_profile.set_defaults(func=cmd_connect_profile)
    connect_inspect = connect_sub.add_parser("inspect")
    connect_inspect.add_argument("profile", type=Path)
    connect_inspect.set_defaults(func=cmd_connect_inspect)
    connect_apply = connect_sub.add_parser("apply")
    connect_apply.add_argument("profile", type=Path)
    connect_apply.set_defaults(func=cmd_connect_apply)
    connect_status = connect_sub.add_parser("status")
    connect_status.add_argument("profile", type=Path)
    connect_status.set_defaults(func=cmd_connect_status)
    connect_run = connect_sub.add_parser("run")
    connect_run.add_argument("profile", type=Path)
    connect_run.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"])
    connect_run.add_argument("--source-id", action="append")
    connect_run.add_argument("--allow-network", action="store_true")
    connect_run.add_argument("--require-ready", action="store_true")
    connect_run.set_defaults(func=cmd_connect_run)

    preflight = sub.add_parser("preflight")
    preflight_sub = preflight.add_subparsers(dest="preflight_command", required=True)
    preflight_live = preflight_sub.add_parser("live")
    preflight_live.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"], action="append")
    preflight_live.add_argument("--source-id", action="append")
    preflight_live.add_argument("--stepik-token-env", default="STEPIK_API_TOKEN")
    preflight_live.add_argument("--state-file", type=Path)
    preflight_live.add_argument("--expect-origin")
    preflight_live.add_argument("--include-disabled", action="store_true")
    preflight_live.add_argument("--require-ready", action="store_true")
    preflight_live.set_defaults(func=cmd_preflight_live)
    preflight_plan = preflight_sub.add_parser("connected-plan")
    preflight_plan.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"], action="append")
    preflight_plan.add_argument("--source-id", action="append")
    preflight_plan.add_argument("--stepik-token-env", default="STEPIK_API_TOKEN")
    preflight_plan.add_argument("--state-file", type=Path)
    preflight_plan.add_argument("--expect-origin")
    preflight_plan.add_argument("--include-disabled", action="store_true")
    preflight_plan.add_argument("--query")
    preflight_plan.add_argument("--max-lessons", type=int, default=50)
    preflight_plan.add_argument("--max-pages", type=int, default=5)
    preflight_plan.add_argument("--max-sources", type=int, default=50)
    preflight_plan.add_argument("--link-pattern")
    preflight_plan.add_argument("--calibration-run", default="connected-live-calibration")
    preflight_plan.add_argument("--live-scope", choices=["bounded", "full-course"], default="bounded")
    preflight_plan.add_argument("--include-step-sources", action="store_true")
    preflight_plan.add_argument("--max-step-sources", type=_step_source_limit, default=DEFAULT_MAX_STEP_SOURCES)
    preflight_plan.add_argument("--step-source-timeout", type=float, default=DEFAULT_STEP_SOURCE_TIMEOUT)
    preflight_plan.add_argument("--require-ready", action="store_true")
    preflight_plan.set_defaults(func=cmd_preflight_connected_plan)
    preflight_semantic = preflight_sub.add_parser("semantic-provider")
    preflight_semantic.add_argument("--run", default=DEFAULT_RUN)
    preflight_semantic.add_argument("--provider", choices=[LOCAL_HASHING_PROVIDER, HTTP_JSON_PROVIDER], default=LOCAL_HASHING_PROVIDER)
    preflight_semantic.add_argument("--dimensions", type=int, default=256)
    preflight_semantic.add_argument("--embedding-endpoint")
    preflight_semantic.add_argument("--embedding-model")
    preflight_semantic.add_argument("--embedding-token-env", default="AOA_COURSE_EMBEDDING_TOKEN")
    preflight_semantic.add_argument("--embedding-batch-size", type=int, default=32)
    preflight_semantic.add_argument("--embedding-timeout-seconds", type=float, default=30.0)
    preflight_semantic.add_argument("--require-ready", action="store_true")
    preflight_semantic.set_defaults(func=cmd_preflight_semantic_provider)

    sources = sub.add_parser("sources")
    sources_sub = sources.add_subparsers(dest="sources_command", required=True)
    sources_add = sources_sub.add_parser("add")
    sources_add.add_argument("source_ref")
    sources_add.add_argument("--platform", required=True)
    sources_add.add_argument("--title")
    sources_add.add_argument("--access-mode")
    sources_add.add_argument("--disabled", action="store_true")
    sources_add.set_defaults(func=cmd_sources_add)
    sources_list = sources_sub.add_parser("list")
    sources_list.add_argument("--platform", action="append")
    sources_list.add_argument("--source-id", action="append")
    sources_list.add_argument("--include-disabled", action="store_true")
    sources_list.add_argument("--no-source-refs", action="store_false", dest="include_source_refs")
    sources_list.add_argument("--no-connected-runs", action="store_false", dest="include_connected_runs")
    sources_list.add_argument("--connected-run-limit", type=int, default=3)
    sources_list.add_argument("--connected-receipt-limit", type=int, default=50)
    sources_list.set_defaults(func=cmd_sources_list, include_source_refs=True, include_connected_runs=True)
    sources_answer = sources_sub.add_parser("answer")
    sources_answer.add_argument("query")
    sources_answer.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"], action="append")
    sources_answer.add_argument("--source-id", action="append")
    sources_answer.add_argument("--kind", choices=["smoke", "sync"], action="append")
    sources_answer.add_argument("--limit", type=int, default=5)
    sources_answer.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="keyword")
    sources_answer.add_argument("--graph-limit", type=int, default=12)
    sources_answer.add_argument("--source-limit", type=int, default=10)
    sources_answer.add_argument("--connected-run-limit", type=int, default=5)
    sources_answer.add_argument("--connected-receipt-limit", type=int, default=50)
    sources_answer.add_argument("--include-disabled", action="store_true")
    sources_answer.add_argument("--include-source-refs", action="store_true")
    sources_answer.set_defaults(func=cmd_sources_answer)
    sources_answer_matrix = sources_sub.add_parser("answer-matrix")
    sources_answer_matrix.add_argument("--query", action="append", required=True)
    sources_answer_matrix.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"], action="append")
    sources_answer_matrix.add_argument("--source-id", action="append")
    sources_answer_matrix.add_argument("--kind", choices=["smoke", "sync"], action="append")
    sources_answer_matrix.add_argument("--limit", type=int, default=5)
    sources_answer_matrix.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="keyword")
    sources_answer_matrix.add_argument("--coverage-mode", choices=["all-sources", "portfolio"], default="all-sources")
    sources_answer_matrix.add_argument("--graph-limit", type=int, default=12)
    sources_answer_matrix.add_argument("--source-limit", type=int, default=10)
    sources_answer_matrix.add_argument("--connected-run-limit", type=int, default=5)
    sources_answer_matrix.add_argument("--connected-receipt-limit", type=int, default=50)
    sources_answer_matrix.add_argument("--include-disabled", action="store_true")
    sources_answer_matrix.add_argument("--include-source-refs", action="store_true")
    sources_answer_matrix.set_defaults(func=cmd_sources_answer_matrix)

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
    capture.add_argument("--expect-origin-contains")
    capture.set_defaults(func=cmd_auth_capture_browser_state)
    firefox = auth_sub.add_parser("import-firefox-state")
    firefox.add_argument("platform")
    firefox.add_argument("source_ref")
    firefox.add_argument("--state-file", type=Path)
    firefox.add_argument("--profile-dir", type=Path)
    firefox.add_argument("--profile-name")
    firefox.add_argument("--profiles-ini", type=Path)
    firefox.add_argument("--expect-origin-contains")
    firefox.set_defaults(func=cmd_auth_import_firefox_state)
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
    discover_stepik_account.add_argument("--state-file", type=Path)
    discover_stepik_account.add_argument("--max-pages", type=int, default=5)
    discover_stepik_account.add_argument("--batch-size", type=int, default=20)
    discover_stepik_account.add_argument("--source-limit", type=int)
    discover_stepik_account.add_argument("--access-mode", choices=["api_token", "oauth", "browser_session"], default=None)
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
    discover_browser_live.add_argument("--wait-until", default="domcontentloaded")
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
    stepik_live.add_argument("--state-file", type=Path)
    stepik_live.add_argument("--max-sections", type=int, default=1)
    stepik_live.add_argument("--max-units-per-section", type=int, default=2)
    stepik_live.add_argument("--max-steps-per-lesson", type=int, default=5)
    stepik_live.add_argument("--batch-size", type=int, default=20)
    stepik_live.add_argument("--include-step-sources", action="store_true")
    stepik_live.add_argument("--max-step-sources", type=_step_source_limit, default=10)
    stepik_live.add_argument("--step-source-timeout", type=float, default=5.0)
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
    browser_live.add_argument("--source-id")
    browser_live.add_argument("--state-file", type=Path)
    browser_live.add_argument("--wait-until", default="domcontentloaded")
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
    crawl_live.add_argument("--source-id")
    crawl_live.add_argument("--state-file", type=Path)
    crawl_live.add_argument("--wait-until", default="domcontentloaded")
    crawl_live.add_argument("--max-lessons", type=int, default=20)
    crawl_live.add_argument("--link-pattern")
    crawl_live.set_defaults(func=cmd_crawl_browser_live)

    sync = sub.add_parser("sync")
    sync_sub = sync.add_subparsers(dest="sync_command", required=True)
    sync_fixture = sync_sub.add_parser("browser-fixture")
    sync_fixture.add_argument("--run", default="browser-sync-fixture")
    sync_fixture.add_argument("--platform", choices=["getcourse", "skillspace"], action="append")
    sync_fixture.add_argument("--source-id", action="append")
    sync_fixture.add_argument("--max-lessons", type=int, default=20)
    sync_fixture.add_argument("--link-pattern")
    sync_fixture.add_argument("--source-limit", type=int)
    sync_fixture.add_argument("--build-artifacts", action="store_true")
    sync_fixture.set_defaults(func=cmd_sync_browser_fixture)
    sync_live = sync_sub.add_parser("browser-live")
    sync_live.add_argument("--run", default="browser-live-sync")
    sync_live.add_argument("--platform", choices=["getcourse", "skillspace"], action="append")
    sync_live.add_argument("--source-id", action="append")
    sync_live.add_argument("--state-file", type=Path)
    sync_live.add_argument("--wait-until", default="domcontentloaded")
    sync_live.add_argument("--max-lessons", type=int, default=20)
    sync_live.add_argument("--link-pattern")
    sync_live.add_argument("--source-limit", type=int)
    sync_live.add_argument("--build-artifacts", action="store_true")
    sync_live.set_defaults(func=cmd_sync_browser_live)
    sync_stepik_fixture = sync_sub.add_parser("stepik-fixture")
    sync_stepik_fixture.add_argument("--run", default="stepik-sync-fixture")
    sync_stepik_fixture.add_argument("--source-id", action="append")
    sync_stepik_fixture.add_argument("--source-limit", type=int)
    sync_stepik_fixture.add_argument("--build-artifacts", action="store_true")
    sync_stepik_fixture.set_defaults(func=cmd_sync_stepik_fixture)
    sync_stepik_live = sync_sub.add_parser("stepik-live")
    sync_stepik_live.add_argument("--run", default="stepik-live-sync")
    sync_stepik_live.add_argument("--source-id", action="append")
    sync_stepik_live.add_argument("--token-env", default="STEPIK_API_TOKEN")
    sync_stepik_live.add_argument("--state-file", type=Path)
    sync_stepik_live.add_argument("--max-sections", type=int, default=1)
    sync_stepik_live.add_argument("--max-units-per-section", type=int, default=2)
    sync_stepik_live.add_argument("--max-steps-per-lesson", type=int, default=5)
    sync_stepik_live.add_argument("--batch-size", type=int, default=20)
    sync_stepik_live.add_argument("--include-step-sources", action="store_true")
    sync_stepik_live.add_argument("--max-step-sources", type=_step_source_limit, default=10)
    sync_stepik_live.add_argument("--step-source-timeout", type=float, default=5.0)
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
    smoke_live.add_argument("--source-id")
    smoke_live.add_argument("--catalog-url")
    smoke_live.add_argument("--course-url")
    smoke_live.add_argument("--state-file", type=Path)
    smoke_live.add_argument("--wait-until", default="domcontentloaded")
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
    smoke_stepik_live.add_argument("--access-mode", choices=["public_api", "api_token", "oauth", "browser_session"], default="public_api")
    smoke_stepik_live.add_argument("--token-env", default="STEPIK_API_TOKEN")
    smoke_stepik_live.add_argument("--state-file", type=Path)
    smoke_stepik_live.add_argument("--max-sections", type=int, default=1)
    smoke_stepik_live.add_argument("--max-units-per-section", type=int, default=2)
    smoke_stepik_live.add_argument("--max-steps-per-lesson", type=int, default=5)
    smoke_stepik_live.add_argument("--batch-size", type=int, default=20)
    smoke_stepik_live.add_argument("--include-step-sources", action="store_true")
    smoke_stepik_live.add_argument("--max-step-sources", type=_step_source_limit, default=10)
    smoke_stepik_live.add_argument("--step-source-timeout", type=float, default=5.0)
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
    calibration_intake = calibration_sub.add_parser("intake")
    calibration_intake.add_argument("--run", default="live-calibration-intake")
    calibration_intake.add_argument("--packet", type=Path, required=True)
    calibration_intake.set_defaults(func=cmd_calibration_intake)
    calibration_connected = calibration_sub.add_parser("connected-run")
    calibration_connected.add_argument("--run", default="connected-calibration")
    calibration_connected.add_argument("--mode", choices=["fixture", "live"], default="fixture")
    calibration_connected.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"], action="append")
    calibration_connected.add_argument("--source-id", action="append")
    calibration_connected.add_argument("--query")
    calibration_connected.add_argument("--live-scope", choices=["bounded", "full-course"], default="bounded")
    calibration_connected.add_argument("--include-step-sources", action="store_true")
    calibration_connected.add_argument("--max-step-sources", type=_step_source_limit, default=10)
    calibration_connected.add_argument("--step-source-timeout", type=float, default=5.0)
    calibration_connected.add_argument("--allow-network", action="store_true")
    calibration_connected.add_argument("--stepik-token-env", default="STEPIK_API_TOKEN")
    calibration_connected.add_argument("--state-file", type=Path)
    calibration_connected.add_argument("--expect-origin")
    calibration_connected.add_argument("--max-lessons", type=int, default=50)
    calibration_connected.add_argument("--max-pages", type=int, default=5)
    calibration_connected.add_argument("--max-sources", type=int, default=50)
    calibration_connected.add_argument("--link-pattern")
    calibration_connected.add_argument("--source-limit", type=int)
    calibration_connected.set_defaults(func=cmd_calibration_connected_run)
    calibration_status = calibration_sub.add_parser("status")
    calibration_status.add_argument("--run", default="connected-calibration")
    calibration_status.set_defaults(func=cmd_calibration_status)
    calibration_query = calibration_sub.add_parser("query")
    calibration_query.add_argument("--run", default="connected-calibration")
    calibration_query.add_argument("--query")
    calibration_query.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"], action="append")
    calibration_query.add_argument("--source-id", action="append")
    calibration_query.add_argument("--kind", choices=["smoke", "sync"], action="append")
    calibration_query.add_argument("--limit", type=int, default=5)
    calibration_query.add_argument("--mode", choices=["keyword", "semantic", "hybrid"])
    calibration_query.add_argument("--graph-limit", type=int, default=12)
    calibration_query.add_argument("--entry-limit", type=int, default=5)
    calibration_query.set_defaults(func=cmd_calibration_query)
    calibration_query_matrix = calibration_sub.add_parser("query-matrix")
    calibration_query_matrix.add_argument("--run", default="connected-calibration")
    calibration_query_matrix.add_argument("--query", action="append", required=True)
    calibration_query_matrix.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"], action="append")
    calibration_query_matrix.add_argument("--source-id", action="append")
    calibration_query_matrix.add_argument("--kind", choices=["smoke", "sync"], action="append")
    calibration_query_matrix.add_argument("--limit", type=int, default=5)
    calibration_query_matrix.add_argument("--mode", choices=["keyword", "semantic", "hybrid"])
    calibration_query_matrix.add_argument("--graph-limit", type=int, default=12)
    calibration_query_matrix.add_argument("--entry-limit", type=int, default=5)
    calibration_query_matrix.set_defaults(func=cmd_calibration_query_matrix)

    build_index = sub.add_parser("build-index")
    build_index.add_argument("--run", default=DEFAULT_RUN)
    build_index.set_defaults(func=cmd_build_index)

    build_semantic = sub.add_parser("build-semantic-index")
    build_semantic.add_argument("--run", default=DEFAULT_RUN)
    build_semantic.add_argument("--dimensions", type=int, default=256)
    build_semantic.add_argument("--provider", choices=[LOCAL_HASHING_PROVIDER, HTTP_JSON_PROVIDER], default=LOCAL_HASHING_PROVIDER)
    build_semantic.add_argument("--embedding-endpoint")
    build_semantic.add_argument("--embedding-model")
    build_semantic.add_argument("--embedding-token-env")
    build_semantic.add_argument("--embedding-batch-size", type=int, default=32)
    build_semantic.add_argument("--embedding-timeout-seconds", type=float, default=30.0)
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

    lesson_context = sub.add_parser("lesson-context")
    lesson_context.add_argument("query")
    lesson_context.add_argument("--run", default=DEFAULT_RUN)
    lesson_context.add_argument("--limit", type=int, default=5)
    lesson_context.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="keyword")
    lesson_context.add_argument("--graph-limit", type=int, default=12)
    lesson_context.set_defaults(func=cmd_lesson_context)

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

    inspect_root = sub.add_parser("inspect")
    inspect_sub = inspect_root.add_subparsers(dest="inspect_command", required=True)
    inspect_browser_snapshot = inspect_sub.add_parser("browser-snapshot")
    inspect_browser_snapshot.add_argument("snapshot", type=Path)
    inspect_browser_snapshot.add_argument("--platform", choices=["getcourse", "skillspace"])
    inspect_browser_snapshot.add_argument("--max-sources", type=int, default=50)
    inspect_browser_snapshot.add_argument("--max-lessons", type=int, default=50)
    inspect_browser_snapshot.add_argument("--link-pattern")
    inspect_browser_snapshot.add_argument("--require-ready", action="store_true")
    inspect_browser_snapshot.set_defaults(func=cmd_inspect_browser_snapshot)

    refresh = sub.add_parser("refresh")
    refresh_sub = refresh.add_subparsers(dest="refresh_command", required=True)
    refresh_query = refresh_sub.add_parser("query")
    refresh_query.add_argument("query")
    refresh_query.add_argument("--run", default=DEFAULT_RUN)
    refresh_query.add_argument("--limit", type=int, default=5)
    refresh_query.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="keyword")
    refresh_query.add_argument("--strategy", choices=["plan", "fixture", "live"], default="plan")
    refresh_query.add_argument("--execute", action="store_true")
    refresh_query.add_argument("--source-id")
    refresh_query.add_argument("--sync-run")
    refresh_query.add_argument("--allow-network", action="store_true")
    refresh_query.add_argument("--state-file", type=Path)
    refresh_query.add_argument("--stepik-token-env", default="STEPIK_API_TOKEN")
    refresh_query.add_argument("--max-lessons", type=int, default=20)
    refresh_query.add_argument("--max-sections", type=int, default=1)
    refresh_query.add_argument("--max-units-per-section", type=int, default=2)
    refresh_query.add_argument("--max-steps-per-lesson", type=int, default=5)
    refresh_query.add_argument("--batch-size", type=int, default=20)
    refresh_query.add_argument("--include-step-sources", action="store_true")
    refresh_query.set_defaults(func=cmd_refresh_query)

    eval_parser = sub.add_parser("eval")
    eval_sub = eval_parser.add_subparsers(dest="eval_command", required=True)
    eval_sub.add_parser("install-route").set_defaults(func=cmd_eval_install_route)
    eval_sub.add_parser("answer-packets").set_defaults(func=cmd_eval_answer_packets)
    eval_sub.add_parser("answer-quality").set_defaults(func=cmd_eval_answer_quality)
    eval_sub.add_parser("retrieval-loop").set_defaults(func=cmd_eval_retrieval_loop)
    source_registry_query = eval_sub.add_parser("source-registry-query")
    source_registry_query.add_argument("--query", action="append")
    source_registry_query.add_argument("--platform", choices=["getcourse", "skillspace", "stepik"], action="append")
    source_registry_query.add_argument("--source-id", action="append")
    source_registry_query.add_argument("--kind", choices=["smoke", "sync"], action="append")
    source_registry_query.add_argument("--limit", type=int, default=5)
    source_registry_query.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="hybrid")
    source_registry_query.add_argument("--coverage-mode", choices=["all-sources", "portfolio"], default="all-sources")
    source_registry_query.add_argument("--graph-limit", type=int, default=12)
    source_registry_query.add_argument("--source-limit", type=int, default=10)
    source_registry_query.add_argument("--connected-run-limit", type=int, default=5)
    source_registry_query.add_argument("--connected-receipt-limit", type=int, default=50)
    source_registry_query.add_argument("--query-sample-limit", type=int, default=3)
    source_registry_query.add_argument("--min-query-count", type=int, default=2)
    source_registry_query.add_argument("--min-ready-query-count", type=int)
    source_registry_query.add_argument("--min-response-count", type=int, default=1)
    source_registry_query.add_argument("--min-evidence-count", type=int, default=1)
    source_registry_query.add_argument("--min-grounded-response-count", type=int, default=1)
    source_registry_query.add_argument("--min-source-count", type=int, default=1)
    source_registry_query.add_argument("--include-disabled", action="store_true")
    source_registry_query.set_defaults(func=cmd_eval_source_registry_query)
    eval_sub.add_parser("freshness-ranking").set_defaults(func=cmd_eval_freshness_ranking)
    eval_sub.add_parser("place-ranking").set_defaults(func=cmd_eval_place_ranking)
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


def cmd_readiness(args: argparse.Namespace) -> int:
    repo_root = find_repo_root()
    roots = StorageRoots.from_env(repo_root)
    tools = {str(tool.get("name")) for tool in tools_manifest().get("tools", []) if isinstance(tool, dict)}
    report = connector_readiness(
        repo_root,
        roots,
        runs=args.run,
        platforms=args.platform,
        source_ids=args.source_id,
        connected_run=args.connected_run,
        stepik_token_env=args.stepik_token_env,
        browser_state_file=args.state_file,
        expect_origin_contains=args.expect_origin,
        include_disabled=args.include_disabled,
        query=args.query,
        max_lessons=args.max_lessons,
        max_pages=args.max_pages,
        max_sources=args.max_sources,
        link_pattern=args.link_pattern,
        live_scope=args.live_scope,
        include_step_sources=args.include_step_sources,
        max_step_sources=args.max_step_sources,
        step_source_timeout=args.step_source_timeout,
        semantic_provider=args.semantic_provider,
        dimensions=args.dimensions,
        embedding_endpoint=args.embedding_endpoint,
        embedding_model=args.embedding_model,
        embedding_token_env=args.embedding_token_env,
        embedding_batch_size=args.embedding_batch_size,
        embedding_timeout_seconds=args.embedding_timeout_seconds,
        mcp_tool_names=tools,
    )
    _emit(report)
    if args.require_ready and not bool(report.get("operational_ready")):
        return 1
    return 0 if report.get("status") != "error" else 1


def cmd_init(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    _emit({"schema": "aoa_course_init_v1", "status": "ok", "created": create_storage_roots(roots), "network_touched": False})
    return 0


def cmd_bootstrap_fixture(args: argparse.Namespace) -> int:
    repo_root = find_repo_root()
    roots = StorageRoots.from_env(repo_root)
    tools = {str(tool.get("name")) for tool in tools_manifest().get("tools", []) if isinstance(tool, dict)}
    receipt = bootstrap_fixture(
        repo_root,
        roots,
        run_id=args.run,
        fixture=args.fixture,
        connected_run=args.connected_run,
        platforms=args.platform,
        query=args.query,
        skip_connected=args.skip_connected,
        mcp_tool_names=tools,
    )
    _emit(receipt)
    return 0 if receipt.get("status") == "ok" else 1


def cmd_storage_status(args: argparse.Namespace) -> int:
    repo_root = find_repo_root()
    _emit(storage_status(repo_root, StorageRoots.from_env(repo_root), measure=args.measure))
    return 0


def cmd_adapters_list(_args: argparse.Namespace) -> int:
    _emit({"schema": "aoa_course_adapters_v1", "adapters": adapter_list()})
    return 0


def cmd_connect_profile(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    create_storage_roots(roots)
    profile = build_connection_profile(
        roots,
        name=args.name,
        getcourse_urls=args.getcourse_url,
        skillspace_urls=args.skillspace_url,
        stepik_course_ids=args.stepik_course_id,
        getcourse_state_file=args.getcourse_state_file,
        skillspace_state_file=args.skillspace_state_file,
        stepik_token_env=args.stepik_token_env,
        run_id=args.run,
        query=args.query,
        live_scope=args.live_scope,
        include_step_sources=args.include_step_sources,
        max_step_sources=args.max_step_sources,
        step_source_timeout=args.step_source_timeout,
        max_lessons=args.max_lessons,
        max_pages=args.max_pages,
        max_sources=args.max_sources,
        link_pattern=args.link_pattern,
        semantic_provider=args.semantic_provider,
        dimensions=args.dimensions,
        embedding_endpoint=args.embedding_endpoint,
        embedding_model=args.embedding_model,
        embedding_token_env=args.embedding_token_env,
        embedding_batch_size=args.embedding_batch_size,
        embedding_timeout_seconds=args.embedding_timeout_seconds,
    )
    path = args.write or default_connection_profile_path(roots.artifact, args.name)
    written = write_connection_profile(profile, path)
    inspection = inspect_connection_profile(roots, profile, profile_path=Path(str(written["path"])))
    _emit(
        {
            "schema": "aoa_course_connection_profile_receipt_v1",
            "status": "ok",
            "network_touched": False,
            "redacted": True,
            "profile_path": written["path"],
            "write": written,
            "profile": profile,
            "inspection": inspection,
        }
    )
    return 0


def cmd_connect_inspect(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    profile = load_connection_profile(args.profile)
    inspection = inspect_connection_profile(roots, profile, profile_path=args.profile)
    _emit(inspection)
    return 0


def cmd_connect_apply(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    create_storage_roots(roots)
    profile = load_connection_profile(args.profile)
    receipt = apply_connection_profile(roots, profile, profile_path=args.profile)
    _emit(receipt)
    return 0


def cmd_connect_status(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    profile = load_connection_profile(args.profile)
    inspection = inspect_connection_profile(roots, profile, profile_path=args.profile)
    _emit(connection_profile_status(inspection))
    return 0


def cmd_connect_run(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    profile = load_connection_profile(args.profile)
    inspection = inspect_connection_profile(roots, profile, profile_path=args.profile)
    run_plan = connection_profile_run_plan(profile, inspection, platform=args.platform, source_ids=args.source_id)
    if not args.allow_network:
        receipt = {
            "schema": "aoa_course_connection_profile_run_receipt_v1",
            "status": "planned" if run_plan.get("ready") else "blocked",
            "network_touched": False,
            "executed": False,
            "profile": inspection.get("profile"),
            "run_plan": run_plan,
            "next_commands": [run_plan.get("command")] if run_plan.get("ready") and run_plan.get("command") else run_plan.get("candidate_commands", []),
        }
        _emit(receipt)
        return 0 if run_plan.get("ready") or not args.require_ready else 1
    if not run_plan.get("ready"):
        _emit(
            {
                "schema": "aoa_course_connection_profile_run_receipt_v1",
                "status": "blocked",
                "network_touched": False,
                "executed": False,
                "profile": inspection.get("profile"),
                "run_plan": run_plan,
                "error": "connection profile is not ready for live connected-run",
            }
        )
        return 2
    browser_state_file = Path(str(run_plan.get("browser_state_file"))) if run_plan.get("browser_state_file") else None
    receipt = run_connected_calibration(
        roots,
        run_id=str(run_plan.get("run_id") or "connected-calibration"),
        mode="live",
        platforms=[str(run_plan.get("platform") or "")],
        source_ids=[str(source_id) for source_id in run_plan.get("source_ids", [])] if isinstance(run_plan.get("source_ids"), list) else None,
        query=str(run_plan.get("query") or "") or None,
        live_scope=str(run_plan.get("live_scope") or "bounded"),
        include_step_sources=bool(run_plan.get("include_step_sources", False)),
        max_step_sources=normalize_max_step_sources(run_plan.get("max_step_sources", DEFAULT_MAX_STEP_SOURCES)),
        step_source_timeout=normalize_step_source_timeout(run_plan.get("step_source_timeout", DEFAULT_STEP_SOURCE_TIMEOUT)),
        allow_network=True,
        stepik_token_env=str(run_plan.get("stepik_token_env") or "STEPIK_API_TOKEN"),
        browser_state_file=browser_state_file,
        expect_origin_contains=str(run_plan.get("expect_origin_contains") or "") or None,
        max_lessons=int(run_plan.get("max_lessons") or 50),
        max_pages=int(run_plan.get("max_pages") or 5),
        max_sources=int(run_plan.get("max_sources") or 50),
        link_pattern=str(run_plan.get("link_pattern") or "") or None,
    )
    _emit(
        {
            "schema": "aoa_course_connection_profile_run_receipt_v1",
            "status": receipt.get("status") or "error",
            "network_touched": True,
            "executed": True,
            "profile": inspection.get("profile"),
            "run_plan": run_plan,
            "connected_run": receipt,
        }
    )
    return 0 if receipt.get("status") == "ok" else 1


def cmd_preflight_live(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    report = live_preflight(
        roots,
        platforms=args.platform,
        source_ids=args.source_id,
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
        source_ids=args.source_id,
        stepik_token_env=args.stepik_token_env,
        browser_state_file=args.state_file,
        expect_origin_contains=args.expect_origin,
        include_disabled=args.include_disabled,
        query=args.query,
        max_lessons=args.max_lessons,
        max_pages=args.max_pages,
        max_sources=args.max_sources,
        link_pattern=args.link_pattern,
        calibration_run=args.calibration_run,
        live_scope=args.live_scope,
        include_step_sources=args.include_step_sources,
        max_step_sources=args.max_step_sources,
        step_source_timeout=args.step_source_timeout,
    )
    _emit(plan)
    return 0 if bool(plan.get("ready")) or not args.require_ready else 1


def cmd_preflight_semantic_provider(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    report = semantic_provider_preflight(
        roots,
        run_id=args.run,
        provider=args.provider,
        dimensions=args.dimensions,
        embedding_endpoint=args.embedding_endpoint,
        embedding_model=args.embedding_model,
        embedding_token_env=args.embedding_token_env,
        embedding_batch_size=args.embedding_batch_size,
        embedding_timeout_seconds=args.embedding_timeout_seconds,
    )
    _emit(report)
    return 0 if bool(report.get("ready")) or not args.require_ready else 1


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


def cmd_sources_list(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    registry = load_registry(roots.data)
    catalog = source_registry_catalog(
        roots,
        registry,
        include_disabled=args.include_disabled,
        platforms=args.platform,
        source_ids=args.source_id,
        include_source_refs=args.include_source_refs,
        include_connected_runs=args.include_connected_runs,
        connected_run_limit=max(1, args.connected_run_limit),
        connected_receipt_limit=max(1, args.connected_receipt_limit),
    )
    _emit(catalog)
    return 0


def cmd_sources_answer(args: argparse.Namespace) -> int:
    try:
        result = call_tool(
            "sources_answer",
            {
                "query": args.query,
                "platforms": args.platform,
                "source_ids": args.source_id,
                "kinds": args.kind,
                "limit": args.limit,
                "mode": args.mode,
                "graph_limit": args.graph_limit,
                "source_limit": args.source_limit,
                "connected_run_limit": args.connected_run_limit,
                "connected_receipt_limit": args.connected_receipt_limit,
                "include_disabled": args.include_disabled,
                "include_source_refs": args.include_source_refs,
            },
        )
    except ValueError as exc:
        _emit({"schema": "aoa_course_sources_answer_cli_v1", "status": "error", "error": str(exc), "network_touched": False})
        return 2
    packet = result.get("sources_answer") if isinstance(result.get("sources_answer"), dict) else {}
    _emit(packet)
    return 0 if packet.get("status") in {"ok", "partial"} else 1


def cmd_sources_answer_matrix(args: argparse.Namespace) -> int:
    try:
        result = call_tool(
            "sources_answer_matrix",
            {
                "queries": args.query,
                "platforms": args.platform,
                "source_ids": args.source_id,
                "kinds": args.kind,
                "limit": args.limit,
                "mode": args.mode,
                "coverage_mode": args.coverage_mode,
                "graph_limit": args.graph_limit,
                "source_limit": args.source_limit,
                "connected_run_limit": args.connected_run_limit,
                "connected_receipt_limit": args.connected_receipt_limit,
                "include_disabled": args.include_disabled,
                "include_source_refs": args.include_source_refs,
            },
        )
    except ValueError as exc:
        _emit({"schema": "aoa_course_sources_answer_matrix_cli_v1", "status": "error", "error": str(exc), "network_touched": False})
        return 2
    packet = result.get("sources_answer_matrix") if isinstance(result.get("sources_answer_matrix"), dict) else {}
    _emit(packet)
    return 0 if packet.get("status") in {"ok", "partial"} else 1


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
            expect_origin_contains=args.expect_origin_contains,
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


def cmd_auth_import_firefox_state(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    create_storage_roots(roots)
    try:
        receipt = import_firefox_browser_state(
            roots.auth,
            args.platform,
            args.source_ref,
            state_file=args.state_file,
            profile_dir=args.profile_dir,
            profile_name=args.profile_name,
            profiles_ini=args.profiles_ini,
            expect_origin_contains=args.expect_origin_contains,
        )
    except Exception as exc:
        state_file = args.state_file or default_browser_state_path(roots.auth, args.platform, args.source_ref)
        _emit({
            "schema": "aoa_course_firefox_state_import_receipt_v1",
            "status": "error",
            "platform": args.platform,
            "source_ref": args.source_ref,
            "state_file": str(state_file),
            "error": str(exc),
            "network_touched": False,
            "privacy": {
                "cookie_values_logged": False,
                "local_storage_values_logged": False,
                "token_values_logged": False,
            },
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
    status = inspect_browser_state(state_file, expect_origin_contains=args.expect_origin_contains, platform=args.platform)
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
            access_mode = args.access_mode or "api_token"
            receipt = discover_stepik_account_fixture_route(
                roots,
                run_id=args.run,
                fixture=args.fixture,
                register=args.register,
                access_mode=access_mode,
                source_limit=args.source_limit,
            )
        elif args.state_file:
            access_mode = args.access_mode or "browser_session"
            receipt = discover_stepik_account_browser_state_route(
                roots,
                run_id=args.run,
                state_file=args.state_file,
                max_pages=args.max_pages,
                batch_size=args.batch_size,
                register=args.register,
                access_mode=access_mode,
                source_limit=args.source_limit,
            )
        else:
            access_mode = args.access_mode or "api_token"
            receipt = discover_stepik_account_live_route(
                roots,
                run_id=args.run,
                token_env=args.token_env,
                max_pages=args.max_pages,
                batch_size=args.batch_size,
                register=args.register,
                access_mode=access_mode,
                source_limit=args.source_limit,
            )
    except Exception as exc:
        _emit({
            "schema": "aoa_course_stepik_account_discovery_receipt_v1",
            "status": "error",
            "run_id": args.run,
            "source_mode": "stepik_account_fixture" if args.from_fixture else "stepik_account_browser_state" if args.state_file else "stepik_account_live",
            "error": str(exc),
            "network_touched": False if args.from_fixture or str(exc).startswith("Stepik account discovery requires token env") or "storage state" in str(exc) else True,
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


def _browser_registry_source(roots: StorageRoots, *, platform: str, source_ref: str, source_id: str | None = None) -> dict[str, object] | None:
    registry = load_registry(roots.data)
    sources = [
        source
        for source in registry.get("sources", [])
        if isinstance(source, dict)
        and source.get("enabled", True)
        and source.get("platform") == platform
        and source.get("access_mode") == "browser_session"
    ]
    if source_id:
        for source in sources:
            if str(source.get("source_id") or "") == source_id:
                return source
        raise ValueError(f"browser source id not found in local registry: {source_id}")
    if not source_ref:
        return None
    return next((source for source in sources if str(source.get("source_ref") or "") == source_ref), None)


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
        source = _browser_registry_source(roots, platform=args.platform, source_ref=args.url, source_id=args.source_id)
        receipt = capture_browser_live(roots, url=args.url, platform=args.platform, run_id=run_id, state_file=args.state_file, wait_until=args.wait_until, source=source)
    except (RuntimeError, ValueError) as exc:
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
        source = _browser_registry_source(roots, platform=args.platform, source_ref=args.url, source_id=args.source_id)
        receipt = crawl_browser_live(
            roots,
            url=args.url,
            platform=args.platform,
            run_id=run_id,
            state_file=args.state_file,
            wait_until=args.wait_until,
            max_lessons=args.max_lessons,
            link_pattern=args.link_pattern,
            source=source,
        )
    except (RuntimeError, ValueError) as exc:
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
        source_ids=args.source_id,
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
        source_ids=args.source_id,
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
        source_ids=args.source_id,
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
        state_file=args.state_file,
        max_sections=max_sections,
        max_units_per_section=max_units,
        max_steps_per_lesson=max_steps,
        batch_size=args.batch_size,
        include_step_sources=args.include_step_sources,
        max_step_sources=args.max_step_sources,
        step_source_timeout=args.step_source_timeout,
        source_ids=args.source_id,
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
        source = _browser_registry_source(roots, platform=args.platform, source_ref=args.course_url or "", source_id=args.source_id)
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
            source=source,
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
        state_file=args.state_file,
        max_sections=max_sections,
        max_units_per_section=max_units,
        max_steps_per_lesson=max_steps,
        batch_size=args.batch_size,
        include_step_sources=args.include_step_sources,
        max_step_sources=args.max_step_sources,
        step_source_timeout=args.step_source_timeout,
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


def cmd_calibration_intake(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    packet = load_json_report(args.packet)
    intake = build_live_calibration_intake(packet=packet, run_id=args.run)
    intake_path = write_live_calibration_intake(roots, intake, run_id=args.run)
    _emit({**intake, "intake_path": str(intake_path)})
    return 0


def cmd_calibration_connected_run(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    try:
        receipt = run_connected_calibration(
            roots,
            run_id=args.run,
            mode=args.mode,
            platforms=args.platform,
            source_ids=args.source_id,
            query=args.query,
            live_scope=args.live_scope,
            include_step_sources=args.include_step_sources,
            max_step_sources=args.max_step_sources,
            step_source_timeout=args.step_source_timeout,
            allow_network=args.allow_network,
            stepik_token_env=args.stepik_token_env,
            browser_state_file=args.state_file,
            expect_origin_contains=args.expect_origin,
            max_lessons=args.max_lessons,
            max_pages=args.max_pages,
            max_sources=args.max_sources,
            link_pattern=args.link_pattern,
            source_limit=args.source_limit,
        )
    except ValueError as exc:
        _emit({"schema": "aoa_course_connected_calibration_run_receipt_v1", "status": "error", "error": str(exc), "network_touched": False})
        return 2
    _emit(receipt)
    return 0 if receipt.get("status") == "ok" else 1


def cmd_calibration_status(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    status = load_connected_calibration_status(roots, run_id=args.run)
    _emit(status)
    return 0 if status.get("status") not in {"missing", "error"} else 1


def cmd_calibration_query(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    packet = query_connected_calibration(
        roots,
        run_id=args.run,
        query=args.query,
        platforms=args.platform,
        source_ids=args.source_id,
        kinds=args.kind,
        limit=args.limit,
        mode=args.mode,
        graph_limit=args.graph_limit,
        entry_limit=args.entry_limit,
    )
    _emit(packet)
    return 0 if packet.get("status") in {"ok", "partial"} else 1


def cmd_calibration_query_matrix(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    packet = query_connected_calibration_matrix(
        roots,
        run_id=args.run,
        queries=args.query,
        platforms=args.platform,
        source_ids=args.source_id,
        kinds=args.kind,
        limit=args.limit,
        mode=args.mode,
        graph_limit=args.graph_limit,
        entry_limit=args.entry_limit,
    )
    _emit(packet)
    return 0 if packet.get("status") in {"ok", "partial"} else 1


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
        state_file=args.state_file,
        max_sections=max_sections,
        max_units_per_section=max_units,
        max_steps_per_lesson=max_steps,
        batch_size=args.batch_size,
        include_step_sources=args.include_step_sources,
        max_step_sources=args.max_step_sources,
        step_source_timeout=args.step_source_timeout,
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
    path = build_semantic_index(
        roots,
        run_id=args.run,
        dimensions=args.dimensions,
        provider=args.provider,
        embedding_endpoint=args.embedding_endpoint,
        embedding_model=args.embedding_model,
        embedding_token_env=args.embedding_token_env,
        embedding_batch_size=args.embedding_batch_size,
        embedding_timeout_seconds=args.embedding_timeout_seconds,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    _emit(
        {
            "schema": "aoa_course_build_semantic_index_receipt_v1",
            "status": "ok",
            "run_id": args.run,
            "semantic_index_path": str(path),
            "provider": payload.get("provider"),
            "dimensions": payload.get("dimensions"),
            "provider_config": payload.get("provider_config"),
        }
    )
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


def cmd_lesson_context(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    _emit(render_lesson_context_packet(roots, args.query, args.run, args.limit, args.mode, args.graph_limit))
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
            "refresh_report": packet["refresh_report"],
        }
    )
    return 0


def cmd_inspect_browser_snapshot(args: argparse.Namespace) -> int:
    report = audit_browser_snapshot_file(
        args.snapshot,
        platform=args.platform,
        max_sources=args.max_sources,
        max_lessons=args.max_lessons,
        link_pattern=args.link_pattern,
    )
    _emit(report)
    ready = bool(report.get("readiness", {}).get("ready_for_discovery")) or bool(
        report.get("readiness", {}).get("ready_for_materialize")
    )
    return 0 if ready or not args.require_ready else 1


def cmd_refresh_query(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    try:
        report = refresh_query_cycle(
            roots,
            args.query,
            run_id=args.run,
            mode=args.mode,
            limit=args.limit,
            strategy=args.strategy,
            execute=args.execute,
            source_id=args.source_id,
            sync_run_id=args.sync_run,
            allow_network=args.allow_network,
            state_file=args.state_file,
            stepik_token_env=args.stepik_token_env,
            max_lessons=args.max_lessons,
            max_sections=args.max_sections,
            max_units_per_section=args.max_units_per_section,
            max_steps_per_lesson=args.max_steps_per_lesson,
            batch_size=args.batch_size,
            include_step_sources=args.include_step_sources,
        )
    except ValueError as exc:
        _emit({"schema": "aoa_course_refresh_cycle_v1", "status": "error", "error": str(exc), "network_touched": False})
        return 2
    _emit(report)
    return 0 if report.get("status") in {"ok", "planned"} else 1


def cmd_eval_install_route(_args: argparse.Namespace) -> int:
    repo_root = find_repo_root()
    roots = StorageRoots.from_env(repo_root)
    tools = {str(tool.get("name")) for tool in tools_manifest().get("tools", []) if isinstance(tool, dict)}
    connected_run = "connected-calibration"
    bootstrap = bootstrap_fixture(
        repo_root,
        roots,
        run_id=DEFAULT_RUN,
        connected_run=connected_run,
        mcp_tool_names=tools,
    )
    storage = storage_status(repo_root, roots)
    readiness = connector_readiness(
        repo_root,
        roots,
        runs=[DEFAULT_RUN],
        connected_run=connected_run,
        mcp_tool_names=tools,
    )
    answer_packet = render_answer_packet(roots, "bootloader rollback", DEFAULT_RUN, 5, "hybrid")
    mcp_answer = call_tool("answer", {"query": "bootloader rollback", "run": DEFAULT_RUN, "mode": "hybrid"})
    mcp_readiness = call_tool("connector_readiness", {"runs": [DEFAULT_RUN], "connected_run": connected_run})
    connected_status = load_connected_calibration_status(roots, run_id=connected_run)
    sources = call_tool("list_sources", {})
    sources_answer = call_tool(
        "sources_answer",
        {"platforms": ["stepik"], "query": "Stepik public API evidence", "mode": "hybrid"},
    )
    sources_answer_matrix = call_tool(
        "sources_answer_matrix",
        {
            "platforms": ["stepik"],
            "queries": ["Stepik public API evidence", "canonical course objects"],
            "mode": "hybrid",
        },
    )
    doc_paths = [
        "README.md",
        "docs/INSTALL.md",
        "docs/AGENT_INSTALL_ROUTE.md",
        "docs/CLI_USAGE.md",
        "docs/MCP_USAGE.md",
        "docs/STORAGE_CONTRACT.md",
        "docs/AUTH_SESSION.md",
        "docs/STATUS.md",
    ]
    failures = _install_route_failures(
        repo_root=repo_root,
        doc_paths=doc_paths,
        storage=storage,
        bootstrap=bootstrap,
        readiness=readiness,
        answer_packet=answer_packet,
        mcp_answer=mcp_answer,
        mcp_readiness=mcp_readiness,
        connected_status=connected_status,
        sources=sources,
        sources_answer=sources_answer,
        sources_answer_matrix=sources_answer_matrix,
    )
    query_plan_ready_count = _ready_query_entry_count(connected_status)
    source_count = _source_registry_count(sources)
    mcp_answer_packet = mcp_answer.get("answer_packet") if isinstance(mcp_answer.get("answer_packet"), dict) else {}
    mcp_answer_quality = mcp_answer_packet.get("quality") if isinstance(mcp_answer_packet.get("quality"), dict) else {}
    _emit(
        {
            "schema": "aoa_course_eval_install_route_v1",
            "status": "ok" if not failures else "error",
            "network_touched": False,
            "run_id": DEFAULT_RUN,
            "connected_run": connected_run,
            "proof_commands": [
                "aoa-course doctor",
                f"aoa-course bootstrap fixture --run {DEFAULT_RUN} --connected-run {connected_run}",
                f"aoa-course readiness --run {DEFAULT_RUN} --connected-run {connected_run}",
                f'aoa-course answer "bootloader rollback" --run {DEFAULT_RUN} --mode hybrid',
                'aoa-course sources answer "Stepik public API evidence" --platform stepik --mode hybrid',
                'aoa-course sources answer-matrix --query "Stepik public API evidence" --query "canonical course objects" --platform stepik --mode hybrid',
                f'aoa-course mcp call answer \'{{"query":"bootloader rollback","run":"{DEFAULT_RUN}","mode":"hybrid"}}\'',
                'aoa-course mcp call sources_answer \'{"platforms":["stepik"],"query":"Stepik public API evidence","mode":"hybrid"}\'',
                'aoa-course mcp call sources_answer_matrix \'{"platforms":["stepik"],"queries":["Stepik public API evidence","canonical course objects"],"mode":"hybrid"}\'',
                f"aoa-course calibration status --run {connected_run}",
            ],
            "storage": {
                "mode": storage.get("mode"),
                "exists": storage.get("exists"),
                "git_private": storage.get("git_private"),
            },
            "docs": {"checked": doc_paths, "missing": [path for path in doc_paths if not (repo_root / path).exists()]},
            "bootstrap": {
                "status": bootstrap.get("status"),
                "network_touched": bootstrap.get("network_touched"),
                "connected_status": (bootstrap.get("connected_receipt") if isinstance(bootstrap.get("connected_receipt"), dict) else {}).get("status"),
            },
            "readiness": {
                "status": readiness.get("status"),
                "operational_ready": readiness.get("operational_ready"),
                "connected_live_ready": readiness.get("connected_live_ready"),
                "mcp_ready": (readiness.get("mcp") if isinstance(readiness.get("mcp"), dict) else {}).get("ready"),
            },
            "answer": {
                "schema": answer_packet.get("schema"),
                "mode": answer_packet.get("mode"),
                "result_count": answer_packet.get("result_count"),
                "quality_ready": (answer_packet.get("quality") if isinstance(answer_packet.get("quality"), dict) else {}).get("ready"),
                "evidence_count": len(answer_packet.get("evidence_chain", [])) if isinstance(answer_packet.get("evidence_chain"), list) else 0,
            },
            "mcp": {
                "answer_tool": mcp_answer.get("tool"),
                "answer_quality_ready": mcp_answer_quality.get("ready"),
                "readiness_operational_ready": mcp_readiness.get("operational_ready"),
            },
            "connected_status": {
                "status": connected_status.get("status"),
                "network_touched": connected_status.get("network_touched"),
                "query_plan_ready_count": query_plan_ready_count,
            },
            "source_registry": {"source_count": source_count},
            "sources_answer": _sources_answer_summary(sources_answer),
            "sources_answer_matrix": _sources_answer_matrix_summary(sources_answer_matrix),
            "failures": failures,
        }
    )
    return 0 if not failures else 1


def cmd_eval_source_registry_query(args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    catalog = source_registry_catalog(
        roots,
        load_registry(roots.data),
        include_disabled=args.include_disabled,
        platforms=args.platform,
        source_ids=args.source_id,
        include_source_refs=False,
        include_connected_runs=True,
        connected_run_limit=max(1, args.connected_run_limit),
        connected_receipt_limit=max(1, args.connected_receipt_limit),
    )
    queries = _dedupe_cli_values(args.query or []) or _source_registry_query_samples(
        catalog,
        limit=max(1, args.query_sample_limit),
    )
    matrix_result: dict[str, object] = {}
    matrix_packet: dict[str, object] = {}
    semantic_failures = _source_registry_external_semantic_provider_failures(catalog, args.mode)
    if queries and not semantic_failures:
        matrix_result = call_tool(
            "sources_answer_matrix",
            {
                "queries": queries,
                "platforms": args.platform,
                "source_ids": args.source_id,
                "kinds": args.kind,
                "limit": args.limit,
                "mode": args.mode,
                "coverage_mode": args.coverage_mode,
                "graph_limit": args.graph_limit,
                "source_limit": args.source_limit,
                "connected_run_limit": args.connected_run_limit,
                "connected_receipt_limit": args.connected_receipt_limit,
                "include_disabled": args.include_disabled,
                "include_source_refs": False,
            },
        )
        matrix_packet = matrix_result.get("sources_answer_matrix") if isinstance(matrix_result.get("sources_answer_matrix"), dict) else {}
    failures = semantic_failures or _source_registry_query_eval_failures(
        catalog=catalog,
        queries=queries,
        matrix_packet=matrix_packet,
        min_query_count=max(1, args.min_query_count),
        min_ready_query_count=args.min_ready_query_count,
        min_response_count=max(1, args.min_response_count),
        min_evidence_count=max(1, args.min_evidence_count),
        min_grounded_response_count=max(1, args.min_grounded_response_count),
        min_source_count=max(1, args.min_source_count),
    )
    connected_runs = catalog.get("connected_runs") if isinstance(catalog.get("connected_runs"), dict) else {}
    summary = _sources_answer_matrix_summary(matrix_result)
    next_commands = [
        "aoa-course sources list --no-source-refs --connected-run-limit 5",
    ]
    next_commands.extend([str(failure.get("next_command")) for failure in semantic_failures if str(failure.get("next_command") or "")])
    next_commands.extend([str(command) for command in matrix_packet.get("next_commands", []) if str(command)] if isinstance(matrix_packet.get("next_commands"), list) else [])
    if not queries:
        next_commands.append("aoa-course preflight connected-plan --live-scope bounded")
    _emit(
        {
            "schema": "aoa_course_eval_source_registry_query_v1",
            "suite_id": "source-registry-query",
            "status": "ok" if not failures else "error",
            "network_touched": False,
            "read_only": True,
            "selection": {
                "platforms": args.platform or [],
                "source_ids": args.source_id or [],
                "kinds": args.kind or [],
                "coverage_mode": args.coverage_mode,
                "source_limit": args.source_limit,
                "connected_run_limit": args.connected_run_limit,
                "connected_receipt_limit": args.connected_receipt_limit,
            },
            "thresholds": {
                "min_query_count": max(1, args.min_query_count),
                "min_ready_query_count": args.min_ready_query_count or max(1, args.min_query_count),
                "min_response_count": max(1, args.min_response_count),
                "min_evidence_count": max(1, args.min_evidence_count),
                "min_grounded_response_count": max(1, args.min_grounded_response_count),
                "min_source_count": max(1, args.min_source_count),
            },
            "source_registry": {
                "path": catalog.get("path"),
                "source_count": catalog.get("source_count"),
                "enabled_source_count": catalog.get("enabled_source_count"),
                "selected_source_count": catalog.get("selected_source_count"),
                "platform_counts": catalog.get("platform_counts", {}),
                "access_mode_counts": catalog.get("access_mode_counts", {}),
                "missing_source_ids": catalog.get("missing_source_ids", []),
            },
            "connected_runs": {
                "included": connected_runs.get("included"),
                "receipt_count": connected_runs.get("receipt_count"),
                "query_ready_entry_count": connected_runs.get("query_ready_entry_count"),
                "answer_ready_entry_count": connected_runs.get("answer_ready_entry_count"),
                "answer_probe_missing_entry_count": connected_runs.get("answer_probe_missing_entry_count"),
                "invalid_answer_ready_entry_count": connected_runs.get("invalid_answer_ready_entry_count"),
                "source_ids_with_query_runs": connected_runs.get("source_ids_with_query_runs", []),
                "error_count": connected_runs.get("error_count"),
            },
            "queries": queries,
            "query_source": "explicit" if args.query else "connected_run_samples",
            "network_blocked": bool(semantic_failures),
            "sources_answer_matrix": summary,
            "query_summaries": matrix_packet.get("query_summaries", []) if isinstance(matrix_packet.get("query_summaries"), list) else [],
            "failures": failures,
            "next_commands": _dedupe_cli_values(next_commands),
        }
    )
    return 0 if not failures else 1


def _dedupe_cli_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _source_registry_query_samples(catalog: dict[str, object], *, limit: int) -> list[str]:
    queries: list[str] = []
    sources = catalog.get("sources") if isinstance(catalog.get("sources"), list) else []
    for source in sources:
        if not isinstance(source, dict):
            continue
        entries = source.get("latest_connected_runs") if isinstance(source.get("latest_connected_runs"), list) else []
        for entry in entries:
            if not isinstance(entry, dict) or not bool(entry.get("query_ready")):
                continue
            query = str(entry.get("query") or "").strip()
            if not query or query.startswith("<") or query in queries:
                continue
            queries.append(query)
            if len(queries) >= limit:
                return queries
    return queries


def _source_registry_external_semantic_provider_failures(catalog: dict[str, object], mode: str) -> list[dict[str, object]]:
    if mode not in {"semantic", "hybrid"}:
        return []
    failures: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    connected_runs = catalog.get("connected_runs") if isinstance(catalog.get("connected_runs"), dict) else {}
    by_source = connected_runs.get("by_source_id") if isinstance(connected_runs.get("by_source_id"), dict) else {}
    for source_id, entries in by_source.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            paths = entry.get("paths") if isinstance(entry.get("paths"), dict) else {}
            semantic_path = str(paths.get("semantic_index") or "")
            provider = _semantic_index_provider(semantic_path)
            if not semantic_path or not provider or provider == LOCAL_HASHING_PROVIDER:
                continue
            key = (str(source_id), semantic_path)
            if key in seen:
                continue
            seen.add(key)
            run_id = str(entry.get("run_id") or "")
            next_command = "aoa-course build-semantic-index"
            if run_id:
                next_command += f" --run {shlex.quote(run_id)}"
            next_command += f" --provider {LOCAL_HASHING_PROVIDER}"
            failures.append(
                {
                    "surface": "connected_runs",
                    "source_id": str(source_id),
                    "run_id": run_id,
                    "field": "semantic_index.provider",
                    "expected": LOCAL_HASHING_PROVIDER,
                    "actual": provider,
                    "path": semantic_path,
                    "reason": "external_semantic_provider_requires_network",
                    "next_command": next_command,
                }
            )
    return failures


def _semantic_index_provider(path: str) -> str:
    if not path:
        return ""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    provider = str(payload.get("provider") or "")
    provider_config = payload.get("provider_config") if isinstance(payload.get("provider_config"), dict) else {}
    return provider or str(provider_config.get("provider") or "")


def _source_registry_query_eval_failures(
    *,
    catalog: dict[str, object],
    queries: list[str],
    matrix_packet: dict[str, object],
    min_query_count: int,
    min_ready_query_count: int | None,
    min_response_count: int,
    min_evidence_count: int,
    min_grounded_response_count: int,
    min_source_count: int,
) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    selected_source_count = int(catalog.get("selected_source_count") or 0)
    if selected_source_count < min_source_count:
        failures.append(
            {
                "surface": "source_registry",
                "field": "selected_source_count",
                "expected_min": min_source_count,
                "actual": selected_source_count,
            }
        )
    connected_runs = catalog.get("connected_runs") if isinstance(catalog.get("connected_runs"), dict) else {}
    if int(connected_runs.get("query_ready_entry_count") or 0) < min_source_count:
        failures.append(
            {
                "surface": "connected_runs",
                "field": "query_ready_entry_count",
                "expected_min": min_source_count,
                "actual": connected_runs.get("query_ready_entry_count"),
            }
        )
    if int(connected_runs.get("invalid_answer_ready_entry_count") or 0) > 0:
        failures.append(
            {
                "surface": "connected_runs",
                "field": "invalid_answer_ready_entry_count",
                "expected": 0,
                "actual": connected_runs.get("invalid_answer_ready_entry_count"),
            }
        )
    if len(queries) < min_query_count:
        failures.append({"surface": "queries", "field": "query_count", "expected_min": min_query_count, "actual": len(queries)})
    if not matrix_packet:
        failures.append({"surface": "sources_answer_matrix", "missing": "packet"})
        return failures
    if matrix_packet.get("schema") != "aoa_course_sources_answer_matrix_v1":
        failures.append(
            {
                "surface": "sources_answer_matrix",
                "field": "schema",
                "expected": "aoa_course_sources_answer_matrix_v1",
                "actual": matrix_packet.get("schema"),
            }
        )
    if matrix_packet.get("status") != "ok":
        failures.append({"surface": "sources_answer_matrix", "field": "status", "expected": "ok", "actual": matrix_packet.get("status")})
    if matrix_packet.get("network_touched") is not False:
        failures.append(
            {
                "surface": "sources_answer_matrix",
                "field": "network_touched",
                "expected": False,
                "actual": matrix_packet.get("network_touched"),
            }
        )
    if matrix_packet.get("source_refs_included") is not False:
        failures.append(
            {
                "surface": "sources_answer_matrix",
                "field": "source_refs_included",
                "expected": False,
                "actual": matrix_packet.get("source_refs_included"),
            }
        )
    quality = matrix_packet.get("quality") if isinstance(matrix_packet.get("quality"), dict) else {}
    if quality.get("ready") is not True:
        failures.append({"surface": "sources_answer_matrix.quality", "field": "ready", "expected": True, "actual": quality.get("ready")})
    expected_ready_queries = min_ready_query_count or min_query_count
    if int(quality.get("ready_query_count") or 0) < expected_ready_queries:
        failures.append(
            {
                "surface": "sources_answer_matrix.quality",
                "field": "ready_query_count",
                "expected_min": expected_ready_queries,
                "actual": quality.get("ready_query_count"),
            }
        )
    if int(quality.get("response_count_total") or 0) < min_response_count:
        failures.append(
            {
                "surface": "sources_answer_matrix.quality",
                "field": "response_count_total",
                "expected_min": min_response_count,
                "actual": quality.get("response_count_total"),
            }
        )
    if int(quality.get("evidence_count_total") or 0) < min_evidence_count:
        failures.append(
            {
                "surface": "sources_answer_matrix.quality",
                "field": "evidence_count_total",
                "expected_min": min_evidence_count,
                "actual": quality.get("evidence_count_total"),
            }
        )
    if int(quality.get("grounded_response_count_total") or 0) < min_grounded_response_count:
        failures.append(
            {
                "surface": "sources_answer_matrix.quality",
                "field": "grounded_response_count_total",
                "expected_min": min_grounded_response_count,
                "actual": quality.get("grounded_response_count_total"),
            }
        )
    for field in [
        "all_queries_have_grounded_response",
        "all_grounded_responses_have_path",
        "all_grounded_responses_have_fetched_at",
        "all_grounded_responses_have_freshness",
    ]:
        if quality.get(field) is not True:
            failures.append({"surface": "sources_answer_matrix.quality", "field": field, "expected": True, "actual": quality.get(field)})
    if matrix_packet.get("blocked_source_count_total", 0):
        failures.append({"surface": "sources_answer_matrix", "field": "blocked_source_count_total", "expected": 0, "actual": matrix_packet.get("blocked_source_count_total")})
    if matrix_packet.get("failure_count_total", 0):
        failures.append({"surface": "sources_answer_matrix", "field": "failure_count_total", "expected": 0, "actual": matrix_packet.get("failure_count_total")})
    return failures


def _install_route_failures(
    *,
    repo_root: Path,
    doc_paths: list[str],
    storage: dict[str, object],
    bootstrap: dict[str, object],
    readiness: dict[str, object],
    answer_packet: dict[str, object],
    mcp_answer: dict[str, object],
    mcp_readiness: dict[str, object],
    connected_status: dict[str, object],
    sources: dict[str, object],
    sources_answer: dict[str, object],
    sources_answer_matrix: dict[str, object],
) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    missing_docs = [path for path in doc_paths if not (repo_root / path).exists()]
    if missing_docs:
        failures.append({"surface": "docs", "missing": missing_docs})
    exists = storage.get("exists") if isinstance(storage.get("exists"), dict) else {}
    for key in ["data", "cache", "auth", "artifact"]:
        if exists.get(key) is not True:
            failures.append({"surface": "storage", "root": key, "expected": True, "actual": exists.get(key)})
    if storage.get("git_private") is not True:
        failures.append({"surface": "storage", "field": "git_private", "expected": True, "actual": storage.get("git_private")})
    if bootstrap.get("status") != "ok":
        failures.append({"surface": "bootstrap", "field": "status", "expected": "ok", "actual": bootstrap.get("status")})
    if bootstrap.get("network_touched") is not False:
        failures.append({"surface": "bootstrap", "field": "network_touched", "expected": False, "actual": bootstrap.get("network_touched")})
    connected_receipt = bootstrap.get("connected_receipt") if isinstance(bootstrap.get("connected_receipt"), dict) else {}
    if connected_receipt.get("status") != "ok":
        failures.append({"surface": "bootstrap.connected_receipt", "field": "status", "expected": "ok", "actual": connected_receipt.get("status")})
    if readiness.get("operational_ready") is not True:
        failures.append({"surface": "readiness", "field": "operational_ready", "expected": True, "actual": readiness.get("operational_ready")})
    mcp = readiness.get("mcp") if isinstance(readiness.get("mcp"), dict) else {}
    if mcp.get("ready") is not True:
        failures.append({"surface": "readiness.mcp", "field": "ready", "expected": True, "actual": mcp.get("ready"), "missing_tools": mcp.get("missing_tools")})
    runs = readiness.get("runs") if isinstance(readiness.get("runs"), list) else []
    run_ready = (runs[0].get("readiness") if runs and isinstance(runs[0], dict) and isinstance(runs[0].get("readiness"), dict) else {})
    if run_ready.get("agent_query_ready") is not True:
        failures.append({"surface": "readiness.runs[0]", "field": "agent_query_ready", "expected": True, "actual": run_ready.get("agent_query_ready")})
    quality = answer_packet.get("quality") if isinstance(answer_packet.get("quality"), dict) else {}
    if answer_packet.get("schema") != "aoa_course_answer_packet_v1":
        failures.append({"surface": "answer", "field": "schema", "expected": "aoa_course_answer_packet_v1", "actual": answer_packet.get("schema")})
    if answer_packet.get("mode") != "hybrid":
        failures.append({"surface": "answer", "field": "mode", "expected": "hybrid", "actual": answer_packet.get("mode")})
    if int(answer_packet.get("result_count") or 0) < 1:
        failures.append({"surface": "answer", "missing": "results"})
    if quality.get("ready") is not True:
        failures.append({"surface": "answer.quality", "field": "ready", "expected": True, "actual": quality.get("ready"), "blockers": quality.get("blockers")})
    evidence = answer_packet.get("evidence_chain") if isinstance(answer_packet.get("evidence_chain"), list) else []
    if not evidence:
        failures.append({"surface": "answer", "missing": "evidence_chain"})
    mcp_packet = mcp_answer.get("answer_packet") if isinstance(mcp_answer.get("answer_packet"), dict) else {}
    mcp_quality = mcp_packet.get("quality") if isinstance(mcp_packet.get("quality"), dict) else {}
    if mcp_answer.get("tool") != "answer":
        failures.append({"surface": "mcp.answer", "field": "tool", "expected": "answer", "actual": mcp_answer.get("tool")})
    if mcp_packet.get("schema") != "aoa_course_answer_packet_v1":
        failures.append({"surface": "mcp.answer_packet", "field": "schema", "expected": "aoa_course_answer_packet_v1", "actual": mcp_packet.get("schema")})
    if mcp_quality.get("ready") is not True:
        failures.append({"surface": "mcp.answer_packet.quality", "field": "ready", "expected": True, "actual": mcp_quality.get("ready")})
    if mcp_readiness.get("operational_ready") is not True:
        failures.append({"surface": "mcp.connector_readiness", "field": "operational_ready", "expected": True, "actual": mcp_readiness.get("operational_ready")})
    if connected_status.get("status") != "ok":
        failures.append({"surface": "connected_status", "field": "status", "expected": "ok", "actual": connected_status.get("status")})
    if connected_status.get("network_touched") is not False:
        failures.append({"surface": "connected_status", "field": "network_touched", "expected": False, "actual": connected_status.get("network_touched")})
    if _ready_query_entry_count(connected_status) < 1:
        failures.append({"surface": "connected_status.query_plan", "missing": "ready query entries"})
    if _source_registry_count(sources) < 1:
        failures.append({"surface": "source_registry", "missing": "registered sources"})
    sources_answer_packet = (
        sources_answer.get("sources_answer")
        if isinstance(sources_answer.get("sources_answer"), dict)
        else {}
    )
    sources_answer_quality = (
        sources_answer_packet.get("quality")
        if isinstance(sources_answer_packet.get("quality"), dict)
        else {}
    )
    if sources_answer.get("tool") != "sources_answer":
        failures.append({
            "surface": "mcp.sources_answer",
            "field": "tool",
            "expected": "sources_answer",
            "actual": sources_answer.get("tool"),
        })
    if sources_answer_packet.get("schema") != "aoa_course_sources_answer_packet_v1":
        failures.append({
            "surface": "sources_answer",
            "field": "schema",
            "expected": "aoa_course_sources_answer_packet_v1",
            "actual": sources_answer_packet.get("schema"),
        })
    if sources_answer_packet.get("status") != "ok":
        failures.append({
            "surface": "sources_answer",
            "field": "status",
            "expected": "ok",
            "actual": sources_answer_packet.get("status"),
        })
    if sources_answer_packet.get("network_touched") is not False:
        failures.append({
            "surface": "sources_answer",
            "field": "network_touched",
            "expected": False,
            "actual": sources_answer_packet.get("network_touched"),
        })
    if int(sources_answer_packet.get("response_count") or 0) < 1:
        failures.append({"surface": "sources_answer", "missing": "responses"})
    if sources_answer_quality.get("ready") is not True:
        failures.append({
            "surface": "sources_answer.quality",
            "field": "ready",
            "expected": True,
            "actual": sources_answer_quality.get("ready"),
        })
    if int(sources_answer_quality.get("evidence_count_total") or 0) < 1:
        failures.append({"surface": "sources_answer.quality", "missing": "evidence"})
    sources_answer_matrix_packet = (
        sources_answer_matrix.get("sources_answer_matrix")
        if isinstance(sources_answer_matrix.get("sources_answer_matrix"), dict)
        else {}
    )
    sources_answer_matrix_quality = (
        sources_answer_matrix_packet.get("quality")
        if isinstance(sources_answer_matrix_packet.get("quality"), dict)
        else {}
    )
    if sources_answer_matrix.get("tool") != "sources_answer_matrix":
        failures.append({
            "surface": "mcp.sources_answer_matrix",
            "field": "tool",
            "expected": "sources_answer_matrix",
            "actual": sources_answer_matrix.get("tool"),
        })
    if sources_answer_matrix_packet.get("schema") != "aoa_course_sources_answer_matrix_v1":
        failures.append({
            "surface": "sources_answer_matrix",
            "field": "schema",
            "expected": "aoa_course_sources_answer_matrix_v1",
            "actual": sources_answer_matrix_packet.get("schema"),
        })
    if sources_answer_matrix_packet.get("status") != "ok":
        failures.append({
            "surface": "sources_answer_matrix",
            "field": "status",
            "expected": "ok",
            "actual": sources_answer_matrix_packet.get("status"),
        })
    if sources_answer_matrix_packet.get("network_touched") is not False:
        failures.append({
            "surface": "sources_answer_matrix",
            "field": "network_touched",
            "expected": False,
            "actual": sources_answer_matrix_packet.get("network_touched"),
        })
    if int(sources_answer_matrix_packet.get("query_count") or 0) < 2:
        failures.append({"surface": "sources_answer_matrix", "missing": "query breadth"})
    if sources_answer_matrix_quality.get("ready") is not True:
        failures.append({
            "surface": "sources_answer_matrix.quality",
            "field": "ready",
            "expected": True,
            "actual": sources_answer_matrix_quality.get("ready"),
        })
    if int(sources_answer_matrix_quality.get("evidence_count_total") or 0) < 2:
        failures.append({"surface": "sources_answer_matrix.quality", "missing": "multi-query evidence"})
    return failures


def _sources_answer_summary(result: dict[str, object]) -> dict[str, object]:
    packet = result.get("sources_answer") if isinstance(result.get("sources_answer"), dict) else {}
    quality = packet.get("quality") if isinstance(packet.get("quality"), dict) else {}
    return {
        "tool": result.get("tool"),
        "schema": packet.get("schema"),
        "status": packet.get("status"),
        "network_touched": packet.get("network_touched"),
        "response_count": packet.get("response_count"),
        "quality_ready": quality.get("ready"),
        "evidence_count_total": quality.get("evidence_count_total"),
        "source_refs_included": packet.get("source_refs_included"),
    }


def _sources_answer_matrix_summary(result: dict[str, object]) -> dict[str, object]:
    packet = result.get("sources_answer_matrix") if isinstance(result.get("sources_answer_matrix"), dict) else {}
    quality = packet.get("quality") if isinstance(packet.get("quality"), dict) else {}
    return {
        "tool": result.get("tool"),
        "schema": packet.get("schema"),
        "status": packet.get("status"),
        "network_touched": packet.get("network_touched"),
        "coverage_mode": packet.get("coverage_mode"),
        "query_count": packet.get("query_count"),
        "quality_ready": quality.get("ready"),
        "ready_query_count": quality.get("ready_query_count"),
        "source_scoped_ready": quality.get("source_scoped_ready"),
        "portfolio_ready": quality.get("portfolio_ready"),
        "response_count_total": quality.get("response_count_total"),
        "evidence_count_total": quality.get("evidence_count_total"),
        "grounded_response_count_total": quality.get("grounded_response_count_total"),
        "all_queries_have_grounded_response": quality.get("all_queries_have_grounded_response"),
        "all_grounded_responses_have_path": quality.get("all_grounded_responses_have_path"),
        "all_grounded_responses_have_fetched_at": quality.get("all_grounded_responses_have_fetched_at"),
        "all_grounded_responses_have_freshness": quality.get("all_grounded_responses_have_freshness"),
        "source_refs_included": packet.get("source_refs_included"),
    }


def _ready_query_entry_count(status: dict[str, object]) -> int:
    query_plan = status.get("query_plan") if isinstance(status.get("query_plan"), dict) else {}
    if "ready_entry_count" in query_plan:
        return int(query_plan.get("ready_entry_count") or 0)
    entries = query_plan.get("entries") if isinstance(query_plan.get("entries"), list) else []
    return len([entry for entry in entries if isinstance(entry, dict) and entry.get("query_ready") is True])


def _source_registry_count(sources: dict[str, object]) -> int:
    registry = sources.get("registry") if isinstance(sources.get("registry"), dict) else {}
    registry_sources = registry.get("sources") if isinstance(registry.get("sources"), list) else []
    return len(registry_sources)


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
                "quality_ready": (packet.get("quality") if isinstance(packet.get("quality"), dict) else {}).get("ready"),
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


def cmd_eval_retrieval_loop(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    suite_path = find_repo_root() / "evals" / "suites" / "retrieval_loop.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    prepared_runs: set[str] = set()
    failures = []
    case_results = []
    for case in suite.get("cases", []):
        if not isinstance(case, dict):
            continue
        run_id = str(case.get("run") or DEFAULT_RUN)
        if run_id not in prepared_runs:
            _prepare_retrieval_loop_run(roots, case)
            prepared_runs.add(run_id)
        packet = _retrieval_loop_packet(roots, case)
        case_failures = _retrieval_loop_failures(packet, case)
        case_results.append(
            {
                "case_id": case.get("case_id"),
                "run": run_id,
                "query": case.get("query"),
                "mode": case.get("mode") or "keyword",
                "answer_result_count": packet["answer_packet"].get("result_count"),
                "mcp_search_result_count": len(packet["mcp_search"].get("results", [])) if isinstance(packet["mcp_search"].get("results"), list) else 0,
                "lesson_graph_status": packet["lesson_context"].get("graph_context", {}).get("status") if isinstance(packet["lesson_context"].get("graph_context"), dict) else "",
                "failure_count": len(case_failures),
            }
        )
        failures.extend(case_failures)
    _emit(
        {
            "schema": "aoa_course_eval_retrieval_loop_v1",
            "suite_id": suite.get("suite_id"),
            "status": "ok" if not failures else "error",
            "network_touched": False,
            "prepared_runs": sorted(prepared_runs),
            "case_results": case_results,
            "failures": failures,
        }
    )
    return 0 if not failures else 1


def _prepare_retrieval_loop_run(roots: StorageRoots, case: dict[str, object]) -> None:
    run_id = str(case.get("run") or DEFAULT_RUN)
    prepare = case.get("prepare") if isinstance(case.get("prepare"), dict) else {}
    kind = str(prepare.get("kind") or "starter_fixture")
    if kind == "starter_fixture":
        materialize_fixture(roots, run_id=run_id)
    elif kind == "browser_fixture":
        materialize_browser_fixture(roots, str(prepare.get("platform") or case.get("expected_top_platform") or ""), run_id=run_id)
    elif kind == "stepik_fixture":
        materialize_stepik_fixture(roots, run_id=run_id)
    else:
        raise ValueError(f"unknown retrieval-loop prepare kind: {kind}")
    build_keyword_index(roots, run_id=run_id)
    build_semantic_index(roots, run_id=run_id)
    build_graph(roots, run_id=run_id)


def _retrieval_loop_packet(roots: StorageRoots, case: dict[str, object]) -> dict[str, object]:
    run_id = str(case.get("run") or DEFAULT_RUN)
    query = str(case.get("query") or "")
    mode = str(case.get("mode") or "keyword")
    limit = int(case.get("limit") or 5)
    graph_limit = int(case.get("graph_limit") or 12)
    answer_packet = render_answer_packet(roots, query, run_id, limit, mode)
    lesson_context = render_lesson_context_packet(roots, query, run_id, limit, mode, graph_limit)
    mcp_search = call_tool("search", {"query": query, "run": run_id, "limit": limit, "mode": mode})
    mcp_lesson_context = call_tool("lesson_context", {"query": query, "run": run_id, "limit": limit, "mode": mode, "graph_limit": graph_limit})
    mcp_evidence = call_tool("evidence_report", {"query": query, "run": run_id, "limit": limit, "mode": mode})
    return {
        "answer_packet": answer_packet,
        "lesson_context": lesson_context,
        "mcp_search": mcp_search,
        "mcp_lesson_context": mcp_lesson_context,
        "mcp_evidence": mcp_evidence,
    }


def _retrieval_loop_failures(packet: dict[str, object], case: dict[str, object]) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    context = {"case_id": case.get("case_id"), "run": case.get("run") or DEFAULT_RUN, "query": case.get("query"), "mode": case.get("mode") or "keyword"}
    answer_packet = packet["answer_packet"] if isinstance(packet.get("answer_packet"), dict) else {}
    results = answer_packet.get("results") if isinstance(answer_packet.get("results"), list) else []
    evidence_chain = answer_packet.get("evidence_chain") if isinstance(answer_packet.get("evidence_chain"), list) else []
    min_results = int(case.get("min_results") or 1)
    if len(results) < min_results:
        failures.append({**context, "surface": "answer_packet", "missing": "minimum results", "expected": min_results, "actual": len(results)})
        return failures
    top = results[0] if isinstance(results[0], dict) else {}
    for key, field in [
        ("expected_top_kind", "kind"),
        ("expected_top_platform", "platform"),
        ("expected_top_source_id", "source_id"),
    ]:
        expected = case.get(key)
        if expected is not None and str(top.get(field) or "") != str(expected):
            failures.append({**context, "surface": "answer_packet", "field": field, "expected": expected, "actual": top.get(field)})
    for term in _list_of_strings(case.get("expected_top_snippet_terms")):
        if term.casefold() not in str(top.get("snippet") or "").casefold():
            failures.append({**context, "surface": "answer_packet", "missing_top_snippet_term": term, "top_doc_id": top.get("doc_id")})
    failures.extend(_proof_field_failures(context, "answer_packet", evidence_chain, case))
    refresh_report = answer_packet.get("refresh_report") if isinstance(answer_packet.get("refresh_report"), dict) else {}
    local_query_commands = [str(command) for command in refresh_report.get("local_query_commands", [])] if isinstance(refresh_report.get("local_query_commands"), list) else []
    if not any("lesson-context" in command for command in local_query_commands):
        failures.append({**context, "surface": "answer_packet.refresh_report", "missing": "lesson-context local query command"})
    if not any("evidence inspect" in command for command in local_query_commands):
        failures.append({**context, "surface": "answer_packet.refresh_report", "missing": "evidence inspect local query command"})

    lesson_context = packet["lesson_context"] if isinstance(packet.get("lesson_context"), dict) else {}
    graph_context = lesson_context.get("graph_context") if isinstance(lesson_context.get("graph_context"), dict) else {}
    failures.extend(_graph_context_failures(context, "lesson_context", graph_context, case))

    mcp_search = packet["mcp_search"] if isinstance(packet.get("mcp_search"), dict) else {}
    mcp_results = mcp_search.get("results") if isinstance(mcp_search.get("results"), list) else []
    if len(mcp_results) < min_results:
        failures.append({**context, "surface": "mcp.search", "missing": "minimum results", "expected": min_results, "actual": len(mcp_results)})

    mcp_lesson = packet["mcp_lesson_context"] if isinstance(packet.get("mcp_lesson_context"), dict) else {}
    mcp_answer = mcp_lesson.get("answer_packet") if isinstance(mcp_lesson.get("answer_packet"), dict) else {}
    if int(mcp_answer.get("result_count") or 0) < min_results:
        failures.append({**context, "surface": "mcp.lesson_context", "missing": "answer results", "expected": min_results, "actual": mcp_answer.get("result_count")})
    mcp_graph = mcp_lesson.get("graph_context") if isinstance(mcp_lesson.get("graph_context"), dict) else {}
    failures.extend(_graph_context_failures(context, "mcp.lesson_context", mcp_graph, case))

    mcp_evidence = packet["mcp_evidence"] if isinstance(packet.get("mcp_evidence"), dict) else {}
    mcp_evidence_chain = mcp_evidence.get("evidence_chain") if isinstance(mcp_evidence.get("evidence_chain"), list) else []
    mcp_result_refs = mcp_evidence.get("result_refs") if isinstance(mcp_evidence.get("result_refs"), list) else []
    failures.extend(_proof_field_failures(context, "mcp.evidence_report", mcp_evidence_chain, case))
    if len(mcp_result_refs) < min_results:
        failures.append({**context, "surface": "mcp.evidence_report", "missing": "result refs", "expected": min_results, "actual": len(mcp_result_refs)})
    return failures


def _proof_field_failures(context: dict[str, object], surface: str, evidence_chain: list[object], case: dict[str, object]) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    if not evidence_chain:
        return [{**context, "surface": surface, "missing": "evidence_chain"}]
    required_fields = _list_of_strings(case.get("required_evidence_fields"))
    for index, evidence in enumerate(evidence_chain):
        if not isinstance(evidence, dict):
            failures.append({**context, "surface": surface, "evidence_index": index, "missing": "object evidence"})
            continue
        for field in required_fields:
            if not evidence.get(field):
                failures.append({**context, "surface": surface, "evidence_index": index, "missing_evidence_field": field})
    return failures


def _graph_context_failures(context: dict[str, object], surface: str, graph_context: dict[str, object], case: dict[str, object]) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    expected_status = str(case.get("expected_graph_status") or "ready")
    if graph_context.get("status") != expected_status:
        failures.append({**context, "surface": surface, "field": "graph_context.status", "expected": expected_status, "actual": graph_context.get("status")})
    contexts = graph_context.get("contexts") if isinstance(graph_context.get("contexts"), list) else []
    min_contexts = int(case.get("min_graph_contexts") or 1)
    if len(contexts) < min_contexts:
        failures.append({**context, "surface": surface, "missing": "graph contexts", "expected": min_contexts, "actual": len(contexts)})
        return failures
    min_neighbors = int(case.get("min_graph_neighbors") or 1)
    for index, item in enumerate(contexts[:min_contexts]):
        graph = item.get("graph") if isinstance(item, dict) and isinstance(item.get("graph"), dict) else {}
        neighbors = graph.get("neighbors") if isinstance(graph.get("neighbors"), list) else []
        if len(neighbors) < min_neighbors:
            failures.append({**context, "surface": surface, "context_index": index, "missing": "graph neighbors", "expected": min_neighbors, "actual": len(neighbors)})
    return failures


def _answer_quality_failures(packet: dict[str, object], case: dict[str, object]) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    context = {"run": case.get("run") or DEFAULT_RUN, "query": case.get("query"), "mode": case.get("mode") or "keyword"}
    results = [item for item in packet.get("results", []) if isinstance(item, dict)] if isinstance(packet.get("results"), list) else []
    evidence_chain = [item for item in packet.get("evidence_chain", []) if isinstance(item, dict)] if isinstance(packet.get("evidence_chain"), list) else []
    min_results = int(case.get("min_results") or 1)
    if len(results) < min_results:
        failures.append({**context, "missing": "minimum results", "expected": min_results, "actual": len(results)})
        return failures
    quality = packet.get("quality") if isinstance(packet.get("quality"), dict) else {}
    if quality.get("schema") != "aoa_course_answer_quality_summary_v1":
        failures.append({**context, "missing": "answer quality summary"})
    elif quality.get("ready") is not True:
        failures.append({**context, "field": "quality.ready", "expected": True, "actual": quality.get("ready"), "blockers": quality.get("blockers", [])})
    elif int(quality.get("result_count") or -1) != len(results):
        failures.append({**context, "field": "quality.result_count", "expected": len(results), "actual": quality.get("result_count")})
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
        metrics = _freshness_ranking_metrics(packet, case)
        case_results.append(
            {
                "query": case.get("query"),
                "run": case.get("run") or DEFAULT_RUN,
                "mode": case.get("mode") or "keyword",
                "result_count": packet.get("result_count"),
                "top_doc_id": results[0].get("doc_id") if results else "",
                "top_rank_score": results[0].get("rank_score") if results else None,
                "metrics": metrics,
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
    query_intent_report = packet.get("query_intent_report") if isinstance(packet.get("query_intent_report"), dict) else {}
    actual_intents = {str(item) for item in query_intent_report.get("intents", [])} if isinstance(query_intent_report.get("intents"), list) else set()
    for intent in _list_of_strings(case.get("expected_query_intents")):
        if intent not in actual_intents:
            failures.append({**context, "missing_query_intent": intent, "actual_intents": sorted(actual_intents)})
    top_rank_features = top.get("rank_features") if isinstance(top.get("rank_features"), dict) else {}
    expected_top_rank_intent = case.get("expected_top_rank_intent")
    if expected_top_rank_intent is not None and str(top_rank_features.get("intent") or "") != str(expected_top_rank_intent):
        failures.append({**context, "field": "top_rank_intent", "expected": expected_top_rank_intent, "actual": top_rank_features.get("intent")})
    expected_intent_class = case.get("expected_intent_class")
    if expected_intent_class is not None and str(query_intent_report.get("intent_class") or "") != str(expected_intent_class):
        failures.append(
            {
                **context,
                "field": "query_intent_report.intent_class",
                "expected": expected_intent_class,
                "actual": query_intent_report.get("intent_class"),
            }
        )
    expected_top_intent_class = case.get("expected_top_intent_class")
    if expected_top_intent_class is not None and str(top_rank_features.get("intent_class") or "") != str(expected_top_intent_class):
        failures.append({**context, "field": "top_rank_intent_class", "expected": expected_top_intent_class, "actual": top_rank_features.get("intent_class")})
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
    if case.get("expect_stale_ranked_above_current"):
        if not current or not stale:
            failures.append({**context, "missing": "current/stale comparison docs", "available_doc_ids": list(by_doc)})
        else:
            current_index = results.index(current)
            stale_index = results.index(stale)
            if stale_index >= current_index:
                failures.append({**context, "expected_order": "stale before current", "actual_order": [item.get("doc_id") for item in results]})
            if float(stale.get("rank_score") or 0.0) <= float(current.get("rank_score") or 0.0):
                failures.append(
                    {
                        **context,
                        "expected": "stale rank_score above current for historical query",
                        "current_rank_score": current.get("rank_score"),
                        "stale_rank_score": stale.get("rank_score"),
                    }
                )
    if case.get("expect_equal_relevance_score") and current and stale and float(current.get("score") or 0.0) != float(stale.get("score") or 0.0):
        failures.append({**context, "expected": "equal base relevance score", "current_score": current.get("score"), "stale_score": stale.get("score")})
    required_rank_features = _list_of_strings(case.get("required_rank_features"))
    for result in results:
        rank_features = result.get("rank_features") if isinstance(result.get("rank_features"), dict) else {}
        for field in required_rank_features:
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
    metrics = _freshness_ranking_metrics(packet, case)
    for threshold_field, metric_field in [
        ("min_latest_at_k", "latest_at_k"),
        ("min_staleness_at_k", "staleness_at_k"),
        ("min_temporal_ndcg", "temporal_ndcg"),
        ("min_source_path_accuracy", "source_path_accuracy"),
        ("min_evidence_attribution", "evidence_attribution"),
        ("min_freshness_coverage", "freshness_coverage"),
    ]:
        if case.get(threshold_field) is not None and float(metrics.get(metric_field) or 0.0) < float(case.get(threshold_field) or 0.0):
            failures.append(
                {
                    **context,
                    "metric": metric_field,
                    "expected_min": case.get(threshold_field),
                    "actual": metrics.get(metric_field),
                }
            )
    if case.get("require_conflict_detection") and not metrics.get("conflict_detected"):
        failures.append({**context, "metric": "conflict_detected", "expected": True, "actual": metrics.get("conflict_detected")})
    return failures


def _freshness_ranking_metrics(packet: dict[str, object], case: dict[str, object]) -> dict[str, object]:
    results = [item for item in packet.get("results", []) if isinstance(item, dict)] if isinstance(packet.get("results"), list) else []
    limit = max(1, int(case.get("limit") or len(results) or 1))
    top_k = results[:limit]
    doc_ids = [str(result.get("doc_id") or "") for result in top_k]
    current_doc_id = str(case.get("current_doc_id") or "")
    stale_doc_id = str(case.get("stale_doc_id") or "")
    current = next((result for result in top_k if str(result.get("doc_id") or "") == current_doc_id), None)
    stale = next((result for result in top_k if str(result.get("doc_id") or "") == stale_doc_id), None)
    evidence_chain = [item for item in packet.get("evidence_chain", []) if isinstance(item, dict)] if isinstance(packet.get("evidence_chain"), list) else []
    required_fields = _list_of_strings(case.get("required_evidence_fields")) or ["evidence_id", "source_url", "path", "fetched_at"]
    evidence_slots = max(1, len(evidence_chain) * max(1, len(required_fields)))
    evidence_hits = sum(1 for evidence in evidence_chain for field in required_fields if evidence.get(field))
    source_path_accuracy = _ratio(sum(1 for result in top_k if _has_source_path(result)), len(top_k))
    freshness_coverage = _ratio(sum(1 for result in top_k if _has_temporal_freshness(result)), len(top_k))
    conflict_detected = False
    if current and stale:
        current_group = str(current.get("version_group_id") or "")
        stale_group = str(stale.get("version_group_id") or "")
        conflict_detected = bool(current_group and current_group == stale_group)
    return {
        "latest_at_k": 1.0 if current_doc_id and current_doc_id in doc_ids else 0.0,
        "staleness_at_k": 1.0 if stale_doc_id and stale_doc_id in doc_ids else 0.0,
        "temporal_ndcg": _temporal_ndcg(top_k, case),
        "source_path_accuracy": source_path_accuracy,
        "evidence_attribution": round(evidence_hits / evidence_slots, 6),
        "freshness_coverage": freshness_coverage,
        "conflict_detected": conflict_detected,
    }


def _has_source_path(result: dict[str, object]) -> bool:
    path = result.get("path")
    return bool(result.get("source_url") and isinstance(path, list) and path)


def _has_temporal_freshness(result: dict[str, object]) -> bool:
    return bool(result.get("freshness_state") and (result.get("observed_at") or result.get("valid_from") or result.get("fetched_at")))


def _temporal_ndcg(results: list[dict[str, object]], case: dict[str, object]) -> float:
    grades = [_temporal_grade(result, case) for result in results]
    dcg = _dcg(grades)
    ideal = _dcg(sorted(grades, reverse=True))
    return round(dcg / ideal, 6) if ideal else 0.0


def _temporal_grade(result: dict[str, object], case: dict[str, object]) -> int:
    doc_id = str(result.get("doc_id") or "")
    current_doc_id = str(case.get("current_doc_id") or "")
    stale_doc_id = str(case.get("stale_doc_id") or "")
    if case.get("expect_stale_ranked_above_current"):
        if doc_id == stale_doc_id:
            return 2
        if doc_id == current_doc_id:
            return 1
        return 0
    if doc_id == current_doc_id:
        return 2
    if doc_id == stale_doc_id:
        return 0
    return 0


def _dcg(grades: list[int]) -> float:
    import math

    return sum(((2**grade) - 1) / math.log2(index + 2) for index, grade in enumerate(grades))


def _ratio(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def cmd_eval_place_ranking(_args: argparse.Namespace) -> int:
    roots = StorageRoots.from_env(find_repo_root())
    suite_path = find_repo_root() / "evals" / "suites" / "place_ranking.json"
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
        case_failures = _place_ranking_failures(packet, case)
        results = [item for item in packet.get("results", []) if isinstance(item, dict)] if isinstance(packet.get("results"), list) else []
        top = results[0] if results else {}
        case_results.append(
            {
                "query": case.get("query"),
                "run": case.get("run") or DEFAULT_RUN,
                "mode": case.get("mode") or "keyword",
                "result_count": packet.get("result_count"),
                "top_doc_id": top.get("doc_id"),
                "top_kind": top.get("kind"),
                "top_path": top.get("path"),
                "top_rank_score": top.get("rank_score"),
                "metrics": _place_ranking_metrics(packet, case),
                "failure_count": len(case_failures),
            }
        )
        failures.extend(case_failures)
    _emit(
        {
            "schema": "aoa_course_eval_place_ranking_v1",
            "suite_id": suite.get("suite_id"),
            "status": "ok" if not failures else "error",
            "case_results": case_results,
            "failures": failures,
        }
    )
    return 0 if not failures else 1


def _place_ranking_failures(packet: dict[str, object], case: dict[str, object]) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    context = {"run": case.get("run") or DEFAULT_RUN, "query": case.get("query"), "mode": case.get("mode") or "keyword"}
    results = [item for item in packet.get("results", []) if isinstance(item, dict)] if isinstance(packet.get("results"), list) else []
    min_results = int(case.get("min_results") or 1)
    if len(results) < min_results:
        return [{**context, "missing": "minimum results", "expected": min_results, "actual": len(results)}]
    top = results[0]
    expected_top_doc_id = case.get("expected_top_doc_id")
    if expected_top_doc_id is not None and str(top.get("doc_id") or "") != str(expected_top_doc_id):
        failures.append({**context, "field": "top_doc_id", "expected": expected_top_doc_id, "actual": top.get("doc_id")})
    expected_top_kind = case.get("expected_top_kind")
    if expected_top_kind is not None and str(top.get("kind") or "") != str(expected_top_kind):
        failures.append({**context, "field": "top_kind", "expected": expected_top_kind, "actual": top.get("kind")})
    expected_path = _list_of_strings(case.get("expected_path_contains"))
    if expected_path and not _path_contains_all(top, expected_path):
        failures.append({**context, "field": "top_path", "expected_contains": expected_path, "actual": top.get("path")})

    query_intent_report = packet.get("query_intent_report") if isinstance(packet.get("query_intent_report"), dict) else {}
    actual_intents = {str(item) for item in query_intent_report.get("intents", [])} if isinstance(query_intent_report.get("intents"), list) else set()
    for intent in _list_of_strings(case.get("expected_query_intents")):
        if intent not in actual_intents:
            failures.append({**context, "missing_query_intent": intent, "actual_intents": sorted(actual_intents)})
    rank_features = top.get("rank_features") if isinstance(top.get("rank_features"), dict) else {}
    for field in _list_of_strings(case.get("required_rank_features")):
        if field not in rank_features:
            failures.append({**context, "doc_id": top.get("doc_id"), "missing_rank_feature": field})
    if rank_features and int(rank_features.get("place_match_count") or 0) <= 0:
        failures.append({**context, "field": "place_match_count", "expected_min": 1, "actual": rank_features.get("place_match_count")})

    required_fields = _list_of_strings(case.get("required_evidence_fields"))
    evidence_chain = [item for item in packet.get("evidence_chain", []) if isinstance(item, dict)] if isinstance(packet.get("evidence_chain"), list) else []
    if not evidence_chain:
        failures.append({**context, "missing": "evidence_chain"})
    for index, evidence in enumerate(evidence_chain):
        for field in required_fields:
            if not evidence.get(field):
                failures.append({**context, "evidence_index": index, "missing_evidence_field": field})

    metrics = _place_ranking_metrics(packet, case)
    for threshold_field, metric_field in [
        ("min_source_path_accuracy", "source_path_accuracy"),
        ("min_place_path_accuracy", "place_path_accuracy"),
        ("min_evidence_attribution", "evidence_attribution"),
    ]:
        if case.get(threshold_field) is not None and float(metrics.get(metric_field) or 0.0) < float(case.get(threshold_field) or 0.0):
            failures.append(
                {
                    **context,
                    "metric": metric_field,
                    "expected_min": case.get(threshold_field),
                    "actual": metrics.get(metric_field),
                }
            )
    return failures


def _place_ranking_metrics(packet: dict[str, object], case: dict[str, object]) -> dict[str, object]:
    results = [item for item in packet.get("results", []) if isinstance(item, dict)] if isinstance(packet.get("results"), list) else []
    limit = max(1, int(case.get("limit") or len(results) or 1))
    top_k = results[:limit]
    evidence_chain = [item for item in packet.get("evidence_chain", []) if isinstance(item, dict)] if isinstance(packet.get("evidence_chain"), list) else []
    required_fields = _list_of_strings(case.get("required_evidence_fields")) or ["evidence_id", "source_url", "path", "fetched_at"]
    evidence_slots = max(1, len(evidence_chain) * max(1, len(required_fields)))
    evidence_hits = sum(1 for evidence in evidence_chain for field in required_fields if evidence.get(field))
    expected_path = _list_of_strings(case.get("expected_path_contains"))
    return {
        "place_at_1": 1.0 if results and str(results[0].get("doc_id") or "") == str(case.get("expected_top_doc_id") or "") else 0.0,
        "source_path_accuracy": _ratio(sum(1 for result in top_k if _has_source_path(result)), len(top_k)),
        "place_path_accuracy": 1.0 if results and _path_contains_all(results[0], expected_path) else 0.0,
        "evidence_attribution": round(evidence_hits / evidence_slots, 6),
    }


def _path_contains_all(result: dict[str, object], expected_parts: list[str]) -> bool:
    if not expected_parts:
        return True
    path = result.get("path")
    if not isinstance(path, list):
        return False
    path_text = " ".join(str(item) for item in path).casefold()
    return all(part.casefold() in path_text for part in expected_parts)


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
    min_snapshot_audit_count = int(suite.get("min_snapshot_audit_count_total") or 0)
    if int(quality.get("snapshot_audit_count_total") or 0) < min_snapshot_audit_count:
        failures.append({"field": "quality.snapshot_audit_count_total", "expected_min": min_snapshot_audit_count, "actual": quality.get("snapshot_audit_count_total")})
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
            and item.get("semantic_index_path")
            and item.get("graph_path")
            and isinstance(item.get("stable_identity"), dict)
            and item["stable_identity"].get("available") is True
            and item["stable_identity"].get("fingerprint")
        ]
        if not matches:
            failures.append({"platform": platform, "missing": "ok checkpoint with normalized/index/semantic-index/graph paths and stable identity fingerprint"})
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
        and item.get("semantic_index_path")
        and item.get("graph_path")
        and isinstance(item.get("stable_identity"), dict)
        and item["stable_identity"].get("available") is True
        and item["stable_identity"].get("fingerprint")
    ]
    if not matches:
        failures.append(
            {
                "platform": "stepik",
                "missing": "ok checkpoint with normalized/index/semantic-index/graph paths and stable identity fingerprint",
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
