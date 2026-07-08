"""Deterministic local keyword index for normalized course content."""

from __future__ import annotations

import json
import math
import os
import re
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from hashlib import blake2b
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.storage import run_artifact_dir, run_data_dir


TOKEN_RE = re.compile(r"[\w.+#/-]+", re.UNICODE)
DEFAULT_VECTOR_DIMENSIONS = 256
LOCAL_HASHING_PROVIDER = "local_hashing_v1"
HTTP_JSON_PROVIDER = "http_json_v1"
KNOWN_AUTHORITY_TIERS = {
    "official_lesson",
    "official_assignment",
    "instructor_comment",
    "mentor_comment",
    "learner_comment",
    "transcript",
    "asset_metadata",
    "discovered_link",
    "access_notice",
    "progress_metadata",
    "discussion_comment",
    "unknown",
}


def build_keyword_index(roots: StorageRoots, run_id: str = "starter-fixture") -> Path:
    bundle_path = run_data_dir(roots, run_id) / "normalized" / "course_bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    docs = list(_iter_docs(bundle))
    inverted: dict[str, list[dict[str, object]]] = defaultdict(list)
    for doc in docs:
        counts = Counter(tokenize(_keyword_text_for_doc(doc)))
        for term, count in sorted(counts.items()):
            inverted[term].append({"doc_id": doc["doc_id"], "count": count})
    output_dir = run_artifact_dir(roots, run_id) / "indexes"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "keyword_index.json"
    payload = {
        "schema": "aoa_course_keyword_index_v1",
        "run_id": run_id,
        "built_at": _now(),
        "unit": "course_knowledge_item",
        "doc_count": len(docs),
        "term_count": len(inverted),
        "docs": docs,
        "inverted": dict(inverted),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def build_semantic_index(
    roots: StorageRoots,
    run_id: str = "starter-fixture",
    *,
    dimensions: int = DEFAULT_VECTOR_DIMENSIONS,
    provider: str = LOCAL_HASHING_PROVIDER,
    embedding_endpoint: str | None = None,
    embedding_model: str | None = None,
    embedding_token_env: str | None = None,
    embedding_batch_size: int = 32,
    embedding_timeout_seconds: float = 30.0,
) -> Path:
    bundle_path = run_data_dir(roots, run_id) / "normalized" / "course_bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    source_docs = list(_iter_docs(bundle))
    provider_config = _provider_config(
        provider,
        dimensions=max(8, dimensions),
        embedding_endpoint=embedding_endpoint,
        embedding_model=embedding_model,
        embedding_token_env=embedding_token_env,
        embedding_batch_size=embedding_batch_size,
        embedding_timeout_seconds=embedding_timeout_seconds,
    )
    docs, resolved_dimensions = _semantic_docs_with_vectors(source_docs, provider_config)
    output_dir = run_artifact_dir(roots, run_id) / "indexes"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "semantic_index.json"
    payload = {
        "schema": "aoa_course_semantic_index_v1",
        "run_id": run_id,
        "built_at": _now(),
        "unit": "course_knowledge_item",
        "provider": provider_config["provider"],
        "provider_config": _public_provider_config(provider_config),
        "dimensions": resolved_dimensions,
        "feature_contract": _feature_contract(str(provider_config["provider"])),
        "doc_count": len(docs),
        "docs": docs,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text) if token.strip()]


def vectorize_semantic_query(
    query: str,
    *,
    dimensions: int = DEFAULT_VECTOR_DIMENSIONS,
    provider: str = LOCAL_HASHING_PROVIDER,
    provider_config: dict[str, object] | None = None,
) -> dict[str, float]:
    if not query.strip():
        return {}
    if provider == HTTP_JSON_PROVIDER:
        config = {**(provider_config or {}), "provider": HTTP_JSON_PROVIDER, "dimensions": dimensions}
        vectors = _embed_http_json([query], config)
        if vectors and len(vectors[0]) != dimensions:
            raise ValueError(f"embedding endpoint returned {len(vectors[0])}-dimension query vector for {dimensions}-dimension index")
        return _normalize_dense(vectors[0]) if vectors else {}
    features = _weighted_text_features(query, weight=1.0)
    return _normalize(_hash_features(features, dimensions=max(8, dimensions)))


def semantic_query_feature_keys(query: str) -> set[str]:
    return _feature_keys(_weighted_text_features(query, weight=1.0))


def semantic_doc_feature_keys(doc: dict[str, object]) -> set[str]:
    return _feature_keys(_semantic_features_for_doc(doc))


def vector_dot(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(weight * right.get(index, 0.0) for index, weight in left.items())


def sparse_vector_from_json(items: object) -> dict[str, float]:
    if not isinstance(items, list):
        return {}
    vector: dict[str, float] = {}
    for item in items:
        if isinstance(item, dict) and item.get("i") is not None:
            vector[str(item["i"])] = float(item.get("w") or 0.0)
    return vector


def _provider_config(
    provider: str,
    *,
    dimensions: int,
    embedding_endpoint: str | None,
    embedding_model: str | None,
    embedding_token_env: str | None,
    embedding_batch_size: int,
    embedding_timeout_seconds: float,
) -> dict[str, object]:
    if provider == LOCAL_HASHING_PROVIDER:
        return {"provider": LOCAL_HASHING_PROVIDER, "dimensions": dimensions}
    if provider == HTTP_JSON_PROVIDER:
        if not embedding_endpoint:
            raise ValueError("http_json_v1 semantic provider requires --embedding-endpoint")
        batch_size = max(1, int(embedding_batch_size or 1))
        token_env = str(embedding_token_env or "")
        return {
            "provider": HTTP_JSON_PROVIDER,
            "endpoint": str(embedding_endpoint),
            "model": str(embedding_model or ""),
            "token_env": token_env,
            "batch_size": batch_size,
            "timeout_seconds": float(embedding_timeout_seconds or 30.0),
            "request_schema": "json_input_array_v1",
            "response_schema": "data_embedding_or_embeddings_array_v1",
        }
    raise ValueError(f"unsupported semantic provider: {provider}")


def _public_provider_config(config: dict[str, object]) -> dict[str, object]:
    provider = str(config.get("provider") or "")
    if provider == LOCAL_HASHING_PROVIDER:
        return {"provider": LOCAL_HASHING_PROVIDER, "dimensions": config.get("dimensions")}
    if provider == HTTP_JSON_PROVIDER:
        return {
            "provider": HTTP_JSON_PROVIDER,
            "endpoint": config.get("endpoint"),
            "model": config.get("model"),
            "token_env": config.get("token_env"),
            "token_env_configured": bool(config.get("token_env")),
            "batch_size": config.get("batch_size"),
            "timeout_seconds": config.get("timeout_seconds"),
            "request_schema": config.get("request_schema"),
            "response_schema": config.get("response_schema"),
            "secret_values_logged": False,
        }
    return {"provider": provider}


def _feature_contract(provider: str) -> dict[str, object]:
    if provider == HTTP_JSON_PROVIDER:
        return {
            "external_embedding_vectors": True,
            "normalized_sparse_vectors": True,
            "query_uses_same_provider": True,
            "secret_values_logged": False,
            "collision_guard": "provider_vector_space",
        }
    return {
        "text_tokens": True,
        "title_path_tokens": True,
        "adjacent_bigrams": True,
        "kind_platform_features": True,
        "authority_tier_features": True,
        "normalized_sparse_vectors": True,
    }


def _semantic_docs_with_vectors(docs: list[dict[str, object]], config: dict[str, object]) -> tuple[list[dict[str, object]], int]:
    provider = str(config.get("provider") or LOCAL_HASHING_PROVIDER)
    if provider == HTTP_JSON_PROVIDER:
        vectors = _embed_http_json([_embedding_text_for_doc(doc) for doc in docs], config)
        dimensions = len(vectors[0]) if vectors else int(config.get("dimensions") or DEFAULT_VECTOR_DIMENSIONS)
        for vector in vectors:
            if len(vector) != dimensions:
                raise ValueError("embedding endpoint returned vectors with inconsistent dimensions")
        return [
            {**doc, "vector": _serialize_vector(_normalize_dense(vector))}
            for doc, vector in zip(docs, vectors)
        ], dimensions
    dimensions = int(config.get("dimensions") or DEFAULT_VECTOR_DIMENSIONS)
    return [
        {**doc, "vector": _serialize_vector(_semantic_vector_for_doc(doc, dimensions=max(8, dimensions)))}
        for doc in docs
    ], max(8, dimensions)


def _embedding_text_for_doc(doc: dict[str, object]) -> str:
    return " ".join(
        str(part)
        for part in [
            doc.get("course_title"),
            doc.get("module_title"),
            doc.get("lesson_title"),
            " ".join(str(item) for item in doc.get("path", []) if item) if isinstance(doc.get("path"), list) else "",
            doc.get("kind"),
            doc.get("platform"),
            doc.get("authority_tier"),
            doc.get("authority_label"),
            doc.get("source_authority"),
            doc.get("item_title"),
            doc.get("item_url"),
            doc.get("thread_title"),
            doc.get("author_label"),
            doc.get("access_state"),
            doc.get("download_state"),
            doc.get("text"),
        ]
        if part
    )


def _keyword_text_for_doc(doc: dict[str, object]) -> str:
    path_text = " ".join(str(item) for item in doc.get("path", []) if item) if isinstance(doc.get("path"), list) else ""
    return " ".join(
        str(part)
        for part in [
            doc.get("course_title"),
            doc.get("module_title"),
            doc.get("lesson_title"),
            path_text,
            doc.get("platform"),
            doc.get("kind"),
            doc.get("authority_tier"),
            doc.get("authority_label"),
            doc.get("source_authority"),
            doc.get("item_title"),
            doc.get("item_url"),
            doc.get("thread_title"),
            doc.get("author_label"),
            doc.get("access_state"),
            doc.get("download_state"),
            doc.get("text"),
        ]
        if part
    )


def _embed_http_json(texts: list[str], config: dict[str, object]) -> list[list[float]]:
    endpoint = str(config.get("endpoint") or "")
    if not endpoint:
        raise ValueError("http_json_v1 semantic provider requires endpoint in index provider_config")
    batch_size = max(1, int(config.get("batch_size") or 1))
    timeout = float(config.get("timeout_seconds") or 30.0)
    token_env = str(config.get("token_env") or "")
    token = os.environ.get(token_env) if token_env else ""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        payload: dict[str, object] = {"input": batch}
        model = str(config.get("model") or "")
        if model:
            payload["model"] = model
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-configured endpoint.
            body = json.loads(response.read().decode("utf-8"))
        batch_vectors = _vectors_from_http_response(body)
        if len(batch_vectors) != len(batch):
            raise ValueError(f"embedding endpoint returned {len(batch_vectors)} vectors for {len(batch)} inputs")
        vectors.extend(batch_vectors)
    return vectors


def _vectors_from_http_response(body: object) -> list[list[float]]:
    if not isinstance(body, dict):
        raise ValueError("embedding endpoint returned non-object JSON")
    data = body.get("data")
    if isinstance(data, list):
        return [_coerce_dense_vector(item.get("embedding") if isinstance(item, dict) else item) for item in data]
    embeddings = body.get("embeddings")
    if isinstance(embeddings, list):
        return [_coerce_dense_vector(item) for item in embeddings]
    raise ValueError("embedding endpoint response missing data[].embedding or embeddings[]")


def _coerce_dense_vector(value: object) -> list[float]:
    if not isinstance(value, list):
        raise ValueError("embedding value is not an array")
    vector = [float(item) for item in value]
    if not vector:
        raise ValueError("embedding vector is empty")
    if not all(math.isfinite(item) for item in vector):
        raise ValueError("embedding vector contains non-finite values")
    return vector


def _normalize_dense(values: list[float]) -> dict[str, float]:
    return _normalize({str(index): value for index, value in enumerate(values) if value})


def _iter_docs(bundle: dict[str, object]) -> list[dict[str, object]]:
    docs: list[dict[str, object]] = []
    for course in bundle.get("courses", []):
        if not isinstance(course, dict):
            continue
        course_path = [str(course.get("title") or course.get("course_id"))]
        progress = course.get("progress")
        if isinstance(progress, dict):
            progress_text = " ".join(
                str(progress.get(key) or "")
                for key in ["state", "percent", "label", "updated_at"]
            )
            docs.append(_course_doc("progress", progress.get("progress_id"), progress_text, course, course_path, progress.get("evidence")))
        for module in course.get("modules", []):
            if not isinstance(module, dict):
                continue
            module_path = [*course_path, str(module.get("title") or module.get("module_id"))]
            for lesson in module.get("lessons", []):
                if not isinstance(lesson, dict):
                    continue
                lesson_path = [*module_path, str(lesson.get("title") or lesson.get("lesson_id"))]
                lesson_evidence = lesson.get("evidence", {}) if isinstance(lesson.get("evidence"), dict) else {}
                for step in lesson.get("steps", []):
                    if isinstance(step, dict):
                        docs.append(_doc("step", step.get("step_id"), step.get("text"), course, module, lesson, lesson_path, step.get("evidence") or lesson_evidence, step))
                for transcript in lesson.get("transcripts", []):
                    if isinstance(transcript, dict):
                        transcript_label = str(transcript.get("title") or transcript.get("language") or transcript.get("transcript_id") or "transcript")
                        docs.append(
                            _doc(
                                "transcript",
                                transcript.get("transcript_id"),
                                transcript.get("text"),
                                course,
                                module,
                                lesson,
                                [*lesson_path, transcript_label],
                                transcript.get("evidence") or lesson_evidence,
                                transcript,
                            )
                        )
                for assignment in lesson.get("assignments", []):
                    if isinstance(assignment, dict):
                        assignment_label = str(assignment.get("title") or assignment.get("assignment_id") or "assignment")
                        docs.append(_doc("assignment", assignment.get("assignment_id"), assignment.get("prompt"), course, module, lesson, [*lesson_path, assignment_label], assignment.get("evidence") or lesson_evidence, assignment))
                for thread in lesson.get("comment_threads", []):
                    if not isinstance(thread, dict):
                        continue
                    thread_label = str(thread.get("title") or thread.get("thread_id") or "comment_thread")
                    for comment in thread.get("comments", []):
                        if isinstance(comment, dict):
                            comment_label = str(comment.get("author_label") or comment.get("author_role") or comment.get("author") or comment.get("comment_id") or "comment")
                            docs.append(
                                _doc(
                                    "comment",
                                    comment.get("comment_id"),
                                    comment.get("text"),
                                    course,
                                    module,
                                    lesson,
                                    [*lesson_path, thread_label, comment_label],
                                    comment.get("evidence") or lesson_evidence,
                                    comment,
                                    place_context={"thread_id": thread.get("thread_id"), "thread_title": thread_label},
                                )
                            )
                for asset in lesson.get("assets", []):
                    if isinstance(asset, dict):
                        text = f"{asset.get('title', '')} {asset.get('kind', '')} {asset.get('download_state', '')}"
                        asset_label = str(asset.get("title") or asset.get("asset_id") or "asset")
                        docs.append(
                            _doc(
                                "asset",
                                asset.get("asset_id"),
                                text,
                                course,
                                module,
                                lesson,
                                [*lesson_path, asset_label],
                                asset.get("evidence") or lesson_evidence,
                                asset,
                                place_context={"item_title": asset_label, "item_url": asset.get("url")},
                            )
                        )
    return docs


def _semantic_vector_for_doc(doc: dict[str, object], *, dimensions: int) -> dict[str, float]:
    return _normalize(_hash_features(_semantic_features_for_doc(doc), dimensions=dimensions))


def _semantic_features_for_doc(doc: dict[str, object]) -> list[tuple[str, float]]:
    features: list[tuple[str, float]] = []
    features.extend(_weighted_text_features(str(doc.get("text") or ""), weight=1.0))
    title_path_text = " ".join(
        str(doc.get(key) or "")
        for key in ["course_title", "module_title", "lesson_title"]
    )
    path_text = " ".join(str(item) for item in doc.get("path", []) if item) if isinstance(doc.get("path"), list) else ""
    features.extend(_weighted_text_features(f"{title_path_text} {path_text}", weight=1.6))
    native_place_text = " ".join(
        str(doc.get(key) or "")
        for key in [
            "authority_label",
            "source_authority",
            "item_title",
            "item_url",
            "thread_title",
            "author_label",
            "access_state",
            "download_state",
        ]
    )
    features.extend(_weighted_text_features(native_place_text, weight=1.3))
    for key in ["kind", "platform", "authority_tier", "source_authority"]:
        value = str(doc.get(key) or "").casefold()
        if value:
            features.append((f"{key}:{value}", 2.0))
    return features


def _feature_keys(features: list[tuple[str, float]]) -> set[str]:
    return {feature for feature, _weight in features if feature}


def _weighted_text_features(text: str, *, weight: float) -> list[tuple[str, float]]:
    tokens = tokenize(text)
    features = [(token, weight) for token in tokens]
    features.extend((f"{left}_{right}", weight * 1.25) for left, right in zip(tokens, tokens[1:]))
    return features


def _hash_features(features: list[tuple[str, float]], *, dimensions: int) -> dict[str, float]:
    vector: dict[str, float] = {}
    for feature, weight in features:
        if not feature:
            continue
        digest = blake2b(feature.encode("utf-8"), digest_size=8).digest()
        index = str(int.from_bytes(digest, "big") % dimensions)
        vector[index] = vector.get(index, 0.0) + weight
    return vector


def _normalize(vector: dict[str, float]) -> dict[str, float]:
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if not norm:
        return {}
    return {index: value / norm for index, value in sorted(vector.items(), key=lambda item: int(item[0]))}


def _serialize_vector(vector: dict[str, float]) -> list[dict[str, object]]:
    return [{"i": int(index), "w": round(weight, 6)} for index, weight in vector.items() if weight]


def _course_doc(kind: str, item_id: object, text: object, course: dict[str, object], path: list[str], evidence: object) -> dict[str, object]:
    evidence_dict = evidence if isinstance(evidence, dict) else {}
    progress = course.get("progress") if isinstance(course.get("progress"), dict) else {}
    doc_id = f"{kind}:{item_id}"
    return {
        "doc_id": doc_id,
        "kind": kind,
        "course_id": course.get("course_id"),
        "source_id": course.get("source_id"),
        "course_title": course.get("title"),
        "module_id": "",
        "module_title": "",
        "lesson_id": "",
        "lesson_title": "",
        "lesson_url": course.get("url"),
        "path": path,
        "text": str(text or ""),
        "tokens": len(tokenize(str(text or ""))),
        "platform": course.get("platform"),
        "freshness_state": "current",
        "authority_tier": "progress_metadata",
        "authority_label": "",
        "version_group_id": progress.get("version_group_id") or course.get("version_group_id") or "",
        "valid_from": progress.get("valid_from") or course.get("valid_from") or "",
        "valid_until": progress.get("valid_until") or course.get("valid_until") or "",
        "observed_at": progress.get("observed_at") or progress.get("updated_at") or evidence_dict.get("fetched_at"),
        "source_url": evidence_dict.get("source_url") or course.get("url"),
        "fetched_at": evidence_dict.get("fetched_at"),
        "evidence_id": evidence_dict.get("evidence_id"),
    }


def _doc(
    kind: str,
    item_id: object,
    text: object,
    course: dict[str, object],
    module: dict[str, object],
    lesson: dict[str, object],
    path: list[str],
    evidence: object,
    source_item: dict[str, object] | None = None,
    place_context: dict[str, object] | None = None,
) -> dict[str, object]:
    evidence_dict = evidence if isinstance(evidence, dict) else {}
    item = source_item or {}
    place_context = place_context or {}
    doc_id = f"{kind}:{item_id}"
    item_title = item.get("title") or place_context.get("item_title") or ""
    item_url = item.get("url") or place_context.get("item_url") or ""
    author_label = str(item.get("author_label") or item.get("author_role") or item.get("author") or item.get("role") or "")
    return {
        "doc_id": doc_id,
        "kind": kind,
        "native_item_id": item_id,
        "item_title": item_title,
        "item_url": item_url,
        "thread_id": place_context.get("thread_id") or "",
        "thread_title": place_context.get("thread_title") or "",
        "author_label": author_label,
        "posted_at": item.get("posted_at") or "",
        "download_state": item.get("download_state") or "",
        "access_state": item.get("access_state") or lesson.get("access_state") or "",
        "course_id": course.get("course_id"),
        "source_id": course.get("source_id"),
        "course_title": course.get("title"),
        "module_id": module.get("module_id"),
        "module_title": module.get("title"),
        "lesson_id": lesson.get("lesson_id"),
        "lesson_title": lesson.get("title"),
        "lesson_url": lesson.get("url"),
        "path": path,
        "text": str(text or ""),
        "tokens": len(tokenize(str(text or ""))),
        "platform": course.get("platform"),
        "freshness_state": lesson.get("freshness_state", "unknown"),
        "authority_tier": _authority_tier(kind, item),
        "authority_label": str(item.get("authority_label") or author_label),
        "source_authority": str(item.get("source_authority") or ""),
        "version_group_id": item.get("version_group_id") or lesson.get("version_group_id") or "",
        "valid_from": item.get("valid_from") or lesson.get("valid_from") or "",
        "valid_until": item.get("valid_until") or lesson.get("valid_until") or "",
        "observed_at": item.get("observed_at") or lesson.get("observed_at") or evidence_dict.get("fetched_at"),
        "source_url": evidence_dict.get("source_url") or lesson.get("url"),
        "fetched_at": evidence_dict.get("fetched_at"),
        "evidence_id": evidence_dict.get("evidence_id"),
    }


def _authority_tier(kind: str, item: dict[str, object]) -> str:
    explicit = str(item.get("authority_tier") or "").casefold()
    if explicit in KNOWN_AUTHORITY_TIERS:
        return explicit
    if kind == "step":
        return "official_lesson"
    if kind == "assignment":
        return "official_assignment"
    if kind == "transcript":
        return "transcript"
    if kind == "asset":
        return "asset_metadata"
    if kind == "progress":
        return "progress_metadata"
    if kind == "comment":
        label = str(item.get("authority_label") or item.get("author_label") or item.get("role") or "").casefold()
        if any(token in label for token in ["instructor", "teacher", "coach", "admin", "staff"]):
            return "instructor_comment"
        if any(token in label for token in ["mentor", "tutor"]):
            return "mentor_comment"
        if any(token in label for token in ["learner", "student", "member", "user"]):
            return "learner_comment"
        return "discussion_comment"
    return "unknown"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
