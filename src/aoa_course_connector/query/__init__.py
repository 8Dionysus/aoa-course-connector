"""Query and answer-packet helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.index import (
    semantic_doc_feature_keys,
    semantic_query_feature_keys,
    sparse_vector_from_json,
    tokenize,
    vector_dot,
    vectorize_semantic_query,
)
from aoa_course_connector.storage import run_artifact_dir


def query_keyword_index(roots: StorageRoots, query: str, run_id: str = "starter-fixture", limit: int = 5) -> list[dict[str, object]]:
    index_path = run_artifact_dir(roots, run_id) / "indexes" / "keyword_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    docs = {str(doc["doc_id"]): doc for doc in index.get("docs", [])}
    query_terms = tokenize(query)
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
        ranked.append({**doc, "score": score, "snippet": _snippet(str(doc.get("text") or ""), query_terms)})
    return ranked[:limit]


def query_semantic_index(roots: StorageRoots, query: str, run_id: str = "starter-fixture", limit: int = 5) -> list[dict[str, object]]:
    index_path = run_artifact_dir(roots, run_id) / "indexes" / "semantic_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    dimensions = int(index.get("dimensions") or 256)
    query_vector = vectorize_semantic_query(query, dimensions=dimensions)
    query_features = semantic_query_feature_keys(query)
    if not query_vector or not query_features:
        return []
    query_terms = tokenize(query)
    ranked = []
    for doc in index.get("docs", []):
        if not isinstance(doc, dict):
            continue
        vector = sparse_vector_from_json(doc.get("vector"))
        score = vector_dot(query_vector, vector)
        if score <= 0:
            continue
        if not (query_features & semantic_doc_feature_keys(doc)):
            continue
        result = {key: value for key, value in doc.items() if key != "vector"}
        ranked.append(
            {
                **result,
                "score": round(score, 6),
                "score_mode": "semantic_vector",
                "snippet": _snippet(str(doc.get("text") or ""), query_terms),
            }
        )
    return sorted(ranked, key=lambda item: (-float(item["score"]), str(item.get("doc_id"))))[:limit]


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
        if not entry.get("snippet"):
            entry["snippet"] = hit.get("snippet")
    ranked = []
    for entry in by_doc.values():
        components = entry.get("score_components") if isinstance(entry.get("score_components"), dict) else {}
        keyword_score = float(components.get("keyword") or 0.0)
        semantic_score = float(components.get("semantic") or 0.0)
        score = (0.45 * keyword_score) + (0.55 * semantic_score)
        ranked.append({**entry, "score": round(score, 6), "score_mode": "hybrid"})
    return sorted(ranked, key=lambda item: (-float(item["score"]), str(item.get("doc_id"))))[:limit]


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
    }


def query_index(roots: StorageRoots, query: str, run_id: str = "starter-fixture", limit: int = 5, mode: str = "keyword") -> list[dict[str, object]]:
    if mode == "keyword":
        return query_keyword_index(roots, query=query, run_id=run_id, limit=limit)
    if mode == "semantic":
        return query_semantic_index(roots, query=query, run_id=run_id, limit=limit)
    if mode == "hybrid":
        return query_hybrid_index(roots, query=query, run_id=run_id, limit=limit)
    raise ValueError(f"unsupported query mode: {mode}")


def render_answer_packet(roots: StorageRoots, query: str, run_id: str = "starter-fixture", limit: int = 5, mode: str = "keyword") -> dict[str, object]:
    results = query_index(roots, query=query, run_id=run_id, limit=limit, mode=mode)
    evidence_chain = []
    seen: set[str] = set()
    for result in results:
        evidence_id = result.get("evidence_id")
        if evidence_id and str(evidence_id) not in seen:
            seen.add(str(evidence_id))
            evidence_chain.append(
                {
                    "evidence_id": evidence_id,
                    "source_url": result.get("source_url"),
                    "fetched_at": result.get("fetched_at"),
                    "platform": result.get("platform"),
                    "path": result.get("path"),
                }
            )
    return {
        "schema": "aoa_course_answer_packet_v1",
        "run_id": run_id,
        "query": query,
        "mode": mode,
        "generated_at": _now(),
        "result_count": len(results),
        "results": results,
        "evidence_chain": evidence_chain,
        "freshness_report": {
            "states": sorted({str(result.get("freshness_state") or "unknown") for result in results}),
            "has_source_timestamps": all(result.get("fetched_at") for result in results),
        },
    }


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


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
