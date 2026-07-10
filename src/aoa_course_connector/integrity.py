"""Cross-artifact integrity and bounded retrieval-recall audits."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from hashlib import blake2b
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.index import LOCAL_HASHING_PROVIDER, tokenize
from aoa_course_connector.query import query_hybrid_index, query_keyword_index, query_semantic_index
from aoa_course_connector.storage import run_artifact_dir, run_data_dir


PROBE_FILLER_TERMS = {"это", "the", "and", "или", "для"}
PROBE_METADATA_TERMS = {
    "asset",
    "available",
    "document",
    "file",
    "img",
    "metadata_only",
    "step",
    "stepik",
    "video",
}


def audit_run_artifacts(
    roots: StorageRoots,
    run_id: str,
    *,
    probe_limit: int = 0,
    recall_k: int = 5,
    mode: str = "hybrid",
    min_recall: float = 1.0,
) -> dict[str, object]:
    artifact_dir = run_artifact_dir(roots, run_id)
    paths = {
        "normalized_bundle": run_data_dir(roots, run_id) / "normalized" / "course_bundle.json",
        "keyword_index": artifact_dir / "indexes" / "keyword_index.json",
        "semantic_index": artifact_dir / "indexes" / "semantic_index.json",
        "course_graph": artifact_dir / "graphs" / "course_graph.json",
    }
    loaded = {name: _load_json(path) for name, path in paths.items()}
    bundle = loaded["normalized_bundle"][0]
    keyword = loaded["keyword_index"][0]
    semantic = loaded["semantic_index"][0]
    graph = loaded["course_graph"][0]
    inventory = _canonical_inventory(bundle, run_id=run_id)

    keyword_docs = [doc for doc in keyword.get("docs", []) if isinstance(doc, dict)]
    semantic_docs = [doc for doc in semantic.get("docs", []) if isinstance(doc, dict)]
    graph_nodes = [node for node in graph.get("nodes", []) if isinstance(node, dict)]
    graph_edges = [edge for edge in graph.get("edges", []) if isinstance(edge, dict)]
    keyword_ids = [str(doc.get("doc_id") or "") for doc in keyword_docs if doc.get("doc_id")]
    semantic_ids = [str(doc.get("doc_id") or "") for doc in semantic_docs if doc.get("doc_id")]
    graph_id_list = [str(node.get("node_id") or "") for node in graph_nodes if node.get("node_id")]
    graph_edge_ids = [str(edge.get("edge_id") or "") for edge in graph_edges if edge.get("edge_id")]
    graph_ids = set(graph_id_list)
    expected_index_ids = inventory["index_doc_ids"]
    expected_graph_ids = inventory["graph_node_ids"]
    evidence_ids = inventory["evidence_ids"]
    keyword_id_set = set(keyword_ids)
    semantic_id_set = set(semantic_ids)

    missing_keyword = sorted(expected_index_ids - keyword_id_set)
    unexpected_keyword = sorted(keyword_id_set - expected_index_ids)
    duplicate_keyword = sorted(doc_id for doc_id, count in Counter(keyword_ids).items() if count > 1)
    missing_semantic = sorted(keyword_id_set - semantic_id_set)
    unexpected_semantic = sorted(semantic_id_set - keyword_id_set)
    duplicate_semantic = sorted(doc_id for doc_id, count in Counter(semantic_ids).items() if count > 1)
    keyword_scoring_issues = _keyword_scoring_issues(keyword, keyword_docs)
    invalid_vectors = _invalid_semantic_vectors(semantic_docs, semantic)
    missing_graph = sorted(expected_graph_ids - graph_ids)
    duplicate_graph_nodes = sorted(node_id for node_id, count in Counter(graph_id_list).items() if count > 1)
    duplicate_graph_edges = sorted(edge_id for edge_id, count in Counter(graph_edge_ids).items() if count > 1)
    dangling_edges = [
        str(edge.get("edge_id") or f"{edge.get('from_node')}->{edge.get('to_node')}")
        for edge in graph_edges
        if str(edge.get("from_node") or "") not in graph_ids
        or str(edge.get("to_node") or "") not in graph_ids
    ]
    invalid_evidence_docs = sorted(
        str(doc.get("doc_id") or "")
        for doc in keyword_docs
        if not doc.get("evidence_id") or str(doc.get("evidence_id")) not in evidence_ids
    )
    posting_doc_ids, invalid_posting_refs = _inverted_inventory(keyword)
    lexically_unretrievable = sorted(keyword_id_set - posting_doc_ids)

    failures: list[dict[str, object]] = []
    for surface, (_payload, load_error) in loaded.items():
        if load_error:
            failures.append({"surface": surface, "count": 1, "error": load_error})
    metadata_failures = _artifact_metadata_failures(
        run_id,
        bundle,
        keyword,
        semantic,
        graph,
        keyword_docs,
        semantic_docs,
        graph_nodes,
        graph_edges,
    )
    failures.extend(metadata_failures)
    _append_failure(failures, "keyword_docs", missing_keyword, unexpected_keyword, duplicate_keyword)
    _append_failure(failures, "semantic_docs", missing_semantic, unexpected_semantic, duplicate_semantic)
    if keyword_scoring_issues:
        failures.append(_failure("keyword_scoring", keyword_scoring_issues))
    if invalid_vectors:
        failures.append(_failure("semantic_vectors", invalid_vectors))
    if missing_graph:
        failures.append(_failure("graph_nodes", missing_graph))
    if duplicate_graph_nodes:
        failures.append(_failure("graph_node_duplicates", duplicate_graph_nodes))
    if duplicate_graph_edges:
        failures.append(_failure("graph_edge_duplicates", duplicate_graph_edges))
    if dangling_edges:
        failures.append(_failure("graph_edges", dangling_edges))
    if invalid_evidence_docs:
        failures.append(_failure("evidence", invalid_evidence_docs))
    if invalid_posting_refs:
        failures.append(_failure("inverted_postings", invalid_posting_refs))
    if lexically_unretrievable:
        failures.append(_failure("lexical_retrievability", lexically_unretrievable))

    probes = _run_probes(
        roots,
        run_id,
        inventory["probe_docs"],
        semantic_provider=str(semantic.get("provider") or ""),
        probe_limit=max(0, probe_limit),
        recall_k=max(1, recall_k),
        mode=mode,
    )
    if probe_limit > 0 and (int(probes["evaluated_count"]) == 0 or float(probes["recall_at_k"]) < min_recall):
        failures.append(
            {
                "surface": "retrieval_probes",
                "count": max(1, int(probes["miss_count"])),
                "min_recall": min_recall,
                "actual_recall": probes["recall_at_k"],
                "samples": [item.get("doc_id") for item in probes["misses"][:10]],
            }
        )

    counts = {
        "expected_index_doc_count": len(expected_index_ids),
        "keyword_doc_count": len(keyword_ids),
        "semantic_doc_count": len(semantic_ids),
        "expected_graph_node_count": len(expected_graph_ids),
        "graph_node_count": len(graph_ids),
        "graph_edge_count": len(graph_edges),
        "evidence_count": len(evidence_ids),
    }
    return {
        "schema": "aoa_course_artifact_integrity_v1",
        "status": "ok" if not failures else "error",
        "run_id": run_id,
        "network_touched": False,
        "counts": counts,
        "integrity": {
            "keyword_coverage": _coverage(len(expected_index_ids) - len(missing_keyword), len(expected_index_ids)),
            "semantic_alignment": _coverage(len(keyword_id_set) - len(missing_semantic), len(keyword_id_set)),
            "graph_coverage": _coverage(len(expected_graph_ids) - len(missing_graph), len(expected_graph_ids)),
            "evidence_attribution": _coverage(len(keyword_ids) - len(invalid_evidence_docs), len(keyword_ids)),
            "lexical_retrievability": _coverage(len(keyword_id_set) - len(lexically_unretrievable), len(keyword_id_set)),
            "semantic_vector_coverage": _coverage(len(semantic_ids) - len(invalid_vectors), len(semantic_ids)),
            "bm25_contract": 1.0 if not keyword_scoring_issues else 0.0,
            "dangling_graph_edge_count": len(dangling_edges),
            "invalid_inverted_posting_count": len(invalid_posting_refs),
        },
        "missing": {
            "keyword_doc_ids": missing_keyword,
            "semantic_doc_ids": missing_semantic,
            "graph_node_ids": missing_graph,
            "evidence_doc_ids": invalid_evidence_docs,
            "lexically_unretrievable_doc_ids": lexically_unretrievable,
        },
        "unexpected": {
            "keyword_doc_ids": unexpected_keyword,
            "semantic_doc_ids": unexpected_semantic,
        },
        "probes": probes,
        "failures": failures,
    }


def _canonical_inventory(bundle: dict[str, object], *, run_id: str) -> dict[str, object]:
    index_doc_ids: set[str] = set()
    graph_node_ids: set[str] = set()
    probe_docs: list[dict[str, str]] = []
    evidence_ids = {
        str(item.get("evidence_id"))
        for item in bundle.get("evidence", [])
        if isinstance(item, dict) and item.get("evidence_id")
    }
    source = bundle.get("source") if isinstance(bundle.get("source"), dict) else {}
    graph_node_ids.add(str(source.get("source_id") or f"source:{run_id}"))
    for course in bundle.get("courses", []):
        if not isinstance(course, dict):
            continue
        _add_id(graph_node_ids, course.get("course_id"))
        progress = course.get("progress") if isinstance(course.get("progress"), dict) else {}
        if progress:
            progress_id = str(progress.get("progress_id") or f"{course.get('course_id')}:progress")
            graph_node_ids.add(progress_id)
            _add_probe_doc(
                index_doc_ids,
                probe_docs,
                "progress",
                progress_id,
                " ".join(str(progress.get(key) or "") for key in ["state", "percent", "label", "updated_at"]),
                str(course.get("title") or ""),
                str(course.get("title") or ""),
                "course_id",
                str(course.get("course_id") or ""),
            )
        for module in course.get("modules", []):
            if not isinstance(module, dict):
                continue
            _add_id(graph_node_ids, module.get("module_id"))
            for lesson in module.get("lessons", []):
                if not isinstance(lesson, dict):
                    continue
                _add_id(graph_node_ids, lesson.get("lesson_id"))
                context = " ".join(
                    str(value or "")
                    for value in [course.get("title"), module.get("title"), lesson.get("title")]
                )
                lesson_id = str(lesson.get("lesson_id") or "")
                place_text = str(lesson.get("title") or "")
                _inventory_items(lesson, "steps", "step_id", "step", ["text"], context, place_text, lesson_id, index_doc_ids, graph_node_ids, probe_docs)
                _inventory_items(lesson, "assets", "asset_id", "asset", ["title", "kind", "download_state"], context, place_text, lesson_id, index_doc_ids, graph_node_ids, probe_docs)
                _inventory_items(lesson, "transcripts", "transcript_id", "transcript", ["title", "language", "text"], context, place_text, lesson_id, index_doc_ids, graph_node_ids, probe_docs)
                _inventory_items(lesson, "assignments", "assignment_id", "assignment", ["title", "prompt"], context, place_text, lesson_id, index_doc_ids, graph_node_ids, probe_docs)
                for thread in lesson.get("comment_threads", []):
                    if not isinstance(thread, dict):
                        continue
                    _add_id(graph_node_ids, thread.get("thread_id"))
                    thread_context = f"{context} {thread.get('title') or ''}"
                    _inventory_items(thread, "comments", "comment_id", "comment", ["author_label", "author_role", "text"], thread_context, place_text, lesson_id, index_doc_ids, graph_node_ids, probe_docs)
                for topic in lesson.get("topics", []):
                    graph_node_ids.add(f"topic:{str(topic).casefold()}")
                for entity in lesson.get("entities", []):
                    if isinstance(entity, dict):
                        _add_id(graph_node_ids, entity.get("entity_id"))
    return {
        "index_doc_ids": index_doc_ids,
        "graph_node_ids": graph_node_ids,
        "evidence_ids": evidence_ids,
        "probe_docs": probe_docs,
    }


def _inventory_items(
    parent: dict[str, object],
    collection: str,
    id_field: str,
    kind: str,
    text_fields: list[str],
    context: str,
    place_text: str,
    lesson_id: str,
    index_doc_ids: set[str],
    graph_node_ids: set[str],
    probe_docs: list[dict[str, str]],
) -> None:
    for item in parent.get(collection, []):
        if not isinstance(item, dict) or not item.get(id_field):
            continue
        item_id = str(item[id_field])
        graph_node_ids.add(item_id)
        item_text = " ".join(str(item.get(field) or "") for field in text_fields)
        _add_probe_doc(index_doc_ids, probe_docs, kind, item_id, item_text, context, place_text, "lesson_id", lesson_id)


def _add_probe_doc(
    index_doc_ids: set[str],
    probe_docs: list[dict[str, str]],
    kind: str,
    item_id: str,
    item_text: str,
    context_text: str,
    place_text: str,
    place_field: str,
    place_id: str,
) -> None:
    doc_id = f"{kind}:{item_id}"
    index_doc_ids.add(doc_id)
    probe_docs.append(
        {
            "doc_id": doc_id,
            "kind": kind,
            "item_text": item_text,
            "context_text": context_text,
            "place_text": place_text,
            "place_field": place_field,
            "place_id": place_id,
        }
    )


def _inverted_inventory(keyword: dict[str, object]) -> tuple[set[str], list[str]]:
    valid_doc_ids = {
        str(doc.get("doc_id"))
        for doc in keyword.get("docs", [])
        if isinstance(doc, dict) and doc.get("doc_id")
    }
    posting_doc_ids: set[str] = set()
    invalid_refs: list[str] = []
    inverted = keyword.get("inverted") if isinstance(keyword.get("inverted"), dict) else {}
    for term, postings in inverted.items():
        if not isinstance(postings, list):
            continue
        for posting in postings:
            if not isinstance(posting, dict) or not posting.get("doc_id"):
                continue
            doc_id = str(posting["doc_id"])
            if doc_id not in valid_doc_ids:
                invalid_refs.append(f"{term}:{doc_id}")
                continue
            posting_doc_ids.add(doc_id)
    return posting_doc_ids, sorted(invalid_refs)


def _run_probes(
    roots: StorageRoots,
    run_id: str,
    docs: object,
    *,
    semantic_provider: str,
    probe_limit: int,
    recall_k: int,
    mode: str,
) -> dict[str, object]:
    if probe_limit <= 0:
        return _empty_probe_report(mode, recall_k, probe_limit, status="not_requested")
    if mode in {"semantic", "hybrid"} and semantic_provider != LOCAL_HASHING_PROVIDER:
        return {
            **_empty_probe_report(mode, recall_k, probe_limit, status="unavailable"),
            "reason": "external_semantic_provider_requires_network",
        }
    probe_docs = [doc for doc in docs if isinstance(doc, dict)] if isinstance(docs, list) else []
    candidates = _canonical_probe_candidates(probe_docs)
    selected = _stratified_probes(candidates, probe_limit)
    misses = []
    place_hits = 0
    exact_hits = 0
    native_id_hits = 0
    hierarchy_path_hits = 0
    query_error_count = 0
    for doc, query in selected:
        try:
            results = _query_for_mode(roots, run_id, query, mode=mode, limit=recall_k)
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            query_error_count += 1
            results = []
        result_ids = [str(result.get("doc_id") or "") for result in results]
        doc_id = str(doc.get("doc_id") or "")
        exact_hit = doc_id in result_ids
        place_field = str(doc.get("place_field") or "")
        place_id = str(doc.get("place_id") or "")
        native_id_hit = bool(
            place_field
            and place_id
            and any(str(result.get(place_field) or "") == place_id for result in results)
        )
        hierarchy_path_hit = any(_same_canonical_place(doc, result) for result in results)
        place_hit = exact_hit or native_id_hit or hierarchy_path_hit
        if exact_hit:
            exact_hits += 1
        if native_id_hit:
            native_id_hits += 1
        if hierarchy_path_hit:
            hierarchy_path_hits += 1
        if place_hit:
            place_hits += 1
        else:
            misses.append({"doc_id": doc_id, "kind": doc.get("kind"), "top_doc_ids": result_ids})
    evaluated = len(selected)
    return {
        "status": "ok" if evaluated else "unavailable",
        "mode": mode,
        "k": recall_k,
        "requested_limit": probe_limit,
        "evaluated_count": evaluated,
        "hit_count": place_hits,
        "exact_hit_count": exact_hits,
        "place_hit_count": place_hits,
        "native_id_hit_count": native_id_hits,
        "hierarchy_path_hit_count": hierarchy_path_hits,
        "miss_count": len(misses),
        "query_error_count": query_error_count,
        "recall_at_k": _coverage(place_hits, evaluated),
        "exact_recall_at_k": _coverage(exact_hits, evaluated),
        "place_grounded_recall_at_k": _coverage(place_hits, evaluated),
        "relevance_contract": "exact_doc_or_native_id_or_hierarchy_path_v2",
        "misses": misses,
    }


def _same_canonical_place(probe: dict[str, object], result: dict[str, object]) -> bool:
    expected = tuple(tokenize(str(probe.get("context_text") or "")))
    path = result.get("path") if isinstance(result.get("path"), list) else []
    native_parts = []
    for item in path:
        part = str(item or "").strip()
        if not part:
            continue
        if ":" in part and not any(character.isspace() for character in part):
            continue
        native_parts.append(part)
        if len(native_parts) >= 3:
            break
    actual = tuple(tokenize(" ".join(native_parts)))
    return bool(expected and actual and expected == actual)


def _canonical_probe_candidates(
    docs: list[dict[str, object]],
) -> list[tuple[dict[str, object], str]]:
    tokens_by_doc: dict[str, tuple[set[str], set[str]]] = {}
    document_frequency: Counter[str] = Counter()
    for doc in docs:
        doc_id = str(doc.get("doc_id") or "")
        item_terms = _probe_terms(str(doc.get("item_text") or ""))
        context_terms = _probe_terms(str(doc.get("context_text") or ""))
        if not doc_id:
            continue
        tokens_by_doc[doc_id] = (item_terms, context_terms)
        document_frequency.update(item_terms | context_terms)
    candidates = []
    for doc in docs:
        doc_id = str(doc.get("doc_id") or "")
        item_terms, context_terms = tokens_by_doc.get(doc_id, (set(), set()))
        meaningful_item_terms = item_terms - PROBE_FILLER_TERMS - PROBE_METADATA_TERMS
        context_text = str(doc.get("context_text") or "")
        native_place_text = str(doc.get("place_text") or "")
        native_place_terms = _probe_terms(native_place_text) - PROBE_FILLER_TERMS
        context_place_terms = context_terms - native_place_terms - PROBE_FILLER_TERMS
        context_query = _ordered_probe_query(
            context_text,
            context_place_terms,
            document_frequency,
            max_terms=3,
        )
        native_place_query = _ordered_probe_query(
            native_place_text,
            native_place_terms,
            document_frequency,
            max_terms=6,
        )
        place_query = " ".join(part for part in [context_query, native_place_query] if part)
        if meaningful_item_terms:
            item_query = _ordered_probe_query(
                str(doc.get("item_text") or ""),
                meaningful_item_terms,
                document_frequency,
                max_terms=3,
            )
            query = " ".join(part for part in [item_query, place_query] if part)
        else:
            query = place_query or _ordered_probe_query(
                context_text,
                context_terms - PROBE_FILLER_TERMS,
                document_frequency,
                max_terms=4,
            )
        if doc_id and query:
            candidates.append((doc, query))
    return candidates


def _probe_terms(text: str) -> set[str]:
    return {term for term in tokenize(text) if len(term) > 2 and not term.isdigit()}


def _ordered_probe_query(
    text: str,
    allowed_terms: set[str],
    document_frequency: Counter[str],
    *,
    max_terms: int,
) -> str:
    ordered = list(dict.fromkeys(term for term in tokenize(text) if term in allowed_terms))
    selected = set(
        sorted(ordered, key=lambda term: (document_frequency[term], -len(term), term))[:max_terms]
    )
    return " ".join(term for term in ordered if term in selected)


def _empty_probe_report(mode: str, recall_k: int, probe_limit: int, *, status: str) -> dict[str, object]:
    return {
        "status": status,
        "mode": mode,
        "k": recall_k,
        "requested_limit": probe_limit,
        "evaluated_count": 0,
        "hit_count": 0,
        "exact_hit_count": 0,
        "place_hit_count": 0,
        "native_id_hit_count": 0,
        "hierarchy_path_hit_count": 0,
        "miss_count": 0,
        "query_error_count": 0,
        "recall_at_k": 0.0,
        "exact_recall_at_k": 0.0,
        "place_grounded_recall_at_k": 0.0,
        "relevance_contract": "exact_doc_or_native_id_or_hierarchy_path_v2",
        "misses": [],
    }


def _stratified_probes(candidates: list[tuple[dict[str, object], str]], limit: int) -> list[tuple[dict[str, object], str]]:
    groups: dict[str, list[tuple[dict[str, object], str]]] = defaultdict(list)
    for candidate in sorted(
        candidates,
        key=lambda item: (
            str(item[0].get("kind") or ""),
            blake2b(str(item[0].get("doc_id") or "").encode("utf-8"), digest_size=8).hexdigest(),
        ),
    ):
        groups[str(candidate[0].get("kind") or "unknown")].append(candidate)
    selected = []
    while groups and len(selected) < limit:
        for kind in sorted(list(groups)):
            selected.append(groups[kind].pop(0))
            if not groups[kind]:
                del groups[kind]
            if len(selected) >= limit:
                break
    return selected


def _query_for_mode(roots: StorageRoots, run_id: str, query: str, *, mode: str, limit: int) -> list[dict[str, object]]:
    if mode == "keyword":
        return query_keyword_index(roots, query, run_id=run_id, limit=limit)
    if mode == "semantic":
        return query_semantic_index(roots, query, run_id=run_id, limit=limit)
    if mode == "hybrid":
        return query_hybrid_index(roots, query, run_id=run_id, limit=limit)
    raise ValueError(f"unsupported integrity probe mode: {mode}")


def _artifact_metadata_failures(
    run_id: str,
    bundle: dict[str, object],
    keyword: dict[str, object],
    semantic: dict[str, object],
    graph: dict[str, object],
    keyword_docs: list[dict[str, object]],
    semantic_docs: list[dict[str, object]],
    graph_nodes: list[dict[str, object]],
    graph_edges: list[dict[str, object]],
) -> list[dict[str, object]]:
    expectations = [
        ("normalized_bundle", bundle, "aoa_course_normalized_bundle_v1", None, None),
        ("keyword_index", keyword, "aoa_course_keyword_index_v1", "doc_count", len(keyword_docs)),
        ("semantic_index", semantic, "aoa_course_semantic_index_v1", "doc_count", len(semantic_docs)),
        ("course_graph", graph, "aoa_course_graph_v1", "node_count", len(graph_nodes)),
        ("course_graph", graph, "aoa_course_graph_v1", "edge_count", len(graph_edges)),
    ]
    failures = []
    for surface, payload, schema, count_field, actual_count in expectations:
        fields = []
        if payload.get("schema") != schema:
            fields.append("schema")
        if surface != "normalized_bundle" and payload.get("run_id") != run_id:
            fields.append("run_id")
        if count_field and _safe_int(payload.get(count_field), default=-1) != actual_count:
            fields.append(count_field)
        if fields:
            failures.append({"surface": f"{surface}_metadata", "count": len(fields), "fields": fields})
    return failures


def _invalid_semantic_vectors(
    docs: list[dict[str, object]],
    semantic: dict[str, object],
) -> list[str]:
    dimensions = _safe_int(semantic.get("dimensions"), default=0)
    invalid = []
    for doc in docs:
        doc_id = str(doc.get("doc_id") or "")
        vector = doc.get("vector")
        if not doc_id or not isinstance(vector, list) or not vector or dimensions <= 0:
            if doc_id:
                invalid.append(doc_id)
            continue
        indexes = []
        vector_valid = True
        for item in vector:
            if not isinstance(item, dict):
                vector_valid = False
                break
            index = _safe_int(item.get("i"), default=-1)
            try:
                weight = float(item.get("w"))
            except (TypeError, ValueError):
                vector_valid = False
                break
            if index < 0 or index >= dimensions or not math.isfinite(weight) or weight == 0:
                vector_valid = False
                break
            indexes.append(index)
        if not vector_valid or len(indexes) != len(set(indexes)):
            invalid.append(doc_id)
    return sorted(invalid)


def _keyword_scoring_issues(
    keyword: dict[str, object],
    docs: list[dict[str, object]],
) -> list[str]:
    scoring = keyword.get("scoring") if isinstance(keyword.get("scoring"), dict) else {}
    issues = []
    if scoring.get("schema") != "aoa_course_bm25_scoring_v1":
        issues.append("schema")
    if scoring.get("algorithm") != "bm25":
        issues.append("algorithm")
    try:
        k1 = float(scoring.get("k1"))
        b = float(scoring.get("b"))
        avg_document_length = float(scoring.get("avg_document_length"))
    except (TypeError, ValueError):
        issues.append("parameters")
        k1, b, avg_document_length = 0.0, -1.0, -1.0
    if k1 <= 0 or not 0 <= b <= 1 or avg_document_length < 0:
        issues.append("parameter_range")
    if scoring.get("document_length_field") != "keyword_token_count":
        issues.append("document_length_field")
    if scoring.get("document_length_basis") != "body_text_tokens":
        issues.append("document_length_basis")
    if scoring.get("query_stopword_policy") != "drop_when_content_terms_exist":
        issues.append("query_stopword_policy")
    if scoring.get("query_stop_terms_version") != "aoa_course_query_stop_terms_v1":
        issues.append("query_stop_terms_version")
    lengths = []
    for doc in docs:
        length = _safe_int(doc.get("keyword_token_count"), default=-1)
        if length <= 0:
            issues.append(f"document_length:{doc.get('doc_id') or 'unknown'}")
        else:
            lengths.append(length)
    expected_average = round(sum(lengths) / len(lengths), 6) if lengths else 0.0
    if lengths and not math.isclose(avg_document_length, expected_average, rel_tol=0.0, abs_tol=0.000001):
        issues.append("avg_document_length")
    return sorted(set(issues))


def _safe_int(value: object, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _append_failure(
    failures: list[dict[str, object]],
    surface: str,
    missing: list[str],
    unexpected: list[str],
    duplicates: list[str],
) -> None:
    items = [*missing, *unexpected, *duplicates]
    if items:
        failures.append(
            {
                "surface": surface,
                "count": len(items),
                "missing_count": len(missing),
                "unexpected_count": len(unexpected),
                "duplicate_count": len(duplicates),
                "samples": items[:10],
            }
        )


def _failure(surface: str, items: list[str]) -> dict[str, object]:
    return {"surface": surface, "count": len(items), "samples": items[:10]}


def _add_id(target: set[str], value: object) -> None:
    if value:
        target.add(str(value))


def _coverage(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 1.0


def _load_json(path: Path) -> tuple[dict[str, object], str]:
    if not path.is_file():
        return {}, "missing_file"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"unreadable_json:{type(exc).__name__}"
    if not isinstance(payload, dict):
        return {}, "json_root_not_object"
    return payload, ""
