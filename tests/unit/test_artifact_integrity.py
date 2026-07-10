from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index, build_semantic_index
from aoa_course_connector.ingest import materialize_stepik_fixture
from aoa_course_connector.integrity import audit_run_artifacts


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def prepare_run(storage: StorageRoots, run_id: str = "integrity-stepik") -> None:
    materialize_stepik_fixture(storage, run_id=run_id)
    build_keyword_index(storage, run_id=run_id)
    build_semantic_index(storage, run_id=run_id)
    build_graph(storage, run_id=run_id)


def test_artifact_integrity_matches_canonical_items_across_indexes_graph_and_evidence(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    prepare_run(storage)

    audit = audit_run_artifacts(storage, "integrity-stepik", probe_limit=20, recall_k=5)

    assert audit["schema"] == "aoa_course_artifact_integrity_v1"
    assert audit["status"] == "ok"
    assert audit["network_touched"] is False
    assert audit["counts"]["expected_index_doc_count"] > 0
    assert audit["counts"]["keyword_doc_count"] == audit["counts"]["expected_index_doc_count"]
    assert audit["counts"]["semantic_doc_count"] == audit["counts"]["expected_index_doc_count"]
    assert audit["integrity"]["keyword_coverage"] == 1.0
    assert audit["integrity"]["semantic_alignment"] == 1.0
    assert audit["integrity"]["graph_coverage"] == 1.0
    assert audit["integrity"]["evidence_attribution"] == 1.0
    assert audit["integrity"]["lexical_retrievability"] == 1.0
    assert audit["integrity"]["dangling_graph_edge_count"] == 0
    assert audit["probes"]["recall_at_k"] == 1.0
    assert audit["failures"] == []


def test_artifact_integrity_fails_for_missing_graph_and_semantic_items(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    prepare_run(storage)
    graph_path = storage.artifact / "runs/integrity-stepik/graphs/course_graph.json"
    semantic_path = storage.artifact / "runs/integrity-stepik/indexes/semantic_index.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
    assignment_node = next(node for node in graph["nodes"] if node["kind"] == "assignment")
    graph["nodes"] = [node for node in graph["nodes"] if node["node_id"] != assignment_node["node_id"]]
    semantic["docs"] = semantic["docs"][1:]
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    semantic_path.write_text(json.dumps(semantic), encoding="utf-8")

    audit = audit_run_artifacts(storage, "integrity-stepik")

    assert audit["status"] == "error"
    assert assignment_node["node_id"] in audit["missing"]["graph_node_ids"]
    assert audit["missing"]["semantic_doc_ids"]
    assert {failure["surface"] for failure in audit["failures"]} >= {"graph_nodes", "semantic_docs"}


def test_artifact_integrity_reports_missing_artifact_without_crashing(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    prepare_run(storage)
    (storage.artifact / "runs/integrity-stepik/indexes/semantic_index.json").unlink()

    audit = audit_run_artifacts(storage, "integrity-stepik", probe_limit=4)

    assert audit["status"] == "error"
    assert any(
        failure["surface"] == "semantic_index" and failure["error"] == "missing_file"
        for failure in audit["failures"]
    )
    assert audit["probes"]["query_error_count"] == audit["probes"]["evaluated_count"]


def test_artifact_integrity_does_not_probe_external_semantic_provider(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    prepare_run(storage)
    semantic_path = storage.artifact / "runs/integrity-stepik/indexes/semantic_index.json"
    semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
    semantic["provider"] = "http_json_v1"
    semantic_path.write_text(json.dumps(semantic), encoding="utf-8")

    audit = audit_run_artifacts(storage, "integrity-stepik", probe_limit=4)

    assert audit["status"] == "error"
    assert audit["network_touched"] is False
    assert audit["probes"]["status"] == "unavailable"
    assert audit["probes"]["reason"] == "external_semantic_provider_requires_network"
