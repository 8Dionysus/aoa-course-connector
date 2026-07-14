# Status

This file records durable capability state. Exact commands belong to the CLI,
scripts, tests, CI workflow, and root `AGENTS.md`. Private runtime receipts and
current operator-source counts are not repository status.

## Public offline baseline

The repository contains a network-free public proof across three adapter
families:

- GetCourse browser-session fixtures;
- Skillspace browser-session fixtures;
- Stepik clean API fixtures.

The baseline covers discovery, source registration, materialization,
normalization, keyword and semantic indexes, course graph, source-backed
queries, lesson context, answer and evidence packets, refresh planning, and MCP
stdio. Fixtures are synthetic public method evidence, not live-source proof.

## Source and ingest state

Browser adapters expose account-catalog discovery, course-tree crawl, visible
lesson materialization, progress, comments, transcript blocks, and caption
sidecars. Stepik exposes course, section, unit, lesson, step, enrollment, and
course-grade shaped routes with bounded batching and optional step-source
enrichment.

All source modes report explicit provenance and network posture. Private raw
pages, API payloads, browser state, credentials, and normalized corpora remain
outside Git.

`aoa_course_ingest_coverage_v1` records the structural inventory before limits,
selected and materialized counts, gaps, exhaustion, and complete, bounded,
partial, or indeterminate status. `aoa_course_identity_continuity_v1` compares
canonical ids across checkpoints while preserving prior artifacts. Incomplete
refresh cannot masquerade as deletion.

## Retrieval state

Keyword artifacts use a versioned BM25 contract with body-text length
normalization and explicit scoring metadata. Semantic artifacts support the
deterministic `local_hashing_v1` baseline and an operator-configured
`http_json_v1` adapter. Provider values are runtime configuration; token values
are never serialized.

Hybrid retrieval keeps lexical, semantic, path, freshness, and authority
components visible. Answer packets carry source id and URL, native hierarchy,
fetched time, freshness state, authority tier, rank features, refresh hint, and
evidence chain. Cross-source queries preserve per-source packets.

## Graph and integrity state

The graph covers course, module, lesson, step, asset, transcript, assignment,
discussion, topic, entity, and evidence relations. Assignment and transcript
objects remain visible as first-class nodes rather than disappearing into
lesson text.

`aoa_course_artifact_integrity_v1` compares normalized canonical objects with
keyword and semantic documents, vectors, postings, evidence, graph nodes and
edges, artifact metadata, and deterministic retrieval probes. Missing files or
records, duplicates, dangling edges, invalid scoring metadata, and retrieval
misses remain explicit failures. The audit never calls an external semantic
provider.

## Readiness and calibration state

`aoa_course_connector_readiness_v1` separates local operational readiness from
connected-live readiness. It accounts for install files, storage, source
registry, selected runs, indexes, graph, semantic provider, MCP tools, connected
plans, and query-ready source receipts. A missing starter fixture does not hide
an already query-ready connected source.

Connection profiles preserve source refs, auth paths, selected live scope,
query intent, and semantic-provider settings without storing secret values.
Connected-source plans preserve selected source ids, traversal and enrichment
bounds, auth candidates, artifact routes, and explicit network posture.

Fixture calibration covers the same receipt, status, intake, and query packet
shapes as the live route without touching the network. Partial stages produce
repair lanes. Calibration intake proposes local fixes and eval candidates but
does not own central proof.

## MCP state

The independently runnable MCP server supports JSON-RPC stdio initialization,
tool discovery, structured tool calls, retrieval, source inspection, evidence,
readiness, preflight, connection-profile inspection, connected-run planning,
fixture connected execution, status, and query packets. Runtime deployment and
registration remain owned by `abyss-stack`.

## Eval state

Local suites cover install route, adapter authority, browser discovery and
crawl, source sync, transcript/caption extraction, Stepik clean API behavior,
semantic retrieval, freshness and authority ranking, answer quality, connected
portfolio selection, ingest coverage, corpus integrity, retrieval loop, and
calibration packet behavior.

These suites prove connector-local behavior only. Scoring policy, promotion,
verdicts, and proof doctrine remain owned by `aoa-evals`.

## Stats state

The root `stats/` port is active and reference-only. Its first measurement is
`aoa-course-connector/public-fixture-structural-materialization-ratio`, a census
of structural references declared by the canonical public GetCourse,
Skillspace, and Stepik starter fixtures.

The current packet reports `9 / 9`: two GetCourse lesson references, two
Skillspace lesson references, and five Stepik section/unit/lesson/step
references are materialized. A missing structural object remains an observed
gap. Bounded, non-exhausted, malformed, duplicate-platform, or empty evidence
is unknown. The ratio does not establish content adequacy, live coverage,
corpus integrity, retrieval quality, readiness, eval success, or runtime
health.

## Remaining development

Live platform calibration remains operator-dependent and outside committed
status. Future work includes broader hard-adapter variants, additional clean
API/LMS adapters, richer caption formats, and evidence-driven local measures
only when a real consumer question appears.
