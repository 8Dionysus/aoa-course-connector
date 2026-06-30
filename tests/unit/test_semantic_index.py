from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index, build_semantic_index
from aoa_course_connector.ingest import materialize_fixture
from aoa_course_connector.mcp.server import call_tool
from aoa_course_connector.query import query_hybrid_index, query_semantic_index, render_answer_packet


REPO_ROOT = Path(__file__).resolve().parents[2]


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_semantic_index_builds_local_vector_artifact(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="starter-fixture")
    path = build_semantic_index(storage, run_id="starter-fixture", dimensions=64)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "aoa_course_semantic_index_v1"
    assert payload["provider"] == "local_hashing_v1"
    assert payload["dimensions"] == 64
    assert payload["doc_count"] >= 1
    assert payload["docs"][0]["vector"]


def test_semantic_and_hybrid_queries_return_evidence(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_semantic_index(storage, run_id="starter-fixture")
    build_graph(storage, run_id="starter-fixture")

    semantic = query_semantic_index(storage, "bootloader rollback", run_id="starter-fixture")
    assert semantic
    assert semantic[0]["score_mode"] == "semantic_vector"
    assert semantic[0]["evidence_id"]

    hybrid = query_hybrid_index(storage, "bootloader rollback", run_id="starter-fixture")
    assert hybrid
    assert hybrid[0]["score_mode"] == "hybrid"
    assert hybrid[0]["score_components"]

    packet = render_answer_packet(storage, "bootloader rollback", run_id="starter-fixture", mode="hybrid")
    assert packet["mode"] == "hybrid"
    assert packet["result_count"] >= 1
    assert packet["evidence_chain"]


def test_semantic_query_rejects_hash_collision_only_matches(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_semantic_index(storage, run_id="starter-fixture", dimensions=8)

    query = "xylophone nebula quaternion"

    assert query_semantic_index(storage, query, run_id="starter-fixture") == []
    assert query_hybrid_index(storage, query, run_id="starter-fixture") == []


def test_index_manifest_schema_keeps_kind_specific_required_fields() -> None:
    schema = json.loads((REPO_ROOT / "connector" / "schemas" / "index_manifest.schema.json").read_text(encoding="utf-8"))
    variants = {
        variant["properties"]["schema"]["const"]: set(variant["required"])
        for variant in schema["oneOf"]
    }

    assert variants["aoa_course_keyword_index_v1"] >= {"schema", "run_id", "doc_count", "term_count"}
    assert variants["aoa_course_semantic_index_v1"] >= {
        "schema",
        "run_id",
        "doc_count",
        "provider",
        "dimensions",
        "feature_contract",
    }


def test_mcp_semantic_search(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_semantic_index(storage, run_id="starter-fixture")
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    result = call_tool("semantic_search", {"query": "rollback", "run": "starter-fixture"})

    assert result["mode"] == "semantic"
    assert result["results"]
