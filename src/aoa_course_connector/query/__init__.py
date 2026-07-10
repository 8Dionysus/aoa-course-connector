"""Query and answer-packet helpers."""

from __future__ import annotations

import json
import re
import shlex
from datetime import UTC, datetime
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.index import (
    LOCAL_HASHING_PROVIDER,
    query_lookup_tokens,
    semantic_doc_feature_keys,
    semantic_query_feature_keys,
    sparse_vector_from_json,
    tokenize,
    vector_dot,
    vectorize_semantic_query,
)
from aoa_course_connector.quality import summarize_answer_packet
from aoa_course_connector.sources import load_registry
from aoa_course_connector.storage import run_artifact_dir


BROWSER_REFRESH_PLATFORMS = {"getcourse", "skillspace"}
LIVE_REFRESH_PLATFORMS = {"getcourse", "skillspace", "stepik"}
AUTH_ROOT_EXPR = "${AOA_COURSE_AUTH_ROOT:-.connector-state/auth}"

FRESHNESS_RANK_WEIGHTS = {
    "current": 0.08,
    "fresh": 0.08,
    "verified": 0.06,
    "active": 0.05,
    "unknown": 0.0,
    "stale": -0.12,
    "outdated": -0.14,
    "deprecated": -0.18,
    "archived": -0.08,
    "access_denied": -0.18,
    "discovered_not_fetched": -0.16,
    "fetch_error": -0.20,
}

AUTHORITY_RANK_WEIGHTS = {
    "official_lesson": 0.10,
    "official_assignment": 0.08,
    "instructor_comment": 0.07,
    "mentor_comment": 0.06,
    "transcript": 0.03,
    "discussion_comment": 0.0,
    "unknown": 0.0,
    "progress_metadata": -0.02,
    "learner_comment": -0.03,
    "asset_metadata": -0.04,
    "discovered_link": -0.10,
    "access_notice": -0.12,
}
ACCESS_INTENT_TERMS = {
    "access",
    "blocked",
    "closed",
    "denied",
    "gated",
    "locked",
    "unlock",
    "unavailable",
    "доступ",
    "доступа",
    "доступен",
    "доступна",
    "доступны",
    "закрыт",
    "закрыта",
    "закрытые",
    "заблокирован",
    "заблокирована",
    "недоступен",
    "недоступна",
    "открыть",
    "разблокировать",
}
FRESH_INTENT_TERMS = {
    "actual",
    "актуален",
    "актуальна",
    "актуально",
    "актуальные",
    "current",
    "fresh",
    "latest",
    "new",
    "newest",
    "now",
    "present",
    "recent",
    "today",
    "version",
    "версия",
    "последняя",
    "последний",
    "последнее",
    "свежая",
    "свежие",
    "свежий",
    "сейчас",
    "сегодня",
    "текущая",
    "текущий",
    "нынешняя",
    "нынешний",
}
VERSION_COMPARISON_INTENT_TERMS = {
    "between",
    "change",
    "changed",
    "changes",
    "changelog",
    "compare",
    "comparison",
    "diff",
    "difference",
    "evolution",
    "timeline",
    "versions",
    "vs",
    "версии",
    "версий",
    "изменение",
    "изменения",
    "история",
    "отличие",
    "отличия",
    "сравнение",
    "сравнить",
    "хронология",
}
HISTORICAL_INTENT_TERMS = {
    "archive",
    "archived",
    "before",
    "deprecated",
    "earlier",
    "history",
    "historical",
    "legacy",
    "old",
    "older",
    "outdated",
    "past",
    "previous",
    "then",
    "архив",
    "архивная",
    "архивный",
    "было",
    "историческая",
    "история",
    "раньше",
    "старая",
    "старый",
    "устаревшая",
    "устаревший",
}
PLACE_INTENT_TERMS = {
    "block",
    "breadcrumb",
    "chapter",
    "comment",
    "course",
    "forum",
    "lesson",
    "module",
    "path",
    "place",
    "section",
    "source",
    "thread",
    "url",
    "where",
    "блок",
    "где",
    "источник",
    "комментарий",
    "курс",
    "место",
    "модуле",
    "модуль",
    "автор",
    "вложение",
    "путь",
    "раздел",
    "ссылка",
    "тред",
    "урок",
    "уроке",
}
QUERY_STOP_TERMS = {
    "a",
    "an",
    "and",
    "for",
    "how",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "what",
    "where",
    "why",
    "а",
    "без",
    "в",
    "во",
    "где",
    "для",
    "до",
    "зачем",
    "и",
    "из",
    "или",
    "как",
    "к",
    "ли",
    "на",
    "о",
    "об",
    "от",
    "по",
    "почему",
    "при",
    "с",
    "со",
    "у",
    "что",
    "это",
}
LEXICAL_SPLIT_RE = re.compile(r"[-_/]+")
CYRILLIC_TERM_RE = re.compile(r"^[а-яё]+$", re.IGNORECASE)
RUSSIAN_INFLECTION_SUFFIXES = tuple(
    sorted(
        {
            "иями",
            "ами",
            "ями",
            "ого",
            "ему",
            "ому",
            "ими",
            "ыми",
            "ать",
            "ять",
            "еть",
            "ить",
            "уть",
            "ите",
            "ете",
            "ают",
            "яют",
            "уют",
            "ах",
            "ях",
            "ов",
            "ев",
            "ей",
            "ам",
            "ям",
            "ом",
            "ем",
            "ою",
            "ею",
            "ую",
            "юю",
            "ая",
            "яя",
            "ое",
            "ее",
            "ые",
            "ие",
            "ый",
            "ий",
            "ой",
            "ых",
            "их",
            "ть",
            "ти",
            "а",
            "я",
            "ы",
            "и",
            "у",
            "ю",
            "е",
            "о",
            "ь",
        },
        key=len,
        reverse=True,
    )
)


def query_keyword_index(roots: StorageRoots, query: str, run_id: str = "starter-fixture", limit: int = 5) -> list[dict[str, object]]:
    index_path = run_artifact_dir(roots, run_id) / "indexes" / "keyword_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    docs = {str(doc["doc_id"]): doc for doc in index.get("docs", [])}
    query_terms = query_lookup_tokens(query)
    scores: dict[str, float] = {}
    for term in query_terms:
        for hit in index.get("inverted", {}).get(term, []):
            doc_id = str(hit["doc_id"])
            scores[doc_id] = scores.get(doc_id, 0.0) + float(hit.get("count", 1))
    ranked = []
    for doc_id, score in sorted(scores.items(), key=lambda item: (-item[1], item[0])):
        doc = docs.get(doc_id)
        if not doc:
            continue
        rank_features = _rank_features(doc, query_terms)
        ranked.append(
            {
                **doc,
                "score": score,
                "rank_score": _rank_score(score, rank_features),
                "rank_features": rank_features,
                "snippet": _snippet(str(doc.get("text") or ""), query_terms),
            }
        )
    return sorted(ranked, key=_result_sort_key)[:limit]


def query_semantic_index(roots: StorageRoots, query: str, run_id: str = "starter-fixture", limit: int = 5) -> list[dict[str, object]]:
    index_path = run_artifact_dir(roots, run_id) / "indexes" / "semantic_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    dimensions = int(index.get("dimensions") or 256)
    provider = str(index.get("provider") or LOCAL_HASHING_PROVIDER)
    provider_config = index.get("provider_config") if isinstance(index.get("provider_config"), dict) else {}
    query_vector = vectorize_semantic_query(
        query,
        dimensions=dimensions,
        provider=provider,
        provider_config=provider_config,
    )
    query_features = semantic_query_feature_keys(query) if provider == LOCAL_HASHING_PROVIDER else set()
    if not query_vector:
        return []
    if provider == LOCAL_HASHING_PROVIDER and not query_features:
        return []
    query_terms = query_lookup_tokens(query)
    ranked = []
    for doc in index.get("docs", []):
        if not isinstance(doc, dict):
            continue
        vector = sparse_vector_from_json(doc.get("vector"))
        score = vector_dot(query_vector, vector)
        if score <= 0:
            continue
        if provider == LOCAL_HASHING_PROVIDER and not (query_features & semantic_doc_feature_keys(doc)):
            continue
        result = {key: value for key, value in doc.items() if key != "vector"}
        rank_features = _rank_features(result, query_terms)
        ranked.append(
            {
                **result,
                "score": round(score, 6),
                "rank_score": _rank_score(score, rank_features),
                "rank_features": rank_features,
                "score_mode": "semantic_vector",
                "semantic_provider": provider,
                "snippet": _snippet(str(doc.get("text") or ""), query_terms),
            }
        )
    return sorted(ranked, key=_result_sort_key)[:limit]


def query_hybrid_index(roots: StorageRoots, query: str, run_id: str = "starter-fixture", limit: int = 5) -> list[dict[str, object]]:
    search_limit = max(limit * 3, 12)
    keyword_hits = query_keyword_index(roots, query, run_id=run_id, limit=search_limit)
    semantic_hits = query_semantic_index(roots, query, run_id=run_id, limit=search_limit)
    max_keyword = max((float(hit.get("score") or 0.0) for hit in keyword_hits), default=1.0) or 1.0
    by_doc: dict[str, dict[str, object]] = {}
    for hit in keyword_hits:
        doc_id = str(hit.get("doc_id") or "")
        if not doc_id:
            continue
        entry = by_doc.setdefault(doc_id, {**hit, "score_components": {}})
        components = entry["score_components"] if isinstance(entry.get("score_components"), dict) else {}
        components["keyword"] = round(float(hit.get("score") or 0.0) / max_keyword, 6)
        entry["score_components"] = components
    for hit in semantic_hits:
        doc_id = str(hit.get("doc_id") or "")
        if not doc_id:
            continue
        entry = by_doc.setdefault(doc_id, {**hit, "score_components": {}})
        components = entry["score_components"] if isinstance(entry.get("score_components"), dict) else {}
        components["semantic"] = round(float(hit.get("score") or 0.0), 6)
        entry["score_components"] = components
        if hit.get("semantic_provider"):
            entry["semantic_provider"] = hit.get("semantic_provider")
        if not entry.get("snippet"):
            entry["snippet"] = hit.get("snippet")
    ranked = []
    for entry in by_doc.values():
        components = entry.get("score_components") if isinstance(entry.get("score_components"), dict) else {}
        rank_features = _rank_features(entry, tokenize(query))
        keyword_score = float(components.get("keyword") or 0.0)
        semantic_score = float(components.get("semantic") or 0.0)
        if keyword_score <= 0 and semantic_score > 0:
            keyword_fallback = float(rank_features.get("lexical_coverage") or 0.0)
            if keyword_fallback > 0:
                keyword_score = keyword_fallback
                components["keyword_fallback"] = round(keyword_fallback, 6)
        score = (0.45 * keyword_score) + (0.55 * semantic_score)
        components["freshness"] = round(float(rank_features.get("freshness_boost") or 0.0), 6)
        components["authority"] = round(float(rank_features.get("authority_boost") or 0.0), 6)
        components["intent"] = round(float(rank_features.get("intent_boost") or 0.0), 6)
        components["temporal"] = round(float(rank_features.get("temporal_boost") or 0.0), 6)
        components["place"] = round(float(rank_features.get("place_boost") or 0.0), 6)
        components["lexical"] = round(float(rank_features.get("lexical_boost") or 0.0), 6)
        components["provenance"] = round(float(rank_features.get("provenance_boost") or 0.0), 6)
        ranked.append(
            {
                **entry,
                "score": round(score, 6),
                "rank_score": _rank_score(score, rank_features),
                "rank_features": rank_features,
                "score_components": components,
                "score_mode": "hybrid",
            }
        )
    return sorted(ranked, key=_result_sort_key)[:limit]


def portfolio_rank_features(query: str, result: dict[str, object]) -> dict[str, object]:
    """Return a cross-run relevance score that is comparable across sources."""

    alignment = _lexical_alignment_features(result, tokenize(query))
    base_rank_score = max(0.0, min(1.0, float(result.get("rank_score") or result.get("score") or 0.0)))
    score_components = result.get("score_components") if isinstance(result.get("score_components"), dict) else {}
    semantic_score = max(0.0, min(1.0, float(score_components.get("semantic") or 0.0)))
    portfolio_rank_score = round(
        (0.20 * base_rank_score)
        + (0.25 * float(alignment["path_coverage"]))
        + (0.15 * float(alignment["lexical_coverage"]))
        + (0.35 * float(alignment["lexical_proximity"]))
        + (0.05 * semantic_score),
        6,
    )
    confidence = _portfolio_confidence(
        alignment,
        semantic_provider=str(result.get("semantic_provider") or ""),
        semantic_score=semantic_score,
    )
    return {
        **alignment,
        "base_rank_score": round(base_rank_score, 6),
        "semantic_score": round(semantic_score, 6),
        "semantic_provider": str(result.get("semantic_provider") or ""),
        "portfolio_rank_score": portfolio_rank_score,
        "confidence": confidence,
        "confident": confidence in {"high", "medium"},
    }


def graph_neighbors(roots: StorageRoots, node_id: str, run_id: str = "starter-fixture", limit: int = 20) -> dict[str, object]:
    graph_path = run_artifact_dir(roots, run_id) / "graphs" / "course_graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = {str(node["node_id"]): node for node in graph.get("nodes", [])}
    edges = [
        edge
        for edge in graph.get("edges", [])
        if edge.get("from_node") == node_id or edge.get("to_node") == node_id
    ][:limit]
    neighbor_ids = {str(edge.get("from_node")) for edge in edges} | {str(edge.get("to_node")) for edge in edges}
    return {
        "schema": "aoa_course_graph_neighbors_v1",
        "run_id": run_id,
        "node_id": node_id,
        "node": nodes.get(node_id),
        "edges": edges,
        "neighbors": [nodes[item] for item in sorted(neighbor_ids) if item in nodes and item != node_id],
        "temporal_context": _graph_temporal_context(node_id, nodes, graph.get("edges", [])),
    }


def query_index(roots: StorageRoots, query: str, run_id: str = "starter-fixture", limit: int = 5, mode: str = "keyword") -> list[dict[str, object]]:
    if mode == "keyword":
        results = query_keyword_index(roots, query=query, run_id=run_id, limit=limit)
    elif mode == "semantic":
        results = query_semantic_index(roots, query=query, run_id=run_id, limit=limit)
    elif mode == "hybrid":
        results = query_hybrid_index(roots, query=query, run_id=run_id, limit=limit)
    else:
        raise ValueError(f"unsupported query mode: {mode}")
    return _attach_refresh_hints(roots, results, query=query, run_id=run_id, limit=limit, mode=mode)


def render_answer_packet(roots: StorageRoots, query: str, run_id: str = "starter-fixture", limit: int = 5, mode: str = "keyword") -> dict[str, object]:
    results = query_index(roots, query=query, run_id=run_id, limit=limit, mode=mode)
    evidence_chain = []
    seen: set[str] = set()
    for result in results:
        evidence_id = result.get("evidence_id")
        if evidence_id and str(evidence_id) not in seen:
            seen.add(str(evidence_id))
            evidence_chain.append(_evidence_chain_item(result, evidence_id))
    packet = {
        "schema": "aoa_course_answer_packet_v1",
        "run_id": run_id,
        "query": query,
        "mode": mode,
        "generated_at": _now(),
        "result_count": len(results),
        "results": results,
        "evidence_chain": evidence_chain,
        "query_intent_report": _query_intent_report(query, results),
        "freshness_report": {
            "states": sorted({str(result.get("freshness_state") or "unknown") for result in results}),
            "has_source_timestamps": all(result.get("fetched_at") for result in results),
        },
        "temporal_report": _temporal_report(results),
        "authority_report": {
            "tiers": sorted({str(result.get("authority_tier") or "unknown") for result in results}),
        },
        "refresh_report": _refresh_report(results),
    }
    packet["quality"] = summarize_answer_packet(packet)
    return packet


def render_lesson_context_packet(
    roots: StorageRoots,
    query: str,
    run_id: str = "starter-fixture",
    limit: int = 5,
    mode: str = "keyword",
    graph_limit: int = 12,
) -> dict[str, object]:
    answer_packet = render_answer_packet(roots, query=query, run_id=run_id, limit=limit, mode=mode)
    return {
        "schema": "aoa_course_lesson_context_packet_v1",
        "run_id": run_id,
        "query": query,
        "mode": mode,
        "generated_at": answer_packet.get("generated_at"),
        "answer_packet": answer_packet,
        "graph_context": lesson_graph_context(roots, answer_packet, run_id=run_id, graph_limit=graph_limit),
    }


def lesson_graph_context(roots: StorageRoots, packet: dict[str, object], *, run_id: str, graph_limit: int = 12) -> dict[str, object]:
    graph_limit = max(1, int(graph_limit))
    evidence_chain = packet.get("evidence_chain") if isinstance(packet.get("evidence_chain"), list) else []
    contexts: list[dict[str, object]] = []
    seen_nodes: set[str] = set()
    missing: list[dict[str, object]] = []
    for evidence in evidence_chain:
        if not isinstance(evidence, dict):
            continue
        node_id = str(evidence.get("lesson_id") or evidence.get("doc_id") or "")
        if not node_id or node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)
        try:
            graph = graph_neighbors(roots, node_id, run_id, graph_limit)
        except (OSError, json.JSONDecodeError) as exc:
            missing.append(
                {
                    "node_id": node_id,
                    "evidence_id": evidence.get("evidence_id"),
                    "reason": exc.__class__.__name__,
                    "next_command": f"aoa-course build-graph --run {run_id}",
                }
            )
            continue
        context = {
            "node_id": node_id,
            "node_status": "ready" if graph.get("node") else "missing_node",
            "evidence_id": evidence.get("evidence_id"),
            "doc_id": evidence.get("doc_id"),
            "lesson_id": evidence.get("lesson_id"),
            "lesson_title": evidence.get("lesson_title"),
            "graph": graph,
        }
        contexts.append(context)
        if not graph.get("node"):
            missing.append(
                {
                    "node_id": node_id,
                    "evidence_id": evidence.get("evidence_id"),
                    "reason": "missing_node",
                    "next_command": f"aoa-course build-graph --run {run_id}",
                }
            )
    ready_contexts = [item for item in contexts if item.get("node_status") == "ready"]
    status = (
        "partial"
        if ready_contexts and missing
        else "ready"
        if ready_contexts
        else "missing_graph"
        if missing
        else "empty"
    )
    return {
        "schema": "aoa_course_lesson_graph_context_v1",
        "run_id": run_id,
        "graph_limit": graph_limit,
        "status": status,
        "context_count": len(contexts),
        "ready_context_count": len(ready_contexts),
        "contexts": contexts,
        "missing": missing,
    }


def _evidence_chain_item(result: dict[str, object], evidence_id: object) -> dict[str, object]:
    item = {
        "evidence_id": evidence_id,
        "doc_id": result.get("doc_id"),
        "kind": result.get("kind"),
        "source_id": result.get("source_id"),
        "source_url": result.get("source_url"),
        "snippet": result.get("snippet"),
        "fetched_at": result.get("fetched_at"),
        "platform": result.get("platform"),
        "path": result.get("path"),
        "native_item_id": result.get("native_item_id"),
        "item_title": result.get("item_title"),
        "item_url": result.get("item_url"),
        "thread_id": result.get("thread_id"),
        "thread_title": result.get("thread_title"),
        "author_label": result.get("author_label"),
        "posted_at": result.get("posted_at"),
        "download_state": result.get("download_state"),
        "access_state": result.get("access_state"),
        "lesson_id": result.get("lesson_id"),
        "lesson_title": result.get("lesson_title"),
        "freshness_state": result.get("freshness_state"),
        "version_group_id": result.get("version_group_id"),
        "valid_from": result.get("valid_from"),
        "valid_until": result.get("valid_until"),
        "observed_at": result.get("observed_at"),
        "authority_tier": result.get("authority_tier"),
        "authority_label": result.get("authority_label"),
        "source_authority": result.get("source_authority"),
        "score": result.get("score"),
        "rank_score": result.get("rank_score"),
        "rank_features": result.get("rank_features"),
        "refresh_hint": result.get("refresh_hint"),
    }
    return {key: value for key, value in item.items() if value is not None}


def write_answer_packet(packet: dict[str, object], roots: StorageRoots, run_id: str) -> Path:
    output_dir = run_artifact_dir(roots, run_id) / "answers"
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(packet.get("query", "query")).casefold()).strip("-")[:80] or "query"
    path = output_dir / f"{slug}.json"
    path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    return path


def freshness_report(roots: StorageRoots, run_id: str = "starter-fixture") -> dict[str, object]:
    index_path = run_artifact_dir(roots, run_id) / "indexes" / "keyword_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    states: dict[str, int] = {}
    for doc in index.get("docs", []):
        state = str(doc.get("freshness_state") or "unknown")
        states[state] = states.get(state, 0) + 1
    return {"schema": "aoa_course_freshness_report_v1", "run_id": run_id, "states": states}


def _snippet(text: str, terms: list[str]) -> str:
    if not text:
        return ""
    lower = text.casefold()
    positions = [lower.find(term) for term in terms if term and lower.find(term) >= 0]
    start = max(0, min(positions) - 80) if positions else 0
    end = min(len(text), start + 240)
    return text[start:end]


def _graph_temporal_context(node_id: str, nodes: dict[str, dict[str, object]], edges: list[object]) -> dict[str, object]:
    node = nodes.get(node_id) or {}
    version_group_id = str(node.get("version_group_id") or "")
    if node.get("kind") == "version_group":
        version_group_id = node_id
    if not version_group_id:
        return {
            "schema": "aoa_course_graph_temporal_context_v1",
            "status": "not_versioned",
            "node_id": node_id,
            "version_group_id": "",
            "version_count": 0,
            "versions": [],
        }
    if node.get("kind") == "version_group":
        snapshot_ids = {
            str(edge.get("to_node"))
            for edge in edges
            if isinstance(edge, dict)
            and edge.get("from_node") == version_group_id
            and str(edge.get("kind") or "").startswith("version_group_has_")
        }
        versions = [nodes[item] for item in snapshot_ids if item in nodes]
    else:
        versions = [
            item
            for item in nodes.values()
            if str(item.get("version_group_id") or "") == version_group_id and item.get("kind") == node.get("kind")
        ]
    version_items = [_temporal_version_item(item, selected=str(item.get("node_id") or "") == node_id) for item in versions]
    version_items.sort(key=lambda item: (str(item.get("valid_from") or ""), str(item.get("observed_at") or ""), str(item.get("node_id") or "")))
    return {
        "schema": "aoa_course_graph_temporal_context_v1",
        "status": "ready",
        "node_id": node_id,
        "version_group_id": version_group_id,
        "version_count": len(version_items),
        "versions": version_items,
    }


def _temporal_version_item(node: dict[str, object], *, selected: bool) -> dict[str, object]:
    return {
        key: value
        for key, value in {
            "node_id": node.get("node_id"),
            "kind": node.get("kind"),
            "label": node.get("label"),
            "selected": selected,
            "freshness_state": node.get("freshness_state"),
            "valid_from": node.get("valid_from"),
            "valid_until": node.get("valid_until"),
            "observed_at": node.get("observed_at"),
            "indexed_at": node.get("indexed_at"),
            "temporal_state": node.get("temporal_state"),
        }.items()
        if value not in {None, ""}
    }


def _attach_refresh_hints(roots: StorageRoots, results: list[dict[str, object]], *, query: str, run_id: str, limit: int, mode: str) -> list[dict[str, object]]:
    sources_by_id = _registry_sources_by_id(roots)
    return [
        {
            **result,
            "refresh_hint": _refresh_hint(result, sources_by_id=sources_by_id, query=query, run_id=run_id, limit=limit, mode=mode),
        }
        for result in results
    ]


def _registry_sources_by_id(roots: StorageRoots) -> dict[str, dict[str, object]]:
    try:
        registry = load_registry(roots.data)
    except (OSError, json.JSONDecodeError):
        return {}
    sources: dict[str, dict[str, object]] = {}
    for source in registry.get("sources", []):
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("source_id") or "")
        if source_id:
            sources[source_id] = source
    return sources


def _refresh_hint(
    result: dict[str, object],
    *,
    sources_by_id: dict[str, dict[str, object]],
    query: str,
    run_id: str,
    limit: int,
    mode: str,
) -> dict[str, object]:
    source_id = str(result.get("source_id") or "")
    source = sources_by_id.get(source_id) if source_id else None
    platform = str((source or {}).get("platform") or result.get("platform") or "")
    source_ref = str((source or {}).get("source_ref") or result.get("source_url") or "")
    access_mode = str((source or {}).get("access_mode") or _default_access_hint(platform))
    registry_match = source is not None
    local_rebuild_commands = [
        f"aoa-course build-index --run {shlex.quote(run_id)}",
        f"aoa-course build-semantic-index --run {shlex.quote(run_id)}",
        f"aoa-course build-graph --run {shlex.quote(run_id)}",
    ]
    local_query_commands = [
        f"aoa-course answer {shlex.quote(query)} --run {shlex.quote(run_id)} --limit {int(limit)} --mode {shlex.quote(mode)}",
        f"aoa-course lesson-context {shlex.quote(query)} --run {shlex.quote(run_id)} --limit {int(limit)} --mode {shlex.quote(mode)} --graph-limit 12",
        f"aoa-course evidence inspect {shlex.quote(query)} --run {shlex.quote(run_id)} --limit {int(limit)} --mode {shlex.quote(mode)}",
    ]
    source_refresh = _source_refresh_hint(
        source_id=source_id,
        platform=platform,
        source_ref=source_ref,
        access_mode=access_mode,
        registry_match=registry_match,
        query=query,
    )
    return {
        "schema": "aoa_course_refresh_hint_v1",
        "source_id": source_id,
        "platform": platform,
        "source_ref": source_ref,
        "access_mode": access_mode,
        "registry_match": registry_match,
        "local_run": run_id,
        "network_touched": False,
        "local_rebuild_commands": local_rebuild_commands,
        "local_query_commands": local_query_commands,
        "source_refresh": source_refresh,
        "recommended_sequence": _refresh_sequence(source_refresh),
    }


def _source_refresh_hint(
    *,
    source_id: str,
    platform: str,
    source_ref: str,
    access_mode: str,
    registry_match: bool,
    query: str,
) -> dict[str, object]:
    if platform not in LIVE_REFRESH_PLATFORMS:
        return {
            "available": False,
            "reason": "source has no connected live refresh route; update the raw/offline export and rebuild local artifacts",
            "commands_touch_network": False,
            "blocked_by": ["no_connected_live_adapter"],
        }
    preflight_command = f"aoa-course preflight connected-plan --platform {platform} --live-scope bounded{_query_arg(query)}"
    payload: dict[str, object] = {
        "available": True,
        "requires_source_registry": True,
        "registry_match": registry_match,
        "access_mode": access_mode,
        "preflight_command": preflight_command,
        "status_command": f"aoa-course sync status --platform {platform}",
        "commands_touch_network": False,
        "blocked_by": [] if registry_match else ["source_not_found_in_local_registry"],
    }
    if registry_match:
        payload["sync_command"] = _sync_command(platform, access_mode, source_id=source_id)
        payload["commands_touch_network"] = True
        payload["post_sync_rebuild_commands"] = [
            "aoa-course build-index --run <checkpoint-run-id>",
            "aoa-course build-semantic-index --run <checkpoint-run-id>",
            "aoa-course build-graph --run <checkpoint-run-id>",
        ]
        payload["post_sync_guidance"] = (
            "read sync status, pick the synced checkpoint run_id, confirm keyword/semantic/graph artifacts are present, "
            "then rerun answer/lesson-context/evidence_report against that run"
        )
    elif platform in BROWSER_REFRESH_PLATFORMS and source_ref:
        payload["register_command"] = f"aoa-course sources add {shlex.quote(source_ref)} --platform {platform}"
    elif platform == "stepik":
        payload["register_guidance"] = "register the original Stepik course id or course URL, then rerun the connected plan"
    return payload


def _sync_command(platform: str, access_mode: str, *, source_id: str) -> str:
    source_arg = f" --source-id {shlex.quote(source_id)}" if source_id else ""
    if platform in BROWSER_REFRESH_PLATFORMS:
        state_file = f'"{AUTH_ROOT_EXPR}/{platform}/account.storage-state.json"'
        return f"aoa-course sync browser-live --run {platform}-live-sync --platform {platform}{source_arg} --state-file {state_file} --build-artifacts"
    if platform == "stepik":
        command = f"aoa-course sync stepik-live --run stepik-live-sync{source_arg} --build-artifacts"
        if access_mode in {"api_token", "oauth"}:
            command += " --token-env STEPIK_API_TOKEN"
        return command
    return ""


def _refresh_sequence(source_refresh: dict[str, object]) -> list[str]:
    sequence = ["rebuild_local_indexes_and_graph"]
    if not source_refresh.get("available"):
        return sequence
    if not source_refresh.get("registry_match"):
        sequence.insert(0, "register_source_or_recover_source_registry_match")
    sequence.insert(0, "run_connected_source_plan")
    if source_refresh.get("sync_command"):
        sequence.append("sync_live_source_when_preflight_is_ready")
    sequence.append("rerun_answer_lesson_context_or_evidence_report")
    return sequence


def _query_arg(query: str) -> str:
    return f" --query {shlex.quote(query)}" if query else ""


def _default_access_hint(platform: str) -> str:
    if platform in BROWSER_REFRESH_PLATFORMS:
        return "browser_session"
    if platform == "stepik":
        return "public_api"
    if platform == "offline_export":
        return "offline_export"
    return "unknown"


def _refresh_report(results: list[dict[str, object]]) -> dict[str, object]:
    hints = [result.get("refresh_hint") for result in results if isinstance(result.get("refresh_hint"), dict)]
    unique_hints = _unique_refresh_hints(hints)
    local_rebuild_commands: list[str] = []
    local_query_commands: list[str] = []
    source_commands: list[str] = []
    for hint in unique_hints:
        local_rebuild_commands.extend([str(command) for command in hint.get("local_rebuild_commands", []) if command])
        local_query_commands.extend([str(command) for command in hint.get("local_query_commands", []) if command])
        source_refresh = hint.get("source_refresh") if isinstance(hint.get("source_refresh"), dict) else {}
        for key in ["preflight_command", "register_command", "sync_command", "status_command"]:
            command = source_refresh.get(key)
            if command:
                source_commands.append(str(command))
    return {
        "schema": "aoa_course_refresh_report_v1",
        "result_count": len(results),
        "source_count": len(unique_hints),
        "refreshable_source_count": len([hint for hint in unique_hints if _source_refresh(hint).get("available")]),
        "registry_matched_source_count": len([hint for hint in unique_hints if hint.get("registry_match")]),
        "network_touched": False,
        "commands_touch_network": any(bool(_source_refresh(hint).get("commands_touch_network")) for hint in unique_hints),
        "local_rebuild_commands": _dedupe(local_rebuild_commands),
        "local_query_commands": _dedupe(local_query_commands),
        "source_commands": _dedupe(source_commands),
    }


def _unique_refresh_hints(hints: list[object]) -> list[dict[str, object]]:
    by_key: dict[str, dict[str, object]] = {}
    for hint in hints:
        if not isinstance(hint, dict):
            continue
        source_id = str(hint.get("source_id") or "")
        key = f"{source_id}|{hint.get('local_run')}" if source_id else "|".join(
            [
                str(hint.get("platform") or ""),
                str(hint.get("source_ref") or ""),
                str(hint.get("local_run") or ""),
            ]
        )
        by_key.setdefault(key, hint)
    return list(by_key.values())


def _source_refresh(hint: dict[str, object]) -> dict[str, object]:
    return hint.get("source_refresh") if isinstance(hint.get("source_refresh"), dict) else {}


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _rank_features(doc: dict[str, object], query_terms: list[str] | None = None) -> dict[str, object]:
    state = str(doc.get("freshness_state") or "unknown").casefold()
    authority_tier = str(doc.get("authority_tier") or "unknown").casefold()
    source_authority = str(doc.get("source_authority") or "").casefold()
    terms = query_terms or []
    query_intents = _query_intents(terms)
    access_boost = _access_intent_boost(terms, state, authority_tier, source_authority)
    intent_class = _intent_class(query_intents, access_boost=access_boost)
    recency_gate = _recency_gate(intent_class)
    base_freshness_boost = FRESHNESS_RANK_WEIGHTS.get(state, 0.0)
    freshness_boost = round(base_freshness_boost * recency_gate, 6)
    temporal_boost = _temporal_boost(query_intents, state, intent_class=intent_class)
    place_features = _place_features(doc, terms, query_intents)
    lexical_features = _lexical_alignment_features(doc, terms)
    lexical_boost = round(
        (0.34 * float(lexical_features["path_coverage"]))
        + (0.14 * float(lexical_features["lexical_coverage"]))
        + (0.18 * float(lexical_features["lexical_proximity"])),
        6,
    )
    evidence_fields = ["source_id", "source_url", "fetched_at", "evidence_id"]
    provenance_complete = all(doc.get(field) for field in evidence_fields)
    return {
        "freshness_state": state,
        "freshness_boost": freshness_boost,
        "base_freshness_boost": base_freshness_boost,
        "recency_gate": recency_gate,
        "authority_tier": authority_tier,
        "authority_boost": AUTHORITY_RANK_WEIGHTS.get(authority_tier, 0.0),
        "intent_boost": access_boost,
        "intent": _primary_intent(query_intents, access_boost=access_boost),
        "intent_class": intent_class,
        "query_intents": sorted(query_intents),
        "temporal_boost": temporal_boost,
        "access_boost": access_boost,
        **place_features,
        **lexical_features,
        "lexical_boost": lexical_boost,
        "provenance_boost": 0.03 if provenance_complete else 0.0,
        "provenance_complete": provenance_complete,
    }


def _rank_score(score: float, features: dict[str, object]) -> float:
    multiplier = (
        1.0
        + float(features.get("freshness_boost") or 0.0)
        + float(features.get("authority_boost") or 0.0)
        + float(features.get("temporal_boost") or 0.0)
        + float(features.get("place_boost") or 0.0)
        + float(features.get("lexical_boost") or 0.0)
        + float(features.get("provenance_boost") or 0.0)
    )
    adjusted = (score * multiplier) + float(features.get("intent_boost") or 0.0)
    return round(max(0.0, adjusted), 6)


def _query_intent_report(query: str, results: list[dict[str, object]]) -> dict[str, object]:
    intents = _query_intents(tokenize(query))
    access_boost = _top_result_access_boost(results)
    intent_class = _intent_class(intents, access_boost=access_boost)
    return {
        "schema": "aoa_course_query_intent_report_v1",
        "intents": sorted(intents),
        "intent_class": intent_class,
        "temporal_intent": _temporal_intent_label(intent_class, intents),
        "recency_gate": _recency_gate(intent_class),
        "place_intent": "place" in intents,
        "top_result_intent": results[0].get("rank_features", {}).get("intent") if results and isinstance(results[0].get("rank_features"), dict) else "",
        "top_result_intent_class": results[0].get("rank_features", {}).get("intent_class") if results and isinstance(results[0].get("rank_features"), dict) else "",
        "top_result_place_complete": bool(results[0].get("rank_features", {}).get("place_complete")) if results and isinstance(results[0].get("rank_features"), dict) else False,
    }


def _temporal_report(results: list[dict[str, object]]) -> dict[str, object]:
    versioned: dict[str, list[dict[str, object]]] = {}
    timestamped = 0
    for result in results:
        if result.get("observed_at") or result.get("valid_from") or result.get("valid_until") or result.get("fetched_at"):
            timestamped += 1
        group_id = str(result.get("version_group_id") or "")
        if group_id:
            versioned.setdefault(group_id, []).append(result)
    groups = [_temporal_group_item(group_id, items) for group_id, items in sorted(versioned.items())]
    conflict_groups = [
        group
        for group in groups
        if int(group.get("result_count") or 0) > 1
        and (len(group.get("freshness_states", [])) > 1 or len(group.get("valid_from_values", [])) > 1)
    ]
    top = results[0] if results else {}
    return {
        "schema": "aoa_course_temporal_answer_report_v1",
        "result_count": len(results),
        "timestamped_result_count": timestamped,
        "timestamp_coverage": round(timestamped / len(results), 6) if results else 0.0,
        "version_group_count": len(groups),
        "conflict_group_count": len(conflict_groups),
        "conflict_detected": bool(conflict_groups),
        "top_result_version_group_id": top.get("version_group_id") or "",
        "top_result_valid_from": top.get("valid_from") or "",
        "top_result_observed_at": top.get("observed_at") or top.get("fetched_at") or "",
        "groups": groups,
        "conflict_groups": conflict_groups,
    }


def _temporal_group_item(group_id: str, items: list[dict[str, object]]) -> dict[str, object]:
    sorted_items = sorted(
        items,
        key=lambda item: (
            str(item.get("valid_from") or ""),
            str(item.get("observed_at") or item.get("fetched_at") or ""),
            str(item.get("doc_id") or ""),
        ),
    )
    current_states = {"current", "fresh", "verified", "active"}
    stale_states = {"stale", "outdated", "deprecated", "archived"}
    current_doc_ids = [str(item.get("doc_id") or "") for item in sorted_items if str(item.get("freshness_state") or "") in current_states]
    stale_doc_ids = [str(item.get("doc_id") or "") for item in sorted_items if str(item.get("freshness_state") or "") in stale_states]
    observed_values = sorted({str(item.get("observed_at") or item.get("fetched_at") or "") for item in sorted_items if item.get("observed_at") or item.get("fetched_at")})
    valid_from_values = sorted({str(item.get("valid_from") or "") for item in sorted_items if item.get("valid_from")})
    return {
        "version_group_id": group_id,
        "result_count": len(sorted_items),
        "doc_ids": [str(item.get("doc_id") or "") for item in sorted_items],
        "freshness_states": sorted({str(item.get("freshness_state") or "unknown") for item in sorted_items}),
        "current_doc_ids": current_doc_ids,
        "stale_doc_ids": stale_doc_ids,
        "valid_from_values": valid_from_values,
        "observed_at_min": observed_values[0] if observed_values else "",
        "observed_at_max": observed_values[-1] if observed_values else "",
    }


def _query_intents(query_terms: list[str]) -> set[str]:
    terms = set(query_terms)
    intents: set[str] = set()
    if terms & ACCESS_INTENT_TERMS:
        intents.add("access")
    if terms & FRESH_INTENT_TERMS:
        intents.add("fresh")
    if terms & HISTORICAL_INTENT_TERMS:
        intents.add("historical")
    if terms & VERSION_COMPARISON_INTENT_TERMS:
        intents.add("version_comparison")
    if terms & PLACE_INTENT_TERMS:
        intents.add("place")
    if "historical" in intents and "fresh" in intents:
        intents.add("version_comparison")
    return intents


def _primary_intent(query_intents: set[str], *, access_boost: float) -> str:
    if access_boost:
        return "access_state"
    if "version_comparison" in query_intents:
        return "version_comparison"
    if "historical" in query_intents:
        return "historical"
    if "fresh" in query_intents:
        return "fresh"
    if "place" in query_intents:
        return "place"
    return ""


def _intent_class(query_intents: set[str], *, access_boost: float = 0.0) -> str:
    if access_boost:
        return "access_state"
    if "version_comparison" in query_intents:
        return "version_comparison"
    if "historical" in query_intents:
        return "historical_fact"
    if "fresh" in query_intents:
        return "fresh_fact"
    if "place" in query_intents:
        return "place_lookup"
    return "stable_knowledge"


def _recency_gate(intent_class: str) -> float:
    return {
        "fresh_fact": 1.0,
        "access_state": 0.7,
        "version_comparison": 0.6,
        "place_lookup": 0.35,
        "stable_knowledge": 0.25,
        "historical_fact": 0.25,
    }.get(intent_class, 0.25)


def _temporal_intent_label(intent_class: str, query_intents: set[str]) -> str:
    if intent_class == "version_comparison":
        return "version_comparison"
    if intent_class == "historical_fact":
        return "historical"
    if intent_class in {"fresh_fact", "access_state"}:
        return "fresh"
    if "place" in query_intents:
        return "place"
    return "stable"


def _temporal_boost(query_intents: set[str], freshness_state: str, *, intent_class: str) -> float:
    if intent_class == "version_comparison":
        if freshness_state in {"current", "fresh", "verified", "active", "stale", "outdated", "deprecated", "archived"}:
            return 0.08
        return 0.0
    if "historical" in query_intents:
        if freshness_state in {"stale", "outdated", "deprecated", "archived"}:
            return 0.32
        if freshness_state in {"current", "fresh", "verified", "active"}:
            return -0.08
        return 0.0
    if "fresh" in query_intents:
        if freshness_state in {"current", "fresh", "verified", "active"}:
            return 0.16
        if freshness_state in {"stale", "outdated", "deprecated", "archived"}:
            return -0.20
    return 0.0


def _place_features(doc: dict[str, object], query_terms: list[str], query_intents: set[str]) -> dict[str, object]:
    path = doc.get("path") if isinstance(doc.get("path"), list) else []
    place_complete = bool(path) and bool(doc.get("platform")) and bool(doc.get("source_id")) and bool(doc.get("source_url"))
    primary_place_text = " ".join(
        str(part)
        for part in [
            doc.get("course_title"),
            doc.get("module_title"),
            doc.get("lesson_title"),
            doc.get("item_title"),
            doc.get("thread_title"),
            doc.get("author_label"),
            " ".join(str(item) for item in path if item),
        ]
        if part
    )
    secondary_place_text = " ".join(
        str(part)
        for part in [
            doc.get("platform"),
            doc.get("kind"),
            doc.get("lesson_url"),
            doc.get("source_url"),
            doc.get("source_id"),
            doc.get("authority_tier"),
            doc.get("authority_label"),
            doc.get("source_authority"),
            doc.get("item_url"),
            doc.get("posted_at"),
            doc.get("download_state"),
            doc.get("access_state"),
        ]
        if part
    )
    primary_place_terms = set(tokenize(primary_place_text))
    place_terms = primary_place_terms | set(tokenize(secondary_place_text))
    intent_terms = ACCESS_INTENT_TERMS | FRESH_INTENT_TERMS | HISTORICAL_INTENT_TERMS | PLACE_INTENT_TERMS
    meaningful_query_terms = {term for term in query_terms if term not in intent_terms}
    matches = sorted(meaningful_query_terms & place_terms)
    primary_matches = sorted(meaningful_query_terms & primary_place_terms)
    secondary_match_count = len(set(matches) - set(primary_matches))
    if primary_matches:
        path_boost = min(0.55, 0.34 + (0.08 * (len(primary_matches) - 1)) + (0.03 * secondary_match_count))
    elif matches:
        path_boost = min(0.18, 0.06 * len(matches))
    else:
        path_boost = 0.0
    requested_boost = 0.05 if "place" in query_intents and place_complete and matches else 0.0
    return {
        "place_complete": place_complete,
        "place_matches": matches,
        "place_match_count": len(matches),
        "place_primary_matches": primary_matches,
        "place_primary_match_count": len(primary_matches),
        "place_boost": round(path_boost + requested_boost, 6),
    }


def _lexical_alignment_features(doc: dict[str, object], query_terms: list[str]) -> dict[str, object]:
    content_query_terms = _content_query_terms(query_terms)
    path_text = " ".join(
        str(part)
        for part in [
            doc.get("course_title"),
            doc.get("module_title"),
            doc.get("lesson_title"),
            doc.get("item_title"),
            doc.get("thread_title"),
            " ".join(str(item) for item in doc.get("path", []) if item) if isinstance(doc.get("path"), list) else "",
        ]
        if part
    )
    body_text = " ".join(str(part) for part in [path_text, doc.get("text"), doc.get("snippet")] if part)
    path_sequence = _expanded_lexical_sequence(tokenize(path_text))
    body_sequence = _expanded_lexical_sequence(tokenize(body_text))
    path_terms = list(dict.fromkeys(path_sequence))
    body_terms = list(dict.fromkeys(body_sequence))
    path_matches = _matched_query_terms(content_query_terms, path_terms)
    lexical_matches = _matched_query_terms(content_query_terms, body_terms)
    query_term_count = len(content_query_terms)
    lexical_span = _minimum_lexical_span(content_query_terms, body_sequence) if query_term_count and len(lexical_matches) == query_term_count else 0
    return {
        "query_terms": content_query_terms,
        "query_term_count": query_term_count,
        "path_lexical_matches": path_matches,
        "path_lexical_match_count": len(path_matches),
        "path_coverage": _coverage(len(path_matches), query_term_count),
        "lexical_matches": lexical_matches,
        "lexical_match_count": len(lexical_matches),
        "lexical_coverage": _coverage(len(lexical_matches), query_term_count),
        "lexical_span": lexical_span,
        "lexical_proximity": round(query_term_count / lexical_span, 6) if lexical_span and query_term_count else 0.0,
    }


def _content_query_terms(query_terms: list[str]) -> list[str]:
    expanded = _expanded_lexical_terms(query_terms)
    ignored = QUERY_STOP_TERMS | ACCESS_INTENT_TERMS | FRESH_INTENT_TERMS | HISTORICAL_INTENT_TERMS | PLACE_INTENT_TERMS
    return list(dict.fromkeys(term for term in expanded if term not in ignored and len(term) > 1))


def _expanded_lexical_terms(terms: list[str]) -> list[str]:
    return list(dict.fromkeys(_expanded_lexical_sequence(terms)))


def _expanded_lexical_sequence(terms: list[str]) -> list[str]:
    expanded: list[str] = []
    for term in terms:
        normalized = str(term or "").casefold().strip()
        if not normalized:
            continue
        parts = [part for part in LEXICAL_SPLIT_RE.split(normalized) if part]
        expanded.extend(parts if len(parts) > 1 else [normalized])
    return expanded


def _matched_query_terms(query_terms: list[str], document_terms: list[str]) -> list[str]:
    return [query_term for query_term in query_terms if any(_lexical_terms_match(query_term, doc_term) for doc_term in document_terms)]


def _lexical_terms_match(left: str, right: str) -> bool:
    if left == right:
        return True
    if CYRILLIC_TERM_RE.fullmatch(left) and CYRILLIC_TERM_RE.fullmatch(right) and min(len(left), len(right)) >= 5:
        left_stem = _russian_stem(left)
        right_stem = _russian_stem(right)
        if left_stem == right_stem:
            return True
        common_prefix = 0
        for left_char, right_char in zip(left_stem, right_stem):
            if left_char != right_char:
                break
            common_prefix += 1
        return common_prefix >= 5
    if left.isascii() and right.isascii() and min(len(left), len(right)) >= 4:
        return left.rstrip("s") == right.rstrip("s")
    return False


def _russian_stem(term: str) -> str:
    for suffix in RUSSIAN_INFLECTION_SUFFIXES:
        if term.endswith(suffix) and len(term) - len(suffix) >= 4:
            return term[: -len(suffix)]
    return term


def _minimum_lexical_span(query_terms: list[str], document_terms: list[str]) -> int:
    if not query_terms or not document_terms:
        return 0
    counts = [0] * len(query_terms)
    covered = 0
    left_event = 0
    minimum = 0
    events: list[tuple[int, list[int]]] = []
    for right, document_term in enumerate(document_terms):
        matches = [index for index, query_term in enumerate(query_terms) if _lexical_terms_match(query_term, document_term)]
        if not matches:
            continue
        events.append((right, matches))
        for index in matches:
            if counts[index] == 0:
                covered += 1
            counts[index] += 1
        while covered == len(query_terms) and left_event < len(events):
            left_position, left_matches = events[left_event]
            span = right - left_position + 1
            minimum = span if minimum == 0 else min(minimum, span)
            for index in left_matches:
                counts[index] -= 1
                if counts[index] == 0:
                    covered -= 1
            left_event += 1
    return minimum


def _portfolio_confidence(alignment: dict[str, object], *, semantic_provider: str, semantic_score: float) -> str:
    path_coverage = float(alignment.get("path_coverage") or 0.0)
    lexical_coverage = float(alignment.get("lexical_coverage") or 0.0)
    lexical_proximity = float(alignment.get("lexical_proximity") or 0.0)
    match_count = int(alignment.get("lexical_match_count") or 0)
    if (path_coverage >= 0.66 and match_count >= 2) or (lexical_coverage >= 1.0 and match_count >= 2 and lexical_proximity >= 0.35):
        return "high"
    if path_coverage >= 0.34 or lexical_coverage >= 0.66:
        return "medium"
    if semantic_provider and semantic_provider != LOCAL_HASHING_PROVIDER and semantic_score >= 0.60:
        return "medium"
    if match_count > 0 or semantic_score >= 0.35:
        return "low"
    return "none"


def _coverage(matches: int, total: int) -> float:
    return round(matches / total, 6) if total else 0.0


def _access_intent_boost(query_terms: list[str], freshness_state: str, authority_tier: str, source_authority: str) -> float:
    if not (set(query_terms) & ACCESS_INTENT_TERMS):
        return 0.0
    if freshness_state == "access_denied" or authority_tier == "access_notice" or source_authority == "browser_access_denied":
        return 0.65
    return 0.0


def _top_result_access_boost(results: list[dict[str, object]]) -> float:
    for result in results[:1]:
        features = result.get("rank_features") if isinstance(result, dict) else {}
        if isinstance(features, dict):
            return float(features.get("access_boost") or 0.0)
    return 0.0


def _result_sort_key(item: dict[str, object]) -> tuple[float, float, str]:
    rank_score = float(item.get("rank_score") or item.get("score") or 0.0)
    score = float(item.get("score") or 0.0)
    return (-rank_score, -score, str(item.get("doc_id") or ""))


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
