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

Answers should be built from query results rather than free-floating summaries.

## Index Modes

- `keyword`: deterministic inverted-index search over normalized course
  knowledge items.
- `semantic`: deterministic local sparse vector search using the
  `local_hashing_v1` provider. It hashes text tokens, title/path tokens,
  adjacent bigrams, kind, platform, and authority tier features into normalized
  vectors.
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

Authority tiers are deterministic local signals derived from normalized item
shape and safe metadata: `official_lesson`, `official_assignment`,
`instructor_comment`, `mentor_comment`, `learner_comment`, `transcript`,
`asset_metadata`, `progress_metadata`, `discussion_comment`, or `unknown`.

The local semantic index is a portable baseline, not a claim that the repo has
external model embeddings configured. Future embedding providers must keep this
contract stable: source-backed snippets, path, URL, fetched timestamp, evidence
IDs, source id, freshness, authority tier, rank features, and score components
remain visible.

`aoa-course eval answer-quality` checks this shape for fixture-safe starter,
Stepik, and GetCourse runs: top-result source identity, path, snippet terms,
freshness timestamps, and evidence fields must all survive retrieval.
`aoa-course eval freshness-ranking` checks the ranking-specific conflict case:
with equal base relevance, current evidence must rank above stale evidence.
`aoa-course eval authority-ranking` checks the ranking-specific authority cases:
official lesson text must rank above learner comments, and mentor comments must
rank above learner comments when base relevance is tied.

Commands:

```bash
aoa-course build-semantic-index --run starter-fixture
aoa-course query "bootloader rollback" --run starter-fixture --mode semantic
aoa-course answer "bootloader rollback" --run starter-fixture --mode hybrid
aoa-course materialize fixture --run freshness-ranking-fixture --fixture connector/fixtures/course/freshness_conflict_course.json
aoa-course build-index --run freshness-ranking-fixture
aoa-course build-semantic-index --run freshness-ranking-fixture
aoa-course eval freshness-ranking
aoa-course materialize fixture --run authority-ranking-fixture --fixture connector/fixtures/course/authority_conflict_course.json
aoa-course build-index --run authority-ranking-fixture
aoa-course build-semantic-index --run authority-ranking-fixture
aoa-course eval authority-ranking
aoa-course mcp call semantic_search '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call hybrid_search '{"query":"rollback","run":"starter-fixture"}'
```
