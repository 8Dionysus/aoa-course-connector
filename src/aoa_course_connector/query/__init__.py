"""Query and answer-packet helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.index import tokenize
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


def render_answer_packet(roots: StorageRoots, query: str, run_id: str = "starter-fixture", limit: int = 5) -> dict[str, object]:
    results = query_keyword_index(roots, query=query, run_id=run_id, limit=limit)
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
