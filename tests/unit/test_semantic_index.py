from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.graph import build_graph
from aoa_course_connector.index import HTTP_JSON_PROVIDER, build_keyword_index, build_semantic_index, query_lookup_tokens
from aoa_course_connector.ingest import materialize_fixture
from aoa_course_connector.mcp.server import call_tool
from aoa_course_connector.query import query_hybrid_index, query_keyword_index, query_semantic_index, render_answer_packet


REPO_ROOT = Path(__file__).resolve().parents[2]


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_semantic_index_builds_local_vector_artifact(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="starter-fixture")
    path = build_semantic_index(storage, run_id="starter-fixture", dimensions=64)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "aoa_course_semantic_index_v1"
    assert payload["provider"] == "local_hashing_v1"
    assert payload["provider_config"]["provider"] == "local_hashing_v1"
    assert payload["dimensions"] == 64
    assert payload["feature_contract"]["authority_tier_features"] is True
    assert payload["doc_count"] >= 1
    assert payload["docs"][0]["vector"]


def test_keyword_index_records_tokenizer_contract_and_queries_legacy_terms(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="starter-fixture")
    path = build_keyword_index(storage, run_id="starter-fixture")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["feature_contract"]["tokenizer_contract"] == "course_tokenizer_v2_strip_edge_punctuation"
    assert "course_tokenizer_v1_raw_regex" in payload["feature_contract"]["legacy_query_tokenizer_compatibility"]
    assert payload["scoring"]["schema"] == "aoa_course_bm25_scoring_v1"
    assert payload["scoring"]["algorithm"] == "bm25"
    assert payload["scoring"]["k1"] == 1.2
    assert payload["scoring"]["b"] == 0.75
    assert payload["scoring"]["avg_document_length"] > 0
    assert payload["scoring"]["document_length_basis"] == "body_text_tokens"
    assert payload["scoring"]["query_stopword_policy"] == "drop_when_content_terms_exist"
    assert payload["scoring"]["query_stop_terms_version"] == "aoa_course_query_stop_terms_v1"
    assert all(doc["keyword_token_count"] > 0 for doc in payload["docs"])
    assert query_lookup_tokens("C#.") == ["c#", "c#."]


def test_bm25_prefers_short_exact_document_over_long_tf_heavy_document(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    index_path = storage.artifact / "runs/bm25/indexes/keyword_index.json"
    index_path.parent.mkdir(parents=True)
    docs = [
        {"doc_id": "target", "text": "specific target", "keyword_token_count": 2},
        {"doc_id": "long", "text": "specific target", "keyword_token_count": 1000},
        *[
            {"doc_id": f"background:{index}", "text": "background", "keyword_token_count": 2}
            for index in range(18)
        ],
    ]
    index_path.write_text(
        json.dumps(
            {
                "schema": "aoa_course_keyword_index_v1",
                "run_id": "bm25",
                "doc_count": len(docs),
                "docs": docs,
                "inverted": {
                    "specific": [{"doc_id": "target", "count": 1}, {"doc_id": "long", "count": 20}],
                    "target": [{"doc_id": "target", "count": 1}, {"doc_id": "long", "count": 20}],
                },
                "scoring": {
                    "schema": "aoa_course_bm25_scoring_v1",
                    "algorithm": "bm25",
                    "k1": 1.2,
                    "b": 0.75,
                    "avg_document_length": 51.9,
                    "document_length_field": "keyword_token_count",
                    "document_length_basis": "body_text_tokens",
                    "query_stopword_policy": "drop_when_content_terms_exist",
                    "query_stop_terms_version": "aoa_course_query_stop_terms_v1",
                },
            }
        ),
        encoding="utf-8",
    )

    results = query_keyword_index(storage, "specific target", run_id="bm25", limit=2)

    assert [result["doc_id"] for result in results] == ["target", "long"]
    assert results[0]["score_mode"] == "bm25"
    assert results[0]["score"] > results[1]["score"]


def test_bm25_drops_stopwords_when_content_terms_exist(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    index_path = storage.artifact / "runs/bm25-stopwords/indexes/keyword_index.json"
    index_path.parent.mkdir(parents=True)
    docs = [
        {"doc_id": "target", "text": "привязать telegram к профилю", "keyword_token_count": 4},
        {"doc_id": "noise", "text": "как как как как", "keyword_token_count": 4},
    ]
    index_path.write_text(
        json.dumps(
            {
                "schema": "aoa_course_keyword_index_v1",
                "run_id": "bm25-stopwords",
                "doc_count": len(docs),
                "docs": docs,
                "inverted": {
                    "как": [{"doc_id": "noise", "count": 4}],
                    "привязать": [{"doc_id": "target", "count": 1}],
                    "telegram": [{"doc_id": "target", "count": 1}],
                    "профилю": [{"doc_id": "target", "count": 1}],
                },
                "scoring": {
                    "schema": "aoa_course_bm25_scoring_v1",
                    "algorithm": "bm25",
                    "k1": 1.2,
                    "b": 0.75,
                    "avg_document_length": 4.0,
                    "document_length_field": "keyword_token_count",
                    "document_length_basis": "body_text_tokens",
                    "query_stopword_policy": "drop_when_content_terms_exist",
                    "query_stop_terms_version": "aoa_course_query_stop_terms_v1",
                },
            }
        ),
        encoding="utf-8",
    )

    results = query_keyword_index(storage, "как привязать Telegram к профилю", run_id="bm25-stopwords", limit=2)

    assert [result["doc_id"] for result in results] == ["target"]


def test_keyword_query_reads_legacy_tf_index_without_bm25_metadata(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    index_path = storage.artifact / "runs/legacy/indexes/keyword_index.json"
    index_path.parent.mkdir(parents=True)
    index_path.write_text(
        json.dumps(
            {
                "schema": "aoa_course_keyword_index_v1",
                "run_id": "legacy",
                "doc_count": 2,
                "docs": [{"doc_id": "short", "text": "term"}, {"doc_id": "repeated", "text": "term term"}],
                "inverted": {"term": [{"doc_id": "short", "count": 1}, {"doc_id": "repeated", "count": 2}]},
            }
        ),
        encoding="utf-8",
    )

    results = query_keyword_index(storage, "term", run_id="legacy", limit=2)

    assert [result["doc_id"] for result in results] == ["repeated", "short"]
    assert {result["score_mode"] for result in results} == {"legacy_tf"}


def test_semantic_index_uses_http_json_embedding_provider(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="starter-fixture")
    server = _EmbeddingServer()
    monkeypatch.setenv("AOA_COURSE_TEST_EMBEDDING_TOKEN", "SUPER_SECRET_EMBEDDING_TOKEN")
    try:
        path = build_semantic_index(
            storage,
            run_id="starter-fixture",
            provider=HTTP_JSON_PROVIDER,
            embedding_endpoint=server.url,
            embedding_model="fixture-embedding",
            embedding_token_env="AOA_COURSE_TEST_EMBEDDING_TOKEN",
            embedding_batch_size=4,
            embedding_timeout_seconds=5.0,
        )
        payload = json.loads(path.read_text(encoding="utf-8"))

        assert payload["provider"] == HTTP_JSON_PROVIDER
        assert payload["provider_config"]["model"] == "fixture-embedding"
        assert payload["provider_config"]["token_env"] == "AOA_COURSE_TEST_EMBEDDING_TOKEN"
        assert payload["dimensions"] == 6
        assert payload["feature_contract"]["external_embedding_vectors"] is True
        assert "SUPER_SECRET_EMBEDDING_TOKEN" not in json.dumps(payload)
        assert server.requests
        assert all(request["authorization"] == "Bearer SUPER_SECRET_EMBEDDING_TOKEN" for request in server.requests)

        semantic = query_semantic_index(storage, "bootloader rollback", run_id="starter-fixture")
        assert semantic
        assert semantic[0]["semantic_provider"] == HTTP_JSON_PROVIDER
        assert semantic[0]["evidence_id"]

        monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
        monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
        monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
        monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))
        result = call_tool("semantic_search", {"query": "bootloader rollback", "run": "starter-fixture"})
        assert result["results"]
        assert result["results"][0]["semantic_provider"] == HTTP_JSON_PROVIDER
    finally:
        server.close()


def test_semantic_and_hybrid_queries_return_evidence(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_semantic_index(storage, run_id="starter-fixture")
    build_graph(storage, run_id="starter-fixture")

    semantic = query_semantic_index(storage, "bootloader rollback", run_id="starter-fixture")
    assert semantic
    assert semantic[0]["score_mode"] == "semantic_vector"
    assert semantic[0]["evidence_id"]

    hybrid = query_hybrid_index(storage, "bootloader rollback", run_id="starter-fixture")
    assert hybrid
    assert hybrid[0]["score_mode"] == "hybrid"
    assert hybrid[0]["score_components"]

    packet = render_answer_packet(storage, "bootloader rollback", run_id="starter-fixture", limit=7, mode="hybrid")
    assert packet["mode"] == "hybrid"
    assert packet["result_count"] >= 1
    assert packet["evidence_chain"]
    assert packet["evidence_chain"][0]["freshness_state"]
    assert packet["evidence_chain"][0]["authority_tier"]
    assert packet["evidence_chain"][0]["rank_score"] == packet["results"][0]["rank_score"]
    assert packet["refresh_report"]["schema"] == "aoa_course_refresh_report_v1"
    assert packet["refresh_report"]["local_rebuild_commands"]
    assert any("lesson-context" in command and "--mode hybrid" in command for command in packet["refresh_report"]["local_query_commands"])
    assert all("--limit 7" in command for command in packet["refresh_report"]["local_query_commands"])
    assert packet["results"][0]["refresh_hint"]["schema"] == "aoa_course_refresh_hint_v1"
    assert "build-semantic-index" in " ".join(packet["results"][0]["refresh_hint"]["local_rebuild_commands"])
    assert any("lesson-context" in command and "--graph-limit 12" in command for command in packet["results"][0]["refresh_hint"]["local_query_commands"])
    assert all("--limit 7" in command for command in packet["results"][0]["refresh_hint"]["local_query_commands"])
    assert packet["evidence_chain"][0]["refresh_hint"]["local_rebuild_commands"]
    assert packet["evidence_chain"][0]["refresh_hint"]["local_query_commands"]


def test_semantic_query_rejects_hash_collision_only_matches(tmp_path: Path) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_semantic_index(storage, run_id="starter-fixture", dimensions=8)

    query = "xylophone nebula quaternion"

    assert query_semantic_index(storage, query, run_id="starter-fixture") == []
    assert query_hybrid_index(storage, query, run_id="starter-fixture") == []


def test_hybrid_search_keeps_lexically_exact_semantic_candidate_outside_keyword_pool(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import aoa_course_connector.query as query_module

    storage = roots(tmp_path)
    distractors = [
        {
            "doc_id": f"distractor:{index}",
            "text": "specific",
            "path": ["Other lesson"],
            "score": 100.0,
        }
        for index in range(20)
    ]
    target = {
        "doc_id": "target",
        "text": "specific target",
        "path": ["Target lesson"],
        "score": 0.4,
        "semantic_provider": "local_hashing_v1",
    }
    monkeypatch.setattr(query_module, "query_keyword_index", lambda *_args, **kwargs: distractors[: int(kwargs["limit"])])
    monkeypatch.setattr(query_module, "query_semantic_index", lambda *_args, **_kwargs: [target])

    results = query_module.query_hybrid_index(storage, "specific target", limit=5)

    assert results[0]["doc_id"] == "target"
    assert results[0]["score_components"]["keyword_fallback"] == 1.0


def test_hybrid_search_prefers_full_query_alignment_over_partial_bm25_leader(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import aoa_course_connector.query as query_module

    storage = roots(tmp_path)
    partial = {"doc_id": "partial", "text": "specific", "path": ["Other lesson"], "score": 100.0}
    target = {"doc_id": "target", "text": "specific target", "path": ["Target lesson"], "score": 10.0}
    monkeypatch.setattr(query_module, "query_keyword_index", lambda *_args, **_kwargs: [partial, target])
    monkeypatch.setattr(
        query_module,
        "query_semantic_index",
        lambda *_args, **_kwargs: [
            {**partial, "score": 0.5, "semantic_provider": "local_hashing_v1"},
            {**target, "score": 0.2, "semantic_provider": "local_hashing_v1"},
        ],
    )

    results = query_module.query_hybrid_index(storage, "specific target", limit=2)

    assert [result["doc_id"] for result in results] == ["target", "partial"]
    assert results[0]["score_components"]["full_lexical_alignment"] == 1.0
    assert results[1]["score_components"]["full_lexical_alignment"] == 0.0


def test_index_manifest_schema_keeps_kind_specific_required_fields() -> None:
    schema = json.loads((REPO_ROOT / "connector" / "schemas" / "index_manifest.schema.json").read_text(encoding="utf-8"))
    variants = {
        variant["properties"]["schema"]["const"]: set(variant["required"])
        for variant in schema["oneOf"]
    }

    assert variants["aoa_course_keyword_index_v1"] >= {"schema", "run_id", "doc_count", "term_count", "feature_contract", "scoring"}
    assert variants["aoa_course_semantic_index_v1"] >= {
        "schema",
        "run_id",
        "doc_count",
        "provider",
        "provider_config",
        "dimensions",
        "feature_contract",
    }


def test_mcp_semantic_search(tmp_path: Path, monkeypatch) -> None:
    storage = roots(tmp_path)
    materialize_fixture(storage, run_id="starter-fixture")
    build_keyword_index(storage, run_id="starter-fixture")
    build_semantic_index(storage, run_id="starter-fixture")
    monkeypatch.setenv("AOA_COURSE_DATA_ROOT", str(storage.data))
    monkeypatch.setenv("AOA_COURSE_CACHE_ROOT", str(storage.cache))
    monkeypatch.setenv("AOA_COURSE_AUTH_ROOT", str(storage.auth))
    monkeypatch.setenv("AOA_COURSE_ARTIFACT_ROOT", str(storage.artifact))

    result = call_tool("semantic_search", {"query": "rollback", "run": "starter-fixture"})

    assert result["mode"] == "semantic"
    assert result["results"]
    assert result["results"][0]["refresh_hint"]["local_rebuild_commands"]


class _EmbeddingServer:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        handler = self._handler()
        self._server = HTTPServer(("127.0.0.1", 0), handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}/embeddings"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)
        self._server.server_close()

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - stdlib handler API.
                length = int(self.headers.get("Content-Length") or "0")
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                inputs = body.get("input")
                if not isinstance(inputs, list):
                    self.send_response(400)
                    self.end_headers()
                    return
                owner.requests.append(
                    {
                        "authorization": self.headers.get("Authorization"),
                        "model": body.get("model"),
                        "count": len(inputs),
                    }
                )
                response = {
                    "data": [
                        {"embedding": _fixture_embedding(str(text))}
                        for text in inputs
                    ]
                }
                encoded = json.dumps(response).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        return Handler


def _fixture_embedding(text: str) -> list[float]:
    lowered = text.casefold()
    return [
        1.0 if "bootloader" in lowered else 0.0,
        1.0 if "rollback" in lowered else 0.0,
        0.8 if "unlock" in lowered else 0.0,
        0.7 if "vendor" in lowered else 0.0,
        0.6 if "mentor" in lowered else 0.0,
        min(len(lowered.split()) / 40.0, 1.0),
    ]
