"""Query and answer-packet helpers."""

from __future__ import annotations

import json
import shlex
from datetime import UTC, datetime
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.index import (
    LOCAL_HASHING_PROVIDER,
    semantic_doc_feature_keys,
    semantic_query_feature_keys,
    sparse_vector_from_json,
    tokenize,
    vector_dot,
    vectorize_semantic_query,
)
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
}


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
        rank_features = _rank_features(doc)
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
    query_terms = tokenize(query)
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
        rank_features = _rank_features(result)
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
        if not entry.get("snippet"):
            entry["snippet"] = hit.get("snippet")
    ranked = []
    for entry in by_doc.values():
        components = entry.get("score_components") if isinstance(entry.get("score_components"), dict) else {}
        keyword_score = float(components.get("keyword") or 0.0)
        semantic_score = float(components.get("semantic") or 0.0)
        score = (0.45 * keyword_score) + (0.55 * semantic_score)
        rank_features = _rank_features(entry)
        components["freshness"] = round(float(rank_features.get("freshness_boost") or 0.0), 6)
        components["authority"] = round(float(rank_features.get("authority_boost") or 0.0), 6)
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
        results = query_keyword_index(roots, query=query, run_id=run_id, limit=limit)
    elif mode == "semantic":
        results = query_semantic_index(roots, query=query, run_id=run_id, limit=limit)
    elif mode == "hybrid":
        results = query_hybrid_index(roots, query=query, run_id=run_id, limit=limit)
    else:
        raise ValueError(f"unsupported query mode: {mode}")
    return _attach_refresh_hints(roots, results, query=query, run_id=run_id)


def render_answer_packet(roots: StorageRoots, query: str, run_id: str = "starter-fixture", limit: int = 5, mode: str = "keyword") -> dict[str, object]:
    results = query_index(roots, query=query, run_id=run_id, limit=limit, mode=mode)
    evidence_chain = []
    seen: set[str] = set()
    for result in results:
        evidence_id = result.get("evidence_id")
        if evidence_id and str(evidence_id) not in seen:
            seen.add(str(evidence_id))
            evidence_chain.append(_evidence_chain_item(result, evidence_id))
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
        "authority_report": {
            "tiers": sorted({str(result.get("authority_tier") or "unknown") for result in results}),
        },
        "refresh_report": _refresh_report(results),
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
        "lesson_id": result.get("lesson_id"),
        "lesson_title": result.get("lesson_title"),
        "freshness_state": result.get("freshness_state"),
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


def _attach_refresh_hints(roots: StorageRoots, results: list[dict[str, object]], *, query: str, run_id: str) -> list[dict[str, object]]:
    sources_by_id = _registry_sources_by_id(roots)
    return [
        {
            **result,
            "refresh_hint": _refresh_hint(result, sources_by_id=sources_by_id, query=query, run_id=run_id),
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
            "aoa-course build-semantic-index --run <checkpoint-run-id>",
        ]
        payload["post_sync_guidance"] = (
            "read sync status, pick the synced checkpoint run_id, rebuild the semantic index for semantic/hybrid queries, "
            "then rerun answer/evidence_report against that run"
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
    sequence.append("rerun_answer_or_evidence_report")
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
    source_commands: list[str] = []
    for hint in unique_hints:
        local_rebuild_commands.extend([str(command) for command in hint.get("local_rebuild_commands", []) if command])
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


def _rank_features(doc: dict[str, object]) -> dict[str, object]:
    state = str(doc.get("freshness_state") or "unknown").casefold()
    authority_tier = str(doc.get("authority_tier") or "unknown").casefold()
    evidence_fields = ["source_id", "source_url", "fetched_at", "evidence_id"]
    provenance_complete = all(doc.get(field) for field in evidence_fields)
    return {
        "freshness_state": state,
        "freshness_boost": FRESHNESS_RANK_WEIGHTS.get(state, 0.0),
        "authority_tier": authority_tier,
        "authority_boost": AUTHORITY_RANK_WEIGHTS.get(authority_tier, 0.0),
        "provenance_boost": 0.03 if provenance_complete else 0.0,
        "provenance_complete": provenance_complete,
    }


def _rank_score(score: float, features: dict[str, object]) -> float:
    multiplier = (
        1.0
        + float(features.get("freshness_boost") or 0.0)
        + float(features.get("authority_boost") or 0.0)
        + float(features.get("provenance_boost") or 0.0)
    )
    return round(max(0.0, score * multiplier), 6)


def _result_sort_key(item: dict[str, object]) -> tuple[float, float, str]:
    rank_score = float(item.get("rank_score") or item.get("score") or 0.0)
    score = float(item.get("score") or 0.0)
    return (-rank_score, -score, str(item.get("doc_id") or ""))


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
