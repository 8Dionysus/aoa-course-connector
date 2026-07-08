from __future__ import annotations

import json
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
    assert packet["quality"]["schema"] == "aoa_course_answer_quality_summary_v1"
    assert packet["quality"]["ready"] is True
    assert packet["quality"]["result_count"] == packet["result_count"]
    assert packet["quality"]["evidence_count"] == len(packet["evidence_chain"])
    assert packet["quality"]["provenance_complete_count"] == packet["result_count"]
    assert packet["quality"]["refresh_hint_count"] == packet["result_count"]
    assert packet["quality"]["top_result"]["doc_id"] == packet["results"][0]["doc_id"]
    evidence = packet["evidence_chain"][0]
    assert evidence["doc_id"]
    assert evidence["freshness_state"] == packet["results"][0]["freshness_state"]
    assert evidence["authority_tier"] == packet["results"][0]["authority_tier"]
    assert evidence["rank_score"] == packet["results"][0]["rank_score"]
    assert evidence["rank_features"]["provenance_complete"] is True
    assert evidence["snippet"] == packet["results"][0]["snippet"]
    assert "bootloader" in evidence["snippet"].casefold()

    place_results = query_keyword_index(storage, "where Course Knowledge Indexing Evidence-Backed Search", run_id="test-run")
    assert place_results[0]["doc_id"] == "step:step:starter:evidence-search:packet"
    assert place_results[0]["rank_features"]["intent"] == "place"
    assert place_results[0]["rank_features"]["place_complete"] is True
    assert {"knowledge", "indexing", "evidence-backed", "search"} <= set(place_results[0]["rank_features"]["place_matches"])
    place_packet = render_answer_packet(storage, "where Course Knowledge Indexing Evidence-Backed Search", run_id="test-run")
    assert place_packet["query_intent_report"]["place_intent"] is True
    assert place_packet["query_intent_report"]["top_result_place_complete"] is True


def test_answer_packet_omits_missing_optional_evidence_fields(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="test-run")
    build_keyword_index(storage, run_id="test-run")

    packet = render_answer_packet(storage, "in_progress", run_id="test-run")
    progress_evidence = next(item for item in packet["evidence_chain"] if item["kind"] == "progress")

    assert progress_evidence["authority_tier"] == "progress_metadata"
    assert progress_evidence["authority_label"] == ""
    assert "source_authority" not in progress_evidence
    assert all(value is not None for value in progress_evidence.values())


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
    graph_path = build_graph(storage, run_id="freshness-ranking-fixture")

    keyword = query_keyword_index(storage, "firmware rollback policy", run_id="freshness-ranking-fixture", limit=2)
    assert [result["doc_id"] for result in keyword] == [
        "step:step:freshness:zzz-current-policy",
        "step:step:freshness:aaa-stale-policy",
    ]
    assert keyword[0]["score"] == keyword[1]["score"]
    assert keyword[0]["rank_score"] > keyword[1]["rank_score"]
    assert keyword[0]["rank_features"]["freshness_state"] == "current"
    assert keyword[0]["rank_features"]["intent_class"] == "stable_knowledge"
    assert keyword[0]["rank_features"]["recency_gate"] < 1.0

    hybrid = query_hybrid_index(storage, "firmware rollback policy", run_id="freshness-ranking-fixture", limit=2)
    assert hybrid[0]["doc_id"] == "step:step:freshness:zzz-current-policy"
    assert hybrid[0]["rank_score"] > hybrid[1]["rank_score"]

    latest = query_keyword_index(storage, "latest firmware rollback policy", run_id="freshness-ranking-fixture", limit=2)
    assert latest[0]["doc_id"] == "step:step:freshness:zzz-current-policy"
    assert latest[0]["rank_features"]["intent"] == "fresh"
    assert latest[0]["rank_features"]["intent_class"] == "fresh_fact"
    assert latest[0]["rank_features"]["recency_gate"] == 1.0
    assert latest[0]["rank_features"]["temporal_boost"] > 0
    assert latest[0]["rank_score"] > latest[1]["rank_score"]

    historical = query_keyword_index(storage, "old firmware rollback policy", run_id="freshness-ranking-fixture", limit=2)
    assert historical[0]["doc_id"] == "step:step:freshness:aaa-stale-policy"
    assert historical[0]["score"] == historical[1]["score"]
    assert historical[0]["rank_features"]["intent"] == "historical"
    assert historical[0]["rank_features"]["intent_class"] == "historical_fact"
    assert historical[0]["rank_features"]["recency_gate"] < latest[0]["rank_features"]["recency_gate"]
    assert historical[0]["rank_features"]["temporal_boost"] > 0
    assert historical[0]["rank_score"] > historical[1]["rank_score"]
    historical_packet = render_answer_packet(storage, "old firmware rollback policy", run_id="freshness-ranking-fixture", limit=2)
    assert historical_packet["query_intent_report"]["intent_class"] == "historical_fact"
    assert historical_packet["evidence_chain"][0]["version_group_id"] == "version-group:freshness:firmware-rollback-policy"
    assert historical_packet["evidence_chain"][0]["valid_until"] == "2026-01-01T00:00:00Z"

    version_history = query_hybrid_index(storage, "version history firmware rollback policy", run_id="freshness-ranking-fixture", limit=2)
    assert [result["doc_id"] for result in version_history] == [
        "step:step:freshness:zzz-current-policy",
        "step:step:freshness:aaa-stale-policy",
    ]
    assert version_history[0]["rank_features"]["intent"] == "version_comparison"
    assert version_history[0]["rank_features"]["intent_class"] == "version_comparison"
    version_packet = render_answer_packet(storage, "version history firmware rollback policy", run_id="freshness-ranking-fixture", limit=2, mode="hybrid")
    assert version_packet["query_intent_report"]["intent_class"] == "version_comparison"
    assert {item["version_group_id"] for item in version_packet["evidence_chain"]} == {"version-group:freshness:firmware-rollback-policy"}
    temporal_report = version_packet["temporal_report"]
    assert temporal_report["schema"] == "aoa_course_temporal_answer_report_v1"
    assert temporal_report["conflict_detected"] is True
    assert temporal_report["conflict_group_count"] == 1
    assert temporal_report["timestamp_coverage"] == 1.0
    assert temporal_report["groups"][0]["current_doc_ids"] == ["step:step:freshness:zzz-current-policy"]
    assert temporal_report["groups"][0]["stale_doc_ids"] == ["step:step:freshness:aaa-stale-policy"]

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    assert graph["temporal"]["version_group_count"] == 1
    assert graph["temporal"]["snapshot_node_count"] >= 4
    assert graph["temporal"]["timestamped_edge_count"] >= 6
    current_node = next(node for node in graph["nodes"] if node["node_id"] == "lesson:freshness:zzz-current-policy")
    stale_node = next(node for node in graph["nodes"] if node["node_id"] == "lesson:freshness:aaa-stale-policy")
    assert current_node["version_group_id"] == stale_node["version_group_id"] == "version-group:freshness:firmware-rollback-policy"
    assert current_node["valid_from"] == "2026-01-01T00:00:00Z"
    assert stale_node["valid_until"] == "2026-01-01T00:00:00Z"
    assert any(
        edge["kind"] == "version_group_has_snapshot"
        and edge["from_node"] == "version-group:freshness:firmware-rollback-policy"
        and edge["to_node"] == "lesson:freshness:zzz-current-policy"
        for edge in graph["edges"]
    )
    temporal_neighbors = graph_neighbors(storage, "lesson:freshness:zzz-current-policy", run_id="freshness-ranking-fixture")
    temporal_context = temporal_neighbors["temporal_context"]
    assert temporal_context["status"] == "ready"
    assert temporal_context["version_count"] == 2
    assert [item["node_id"] for item in temporal_context["versions"]] == [
        "lesson:freshness:aaa-stale-policy",
        "lesson:freshness:zzz-current-policy",
    ]


def test_place_ranking_preserves_native_hierarchy_fields(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(
        storage,
        run_id="place-ranking-fixture",
        fixture=REPO_ROOT / "connector" / "fixtures" / "course" / "place_conflict_course.json",
    )
    build_keyword_index(storage, run_id="place-ranking-fixture")
    build_semantic_index(storage, run_id="place-ranking-fixture")

    thread_hits = query_hybrid_index(storage, "where in thread Mentor Answers timestamp window reproduction step", run_id="place-ranking-fixture", limit=4)
    assert thread_hits[0]["doc_id"] == "comment:comment:place:mentor-answer"
    assert thread_hits[0]["thread_title"] == "Mentor Answers"
    assert thread_hits[0]["author_label"] == "mentor"
    assert thread_hits[0]["rank_features"]["place_complete"] is True
    assert thread_hits[0]["rank_features"]["place_match_count"] >= 2
    thread_packet = render_answer_packet(storage, "where in thread Mentor Answers timestamp window reproduction step", run_id="place-ranking-fixture", limit=4, mode="hybrid")
    assert thread_packet["query_intent_report"]["intent_class"] == "place_lookup"
    assert thread_packet["evidence_chain"][0]["thread_title"] == "Mentor Answers"
    assert thread_packet["evidence_chain"][0]["author_label"] == "mentor"

    asset_hits = query_hybrid_index(storage, "where attachment Camera Evidence Pack", run_id="place-ranking-fixture", limit=4)
    assert asset_hits[0]["doc_id"] == "asset:asset:place:camera-pack"
    assert asset_hits[0]["item_title"] == "Camera Evidence Pack"
    assert str(asset_hits[0]["item_url"]).endswith("/camera-evidence-pack.txt")


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
    official_packet = render_answer_packet(storage, "driver signing rollback policy", run_id="authority-ranking-fixture")
    assert official_packet["quality"]["ready"] is True
    assert official_packet["quality"]["top_result"]["authority_tier"] == "official_lesson"
    assert official_packet["evidence_chain"][0]["authority_tier"] == "official_lesson"
    assert official_packet["evidence_chain"][0]["rank_score"] == official_packet["results"][0]["rank_score"]

    mentor = query_hybrid_index(storage, "diagnostic logcat capture sequence", run_id="authority-ranking-fixture", limit=2)
    assert [result["doc_id"] for result in mentor] == [
        "comment:comment:authority:mentor-diagnostics",
        "comment:comment:authority:learner-diagnostics",
    ]
    assert mentor[0]["rank_features"]["authority_tier"] == "mentor_comment"
    assert mentor[1]["rank_features"]["authority_tier"] == "learner_comment"
    assert mentor[0]["rank_score"] > mentor[1]["rank_score"]
