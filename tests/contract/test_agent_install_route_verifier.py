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
