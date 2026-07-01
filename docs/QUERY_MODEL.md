# Query Model

A useful result must include:

- matched snippet;
- course/module/lesson/step path;
- source URL;
- source id;
- fetched timestamp;
- platform;
- evidence IDs;
- freshness state;
- authority tier;
- base relevance `score`;
- freshness/authority/provenance adjusted `rank_score`.
- refresh hint that tells an agent how to rebuild local artifacts and how to
  preflight/sync the source when a connected live route exists.

Answers should be built from query results rather than free-floating summaries.

## Index Modes

- `keyword`: deterministic inverted-index search over normalized course
  knowledge items.
- `semantic`: sparse vector search using the semantic provider declared by the
  index artifact. The default `local_hashing_v1` provider hashes text tokens,
  title/path tokens, adjacent bigrams, kind, platform, and authority tier
  features into normalized vectors. The optional `http_json_v1` provider calls
  an operator-configured JSON embedding endpoint for both document indexing and
  query vectors.
- `hybrid`: combines normalized keyword score and semantic vector score while
  preserving the same evidence-bearing result shape.

## Ranking

`score` remains the raw match score for the selected mode. `rank_score` is the
ordering score used for results. It applies small transparent boosts/penalties
for freshness state, authority tier, and complete source provenance, so current
or authoritative source-backed items can beat stale or lower-authority items
when the underlying relevance is otherwise tied or close.

Each result exposes `rank_features`, including `freshness_state`,
`freshness_boost`, `authority_tier`, `authority_boost`, `provenance_boost`, and
`provenance_complete`. Hybrid results also expose these factors in
`score_components`.

Each result also exposes `refresh_hint`. This is read-only plan metadata, not
a network action. It always includes `local_rebuild_commands` for
`build-index`, `build-semantic-index`, and `build-graph` against the current
run. For connected platforms (`getcourse`, `skillspace`, `stepik`) it also
includes a bounded `preflight connected-plan` command. When the result's
`source_id` matches the local source registry, `source_refresh.registry_match`
is true and the hint includes a registry-driven live `sync` command scoped with
`--source-id`, plus sync-status guidance. When the source is an `offline_export`
or a registry match is missing, the hint says what is blocked instead of
pretending a live refresh can safely run.

Answer packets summarize these per-result hints in `refresh_report` with
unique source counts, registry-match counts, local rebuild commands, source
commands, and `network_touched: false`.

The `evidence_chain` is also proof-bearing. Each evidence item keeps the
source URL/id, fetched timestamp, platform, path, freshness state, authority
tier, rank score, rank features, source authority when available, and refresh
hint, so agents can cite and refresh the exact result without reopening the
full result list.

`aoa-course refresh query` wraps this into an `aoa_course_refresh_cycle_v1`
packet. Without `--execute`, it is a read-only plan: current answer packet,
selected source-backed result, planned rebuild/source commands, refresh hint,
and optional connected-source plan. With `--strategy fixture --execute`, it
proves the full loop against safe registered fixture sources: source sync,
checkpoint selection, keyword/semantic/graph rebuild, refreshed answer packet,
and a source-id comparison. Live execution is gated behind
`--strategy live --execute --allow-network`.

Authority tiers are deterministic local signals derived from normalized item
shape and safe metadata: `official_lesson`, `official_assignment`,
`instructor_comment`, `mentor_comment`, `learner_comment`, `transcript`,
`asset_metadata`, `progress_metadata`, `discussion_comment`, or `unknown`.
When adapters provide explicit `authority_tier`, `authority_label`, `role`, or
`source_authority` metadata, the index preserves those adapter-derived signals
before falling back to kind/label heuristics.

The local semantic index is the portable baseline, not a claim that a clone has
external model credentials configured. External providers must keep this
contract stable: source-backed snippets, path, URL, fetched timestamp, evidence
IDs, source id, freshness, authority tier, rank features, and score components
remain visible.

`http_json_v1` stores endpoint/model metadata and the token environment variable
name in `provider_config`, but never stores the token value. The query route
reads the semantic index provider and uses the same provider for query
vectorization, so MCP `semantic_search` and `hybrid_search` stay in the same
vector space as the indexed course documents.

`aoa-course eval answer-quality` checks this shape for fixture-safe starter,
Stepik, and GetCourse runs: top-result source identity, path, snippet terms,
freshness timestamps, authority/rank proof fields, and evidence fields must
all survive retrieval.
`aoa-course eval freshness-ranking` checks the ranking-specific conflict case:
with equal base relevance, current evidence must rank above stale evidence.
`aoa-course eval authority-ranking` checks the ranking-specific authority cases:
official lesson text must rank above learner comments, and mentor comments must
rank above learner comments when base relevance is tied.
`aoa-course eval adapter-authority` checks that adapter-derived authority
metadata from browser-session and Stepik fixtures survives normalization,
indexing, and query packets.

Commands:

```bash
aoa-course build-semantic-index --run starter-fixture
aoa-course preflight semantic-provider --run starter-fixture --provider http_json_v1 --embedding-endpoint "http://127.0.0.1:8000/embeddings" --embedding-model "local-course-embedding" --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN --require-ready
aoa-course build-semantic-index --run starter-fixture --provider http_json_v1 --embedding-endpoint "http://127.0.0.1:8000/embeddings" --embedding-model "local-course-embedding" --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN
aoa-course query "bootloader rollback" --run starter-fixture --mode semantic
aoa-course answer "bootloader rollback" --run starter-fixture --mode hybrid
aoa-course evidence inspect "bootloader rollback" --run starter-fixture --mode hybrid
aoa-course refresh query "bootloader rollback" --run starter-fixture --mode hybrid
aoa-course refresh query "Stepik public API evidence" --run "<checkpoint-run-id>" --mode hybrid --strategy fixture --execute --sync-run stepik-refresh-cycle
aoa-course materialize fixture --run freshness-ranking-fixture --fixture connector/fixtures/course/freshness_conflict_course.json
aoa-course build-index --run freshness-ranking-fixture
aoa-course build-semantic-index --run freshness-ranking-fixture
aoa-course eval freshness-ranking
aoa-course materialize fixture --run authority-ranking-fixture --fixture connector/fixtures/course/authority_conflict_course.json
aoa-course build-index --run authority-ranking-fixture
aoa-course build-semantic-index --run authority-ranking-fixture
aoa-course eval authority-ranking
aoa-course eval adapter-authority
aoa-course mcp call semantic_search '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call hybrid_search '{"query":"rollback","run":"starter-fixture"}'
```
