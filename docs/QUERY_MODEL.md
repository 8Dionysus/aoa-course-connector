# Query model

The query layer turns normalized course objects into source-backed ranked
results, lesson context, answers, evidence, and refresh information. It does not
replace the source or eval authority.

## Keyword and semantic retrieval

Keyword retrieval uses a versioned BM25 contract with body-text document length,
IDF, explicit scoring metadata, and content-aware query stop terms. Legacy
term-frequency artifacts may remain readable but do not satisfy current corpus
integrity.

Semantic retrieval supports `local_hashing_v1` as the deterministic offline
baseline and `http_json_v1` as an operator-configured provider adapter.
Provider metadata is recorded as `provider_config`; token value material is
never stored or logged. `semantic_search` and `hybrid_search` reuse the
provider contract recorded by the index.

## Hybrid rank

Hybrid rank preserves BM25, semantic similarity, lexical coverage, all-term
coverage, native-path alignment, freshness, and authority contributions in
`rank_score` and rank features. Machine ids do not count as human path
breadcrumbs.

Freshness is evidence, not truth. `authority_tier` distinguishes official
source, mentor, learner, and derived content without making the ranker a verdict
engine.

## Source identity and path

Every result keeps source id, platform, course/module/lesson path, object kind,
native id, fetched time, freshness, authority tier, and evidence refs. Equivalent
objects from different sources or native paths remain distinct.

Place-grounded retrieval accepts the correct canonical course and lesson context
when duplicate documents exist inside that place. Exact-document recall remains
a separate diagnostic.

## Answer and context

Answer packets retain ranked results, evidence chain, quality summary, blockers,
and `refresh_hint`. Lesson-context packets add bounded graph neighborhoods
around the evidence lesson. Evidence reports preserve source identity,
freshness, authority, and refresh information without opening raw content.

Cross-source queries keep one answer and evidence chain per source. Portfolio
coverage can establish that at least one selected source answers a question,
but it cannot turn an unrelated source into a failure or merge sources into one
authority.

## Refresh

A refresh plan returns `aoa_course_refresh_cycle_v1` with
`registry_match`, source posture, local rebuild steps, and source-aware next
actions. Planning is no-network. Execution uses the source registry and writes a
new checkpoint rather than overwriting previous evidence.

Incomplete or bounded ingest keeps removals inconclusive. `refresh_hint` never
authorizes a network call by itself.

## Integrity and eval boundary

Corpus integrity compares canonical objects with indexes, vectors, postings,
graph, evidence, and deterministic retrieval probes. Local answer, freshness,
authority, and portfolio suites test connector behavior. None of these surfaces
owns central proof or a course-content verdict.

Exact query syntax belongs to the CLI parser and MCP tool schemas. Executable
proof lives in tests, the verifier, and CI rather than in Markdown command
blocks.
