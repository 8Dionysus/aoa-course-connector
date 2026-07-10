from __future__ import annotations

import json
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import build_keyword_index, build_semantic_index, tokenize
from aoa_course_connector.ingest import materialize_fixture
from aoa_course_connector.query import (
    _rank_features,
    graph_neighbors,
    lesson_graph_context,
    portfolio_rank_features,
    query_hybrid_index,
    query_keyword_index,
    render_answer_packet,
)
from aoa_course_connector.storage import run_data_dir


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

    unlock_results = query_keyword_index(storage, "bootloader unlock rollback", run_id="test-run")
    assert unlock_results[0]["rank_features"]["access_boost"] == 0.0
    assert unlock_results[0]["rank_features"]["intent_class"] == "stable_knowledge"
    unlock_packet = render_answer_packet(storage, "bootloader unlock rollback", run_id="test-run")
    assert unlock_packet["query_intent_report"]["intent_class"] == "stable_knowledge"
    assert unlock_packet["query_intent_report"]["top_result_intent_class"] == "stable_knowledge"

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


def test_keyword_index_preserves_item_timestamp_before_fetch_timestamp(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="test-run")
    index_path = build_keyword_index(storage, run_id="test-run")

    index = json.loads(index_path.read_text(encoding="utf-8"))
    mentor_comment = next(doc for doc in index["docs"] if doc["doc_id"] == "comment:comment:starter:mentor-warning")

    assert mentor_comment["observed_at"] == "2026-06-29T12:15:00Z"


def test_symbolic_course_title_terms_match_without_sentence_punctuation(tmp_path: Path) -> None:
    assert tokenize("PRO C#. Основы программирования")[:3] == ["pro", "c#", "основы"]

    storage = roots(tmp_path)
    run_id = "csharp-title-fixture"
    bundle_path = run_data_dir(storage, run_id) / "normalized" / "course_bundle.json"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(
        json.dumps(
            {
                "schema": "aoa_course_bundle_v1",
                "courses": [
                    {
                        "course_id": "course:csharp",
                        "source_id": "source:stepik:csharp",
                        "title": "PRO C#. Основы программирования",
                        "url": "https://stepik.org/course/5482",
                        "platform": "stepik",
                        "modules": [
                            {
                                "module_id": "module:intro",
                                "title": "Общая информация о курсе",
                                "lessons": [
                                    {
                                        "lesson_id": "lesson:welcome",
                                        "title": "Добро пожаловать",
                                        "url": "https://stepik.org/lesson/1263653",
                                        "freshness_state": "current",
                                        "evidence": {
                                            "evidence_id": "evidence:csharp:welcome",
                                            "source_url": "https://stepik.org/lesson/1263653",
                                            "fetched_at": "2026-07-08T23:09:17Z",
                                        },
                                        "steps": [
                                            {
                                                "step_id": "step:welcome",
                                                "text": "Добро пожаловать в курс.",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "course_id": "course:python",
                        "source_id": "source:stepik:python",
                        "title": "Программирование на Python",
                        "url": "https://stepik.org/course/67",
                        "platform": "stepik",
                        "modules": [
                            {
                                "module_id": "module:python-basics",
                                "title": "Заключение",
                                "lessons": [
                                    {
                                        "lesson_id": "lesson:python-finish",
                                        "title": "Основы программирования",
                                        "url": "https://stepik.org/lesson/7630",
                                        "freshness_state": "current",
                                        "evidence": {
                                            "evidence_id": "evidence:python:finish",
                                            "source_url": "https://stepik.org/lesson/7630",
                                            "fetched_at": "2026-07-08T23:09:17Z",
                                        },
                                        "steps": [
                                            {
                                                "step_id": "step:python-finish",
                                                "text": "Изучайте основы программирования и программируйте с удовольствием.",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    build_keyword_index(storage, run_id=run_id)
    build_semantic_index(storage, run_id=run_id)

    results = query_keyword_index(storage, "C#", run_id=run_id)

    assert results
    assert results[0]["course_title"] == "PRO C#. Основы программирования"
    assert results[0]["evidence_id"] == "evidence:csharp:welcome"

    hybrid_results = query_hybrid_index(storage, "C# основы программирования", run_id=run_id)

    assert hybrid_results[0]["course_title"] == "PRO C#. Основы программирования"
    assert hybrid_results[0]["rank_features"]["place_match_count"] == 3
    assert set(hybrid_results[0]["rank_features"]["place_matches"]) == {"c#", "основы", "программирования"}
    assert hybrid_results[0]["rank_features"]["place_boost"] > hybrid_results[1]["rank_features"]["place_boost"]


def test_single_course_title_match_beats_cross_source_semantic_noise(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    run_id = "single-course-title-place-fixture"
    bundle_path = run_data_dir(storage, run_id) / "normalized" / "course_bundle.json"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(
        json.dumps(
            {
                "schema": "aoa_course_bundle_v1",
                "courses": [
                    {
                        "course_id": "course:philosophy",
                        "source_id": "source:stepik:philosophy",
                        "title": "Философия",
                        "url": "https://stepik.org/course/6667",
                        "platform": "stepik",
                        "modules": [
                            {
                                "module_id": "module:philosophy-intro",
                                "title": "Введение",
                                "lessons": [
                                    {
                                        "lesson_id": "lesson:philosophy-short",
                                        "title": "КРАТКО: чем философия отличается от науки, религии и искусства?",
                                        "url": "https://stepik.org/lesson/459388",
                                        "freshness_state": "current",
                                        "evidence": {
                                            "evidence_id": "evidence:philosophy:short",
                                            "source_url": "https://stepik.org/lesson/459388",
                                            "fetched_at": "2026-07-08T23:09:17Z",
                                        },
                                        "steps": [
                                            {
                                                "step_id": "step:philosophy-short",
                                                "text": "Философия помогает понять основания знания, ценностей и искусства.",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "course_id": "course:bot",
                        "source_id": "source:stepik:bot",
                        "title": "Telegram-бот на Python за вечер",
                        "url": "https://stepik.org/course/268845",
                        "platform": "stepik",
                        "modules": [
                            {
                                "module_id": "module:bot-bonus",
                                "title": "Бонус",
                                "lessons": [
                                    {
                                        "lesson_id": "lesson:bot-business",
                                        "title": "Бот-визитка репетитора",
                                        "url": "https://stepik.org/lesson/1592972",
                                        "freshness_state": "current",
                                        "evidence": {
                                            "evidence_id": "evidence:bot:business",
                                            "source_url": "https://stepik.org/lesson/1592972",
                                            "fetched_at": "2026-07-08T23:09:17Z",
                                        },
                                        "steps": [
                                            {
                                                "step_id": "step:bot-business",
                                                "text": "Зачем нужна визитка, зачем нужна заявка и зачем нужна автоматизация общения.",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    build_keyword_index(storage, run_id=run_id)
    build_semantic_index(storage, run_id=run_id)

    hybrid_results = query_hybrid_index(storage, "философия зачем нужна", run_id=run_id, limit=2)

    assert [result["course_title"] for result in hybrid_results] == ["Философия", "Telegram-бот на Python за вечер"]
    assert hybrid_results[0]["rank_features"]["place_matches"] == ["философия"]
    assert hybrid_results[0]["rank_features"]["place_boost"] > hybrid_results[1]["rank_features"]["place_boost"]


def test_portfolio_rank_matches_compound_and_inflected_native_path_terms() -> None:
    query = "как запустить онлайн-школу"
    relevant = portfolio_rank_features(
        query,
        {
            "path": ["Марафон Точка Старта", "Уроки", "Старт запуска вашей онлайн-школы"],
            "text": "Первый урок о запуске онлайн-школы.",
            "rank_score": 0.59,
            "score_components": {"semantic": 0.12},
            "semantic_provider": "local_hashing_v1",
        },
    )
    noise = portfolio_rank_features(
        query,
        {
            "path": ["Философия", "Мир и познание", "Пространство и время"],
            "text": "Исторические формы понимания пространства и времени.",
            "rank_score": 0.68,
            "score_components": {"semantic": 0.33},
            "semantic_provider": "local_hashing_v1",
        },
    )

    assert relevant["query_term_count"] == 3
    assert relevant["path_coverage"] == 1.0
    assert relevant["lexical_coverage"] == 1.0
    assert relevant["confidence"] == "high"
    assert relevant["confident"] is True
    assert relevant["portfolio_rank_score"] > noise["portfolio_rank_score"]
    assert noise["confidence"] == "none"
    assert noise["confident"] is False

    false_prefix = portfolio_rank_features(
        "как привязать Telegram к профилю",
        {
            "path": ["Telegram-бот", "Сообщения"],
            "text": "Привет пользователю. Профилю назначен Telegram username.",
            "rank_score": 0.74,
            "score_components": {"semantic": 0.17},
            "semantic_provider": "local_hashing_v1",
        },
    )
    assert "привязать" not in false_prefix["lexical_matches"]
    assert false_prefix["lexical_coverage"] < 1.0

    machine_doc = {
        "path": ["Firmware Audit", "Bugreport lesson", "skillspace:lesson:ss-lesson-bugreport:assignment:1"],
        "text": "Attach bugreport evidence.",
        "rank_score": 0.74,
        "score_components": {"semantic": 0.17},
        "semantic_provider": "local_hashing_v1",
    }
    machine_path = portfolio_rank_features("Skillspace logcat bugreport evidence", machine_doc)
    native_path = portfolio_rank_features(
        "Skillspace logcat bugreport evidence",
        {
            "path": ["Firmware Audit", "Mobile Debugging", "Logcat lesson"],
            "text": "Use Skillspace logcat to inspect the bugreport evidence.",
            "rank_score": 0.70,
            "score_components": {"semantic": 0.20},
            "semantic_provider": "local_hashing_v1",
        },
    )
    assert "skillspace" not in machine_path["path_lexical_matches"]
    assert "skillspace" not in _rank_features(machine_doc, tokenize("Skillspace logcat bugreport evidence"))["place_matches"]
    assert native_path["portfolio_rank_score"] > machine_path["portfolio_rank_score"]


def test_graph_neighbors_include_lesson_context(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="test-run")
    build_keyword_index(storage, run_id="test-run")
    build_graph(storage, run_id="test-run")
    packet = graph_neighbors(storage, "lesson:starter:unlock-risk", run_id="test-run")
    kinds = {edge["kind"] for edge in packet["edges"]}
    assert "module_contains_lesson" in kinds
    assert "lesson_about_topic" in kinds


def test_lesson_graph_context_reports_missing_node_as_unavailable(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="test-run")
    build_graph(storage, run_id="test-run")
    packet = {"evidence_chain": [{"evidence_id": "evidence:missing", "lesson_id": "lesson:missing"}]}

    context = lesson_graph_context(storage, packet, run_id="test-run")

    assert context["status"] == "missing_graph"
    assert context["ready_context_count"] == 0
    assert context["contexts"][0]["node_status"] == "missing_node"
    assert context["missing"][0]["reason"] == "missing_node"
    assert "build-graph --run test-run" in context["missing"][0]["next_command"]


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
