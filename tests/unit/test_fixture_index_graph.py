from __future__ import annotations

from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index, build_semantic_index
from aoa_course_connector.ingest import materialize_fixture
from aoa_course_connector.query import graph_neighbors, query_hybrid_index, query_keyword_index, render_answer_packet


REPO_ROOT = Path(__file__).resolve().parents[2]


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_fixture_to_query_answer_with_evidence(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    receipt = materialize_fixture(storage, run_id="test-run")
    assert receipt["status"] == "ok"
    build_keyword_index(storage, run_id="test-run")
    build_graph(storage, run_id="test-run")
    results = query_keyword_index(storage, "bootloader rollback", run_id="test-run")
    assert results
    assert results[0]["evidence_id"]
    packet = render_answer_packet(storage, "bootloader rollback", run_id="test-run")
    assert packet["result_count"] >= 1
    assert packet["evidence_chain"]


def test_graph_neighbors_include_lesson_context(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="test-run")
    build_keyword_index(storage, run_id="test-run")
    build_graph(storage, run_id="test-run")
    packet = graph_neighbors(storage, "lesson:starter:unlock-risk", run_id="test-run")
    kinds = {edge["kind"] for edge in packet["edges"]}
    assert "module_contains_lesson" in kinds
    assert "lesson_about_topic" in kinds


def test_freshness_ranking_prefers_current_when_relevance_ties(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(
        storage,
        run_id="freshness-ranking-fixture",
        fixture=REPO_ROOT / "connector" / "fixtures" / "course" / "freshness_conflict_course.json",
    )
    build_keyword_index(storage, run_id="freshness-ranking-fixture")
    build_semantic_index(storage, run_id="freshness-ranking-fixture")

    keyword = query_keyword_index(storage, "firmware rollback policy", run_id="freshness-ranking-fixture", limit=2)
    assert [result["doc_id"] for result in keyword] == [
        "step:step:freshness:zzz-current-policy",
        "step:step:freshness:aaa-stale-policy",
    ]
    assert keyword[0]["score"] == keyword[1]["score"]
    assert keyword[0]["rank_score"] > keyword[1]["rank_score"]
    assert keyword[0]["rank_features"]["freshness_state"] == "current"

    hybrid = query_hybrid_index(storage, "firmware rollback policy", run_id="freshness-ranking-fixture", limit=2)
    assert hybrid[0]["doc_id"] == "step:step:freshness:zzz-current-policy"
    assert hybrid[0]["rank_score"] > hybrid[1]["rank_score"]


def test_authority_ranking_prefers_official_and_mentor_sources_when_relevance_ties(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(
        storage,
        run_id="authority-ranking-fixture",
        fixture=REPO_ROOT / "connector" / "fixtures" / "course" / "authority_conflict_course.json",
    )
    build_keyword_index(storage, run_id="authority-ranking-fixture")
    build_semantic_index(storage, run_id="authority-ranking-fixture")

    official = query_keyword_index(storage, "driver signing rollback policy", run_id="authority-ranking-fixture", limit=2)
    assert [result["doc_id"] for result in official] == [
        "step:step:authority:official-policy",
        "comment:comment:authority:learner-policy",
    ]
    assert official[0]["score"] == official[1]["score"]
    assert official[0]["rank_features"]["authority_tier"] == "official_lesson"
    assert official[1]["rank_features"]["authority_tier"] == "learner_comment"
    assert official[0]["rank_score"] > official[1]["rank_score"]

    mentor = query_hybrid_index(storage, "diagnostic logcat capture sequence", run_id="authority-ranking-fixture", limit=2)
    assert [result["doc_id"] for result in mentor] == [
        "comment:comment:authority:mentor-diagnostics",
        "comment:comment:authority:learner-diagnostics",
    ]
    assert mentor[0]["rank_features"]["authority_tier"] == "mentor_comment"
    assert mentor[1]["rank_features"]["authority_tier"] == "learner_comment"
    assert mentor[0]["rank_score"] > mentor[1]["rank_score"]
