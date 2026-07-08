from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


VERIFIER_PATH = Path("scripts/verify_agent_install_route.py")


def load_verifier_module():
    spec = importlib.util.spec_from_file_location("verify_agent_install_route", VERIFIER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stdio_verifier_rejects_tool_error_with_structured_content() -> None:
    verifier = load_verifier_module()
    responses = [
        {"jsonrpc": "2.0", "id": 3, "result": {"structuredContent": {"tool": "search", "results": [{}]}, "isError": False}},
        {
            "jsonrpc": "2.0",
            "id": 8,
            "result": {
                "structuredContent": {
                    "tool": "answer",
                    "answer_packet": {
                        "schema": "aoa_course_answer_packet_v1",
                        "quality": {"ready": True},
                        "evidence_chain": [{"evidence_id": "evidence:test"}],
                    },
                },
                "isError": False,
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 9,
            "result": {
                "structuredContent": {
                    "tool": "connected_run",
                    "connected_run": {
                        "schema": "aoa_course_connected_calibration_run_receipt_v1",
                        "status": "ok",
                        "network_touched": False,
                    },
                },
                "isError": False,
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "result": {
                "structuredContent": {
                    "schema": "aoa_course_mcp_error_v1",
                    "error": "preflight broke",
                },
                "isError": True,
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 5,
            "result": {
                "structuredContent": {
                    "tool": "connected_source_plan",
                    "plan": {"network_touched": False, "live_scope": "bounded"},
                },
                "isError": False,
            },
        },
    ]
    stdout = "\n".join(json.dumps(response) for response in responses)

    with pytest.raises(verifier.StdioVerificationError, match="live_preflight returned MCP tool error"):
        verifier._verify_stdio_tool_responses(stdout)


def test_stdio_verifier_requires_direct_answer_packet() -> None:
    verifier = load_verifier_module()
    responses = _healthy_stdio_responses()
    answer = next(response for response in responses if response["id"] == 8)
    answer["result"]["structuredContent"]["answer_packet"]["quality"]["ready"] = False
    stdout = "\n".join(json.dumps(response) for response in responses)

    with pytest.raises(verifier.StdioVerificationError, match="answer stdio response quality is not ready"):
        verifier._verify_stdio_tool_responses(stdout)


def test_stdio_verifier_requires_connected_run_ok() -> None:
    verifier = load_verifier_module()
    responses = _healthy_stdio_responses()
    connected_run = next(response for response in responses if response["id"] == 9)
    connected_run["result"]["structuredContent"]["connected_run"]["status"] = "partial"
    stdout = "\n".join(json.dumps(response) for response in responses)

    with pytest.raises(verifier.StdioVerificationError, match="connected_run stdio response was not ok"):
        verifier._verify_stdio_tool_responses(stdout)


def test_stdio_verifier_requires_sources_answer_ready() -> None:
    verifier = load_verifier_module()
    responses = _healthy_stdio_responses()
    sources_answer = next(response for response in responses if response["id"] == 11)
    sources_answer["result"]["structuredContent"]["sources_answer"]["quality"]["ready"] = False
    stdout = "\n".join(json.dumps(response) for response in responses)

    with pytest.raises(
        verifier.StdioVerificationError,
        match="sources_answer stdio response did not prove source-scoped retrieval readiness",
    ):
        verifier._verify_stdio_tool_responses(stdout)


def test_stdio_verifier_requires_sources_answer_matrix_ready() -> None:
    verifier = load_verifier_module()
    responses = _healthy_stdio_responses()
    sources_answer_matrix = next(response for response in responses if response["id"] == 12)
    sources_answer_matrix["result"]["structuredContent"]["sources_answer_matrix"]["quality"]["ready"] = False
    stdout = "\n".join(json.dumps(response) for response in responses)

    with pytest.raises(
        verifier.StdioVerificationError,
        match="sources_answer_matrix stdio response did not prove multi-query readiness",
    ):
        verifier._verify_stdio_tool_responses(stdout)


def test_stdio_verifier_requires_ready_connected_run_mcp_call() -> None:
    verifier = load_verifier_module()
    responses = _healthy_stdio_responses()
    plan = responses[2]["result"]["structuredContent"]["plan"]["connected_run_plan"]
    plan.update(
        {
            "ready": True,
            "command": "aoa-course calibration connected-run --mode live --allow-network",
        }
    )
    stdout = "\n".join(json.dumps(response) for response in responses)

    with pytest.raises(verifier.StdioVerificationError, match="did not expose MCP connected_run tool call"):
        verifier._verify_stdio_tool_responses(stdout)


def test_stdio_verifier_accepts_full_mcp_route() -> None:
    verifier = load_verifier_module()
    stdout = "\n".join(json.dumps(response) for response in _healthy_stdio_responses())

    verifier._verify_stdio_tool_responses(stdout)


def _healthy_stdio_responses() -> list[dict[str, object]]:
    return [
        {"jsonrpc": "2.0", "id": 3, "result": {"structuredContent": {"tool": "search", "results": [{}]}, "isError": False}},
        {
            "jsonrpc": "2.0",
            "id": 4,
            "result": {"structuredContent": {"tool": "live_preflight", "preflight": {"network_touched": False}}, "isError": False},
        },
        {
            "jsonrpc": "2.0",
            "id": 5,
            "result": {
                "structuredContent": {
                    "tool": "connected_source_plan",
                    "plan": {
                        "network_touched": False,
                        "live_scope": "bounded",
                        "connected_run_plan": {
                            "kind": "connected_run",
                            "network_touched": True,
                            "ready": False,
                            "blocked_by": ["missing operator auth"],
                        },
                    },
                },
                "isError": False,
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 6,
            "result": {
                "structuredContent": {
                    "tool": "semantic_provider_preflight",
                    "preflight": {"network_touched": False},
                },
                "isError": False,
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 7,
            "result": {
                "structuredContent": {
                    "tool": "connector_readiness",
                    "schema": "aoa_course_connector_readiness_v1",
                    "network_touched": False,
                },
                "isError": False,
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 8,
            "result": {
                "structuredContent": {
                    "tool": "answer",
                    "answer_packet": {
                        "schema": "aoa_course_answer_packet_v1",
                        "quality": {"ready": True},
                        "evidence_chain": [{"evidence_id": "evidence:test"}],
                    },
                },
                "isError": False,
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 9,
            "result": {
                "structuredContent": {
                    "tool": "connected_run",
                    "connected_run": {
                        "schema": "aoa_course_connected_calibration_run_receipt_v1",
                        "status": "ok",
                        "network_touched": False,
                    },
                },
                "isError": False,
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 10,
            "result": {
                "structuredContent": {
                    "tool": "connected_run_query",
                    "query_packet": {
                        "schema": "aoa_course_connected_run_query_packet_v1",
                        "status": "ok",
                        "network_touched": False,
                        "response_count": 1,
                        "quality": {"ready": True},
                    },
                },
                "isError": False,
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 11,
            "result": {
                "structuredContent": {
                    "tool": "sources_answer",
                    "sources_answer": {
                        "schema": "aoa_course_sources_answer_packet_v1",
                        "status": "ok",
                        "network_touched": False,
                        "response_count": 1,
                        "quality": {"ready": True, "evidence_count_total": 1},
                    },
                },
                "isError": False,
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 12,
            "result": {
                "structuredContent": {
                    "tool": "sources_answer_matrix",
                    "sources_answer_matrix": {
                        "schema": "aoa_course_sources_answer_matrix_v1",
                        "status": "ok",
                        "network_touched": False,
                        "query_count": 2,
                        "quality": {"ready": True, "evidence_count_total": 2},
                    },
                },
                "isError": False,
            },
        },
    ]
