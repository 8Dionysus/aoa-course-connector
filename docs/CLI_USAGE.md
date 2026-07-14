# CLI surface

The `aoa-course` parser is the executable owner of command names, arguments,
defaults, and help text. This document describes command-group semantics and
returned packet contracts; it is not a second syntax catalog.

## Storage and health

The storage and doctor groups resolve the configured data, cache, auth, and
artifact roots and report whether the local installation is usable. They do
not inspect or emit secret values.

The fixture bootstrap route produces
`aoa_course_fixture_bootstrap_receipt_v1`. It prepares the starter normalized
bundle, keyword and semantic indexes, graph, and a fixture connected-run across
GetCourse, Skillspace, and Stepik. The route is isolated and must retain
`network_touched: false`.

## Discovery, materialization, and sync

Discovery identifies course entrypoints. Registration writes only normalized
source metadata to the local source registry. Materialization writes raw and
normalized runtime artifacts under configured storage. Sync refreshes enabled
sources, retains checkpoint history, and can build the selected source's
derived artifacts.

Source selection is explicit in large registries. CLI selections map to the
same `source_ids` array used by MCP, and plans report the resolved
`selected_source_ids`. Omitted selection preserves the broader batch route.

Fixture, snapshot, and live modes remain distinct. Live execution requires an
explicit network gate and source readiness; a planning or preflight packet is
always no-network.

## Coverage and continuity

Ingest coverage reports source inventory scope, structural counts, limits,
gaps, exhaustion, and complete, bounded, partial, or indeterminate status.
Browser coverage measures visible lessons. Stepik coverage measures referenced
and fetched sections, units, lessons, and steps, with optional step-source
enrichment reported separately.

Sync checkpoints attach canonical identity continuity. A bounded refresh cannot
declare absent objects deleted; its removal assessment remains inconclusive.

## Index, graph, and query

Index groups build versioned keyword and semantic artifacts. Graph groups build
course hierarchy and evidence relations. Query groups return ranked objects,
lesson context, evidence, freshness, authority, and refresh information.

Source-scoped answer surfaces locate a query-ready connected run for each
selected registry source. Cross-source surfaces retain one answer and evidence
chain per source. Matrix surfaces repeat the same source set over several
questions and report aggregate breadth without replacing the individual
packets.

The query model distinguishes a strict all-sources coverage mode from a
portfolio mode where each question needs evidence from at least one selected
source. Neither mode changes source authority.

## Semantic provider

Semantic-provider preflight is read-only. The
`aoa_course_semantic_provider_preflight_v1` packet reports provider type,
endpoint and model presence, token-environment presence, normalized-input
availability, and `token_value_logged: false`. It does not call the provider.

The deterministic local provider remains the fixture baseline. External
providers are operator-selected runtime adapters and do not change the stable
index or query contract.

## Readiness and connected plans

Readiness returns `aoa_course_connector_readiness_v1`, separating
`operational_ready`, `connected_live_ready`, and semantic-provider readiness.
It includes storage, install, source registry, selected run, MCP coverage,
query-ready connected receipts, and bounded next-action data.

Connected-source planning preserves platform and source selection, browser
traversal bounds, Stepik enrichment bounds, query intent, auth candidates,
portable artifact paths, and a `connected_run_plan`. A ready subset may proceed
while unrelated blocked sources remain visible. The plan never executes live
work.

## Connection profiles

Connection profiles package operator source refs, local auth paths, live scope,
query intent, and semantic-provider settings into
`aoa_course_connection_profile_v1`. Inspection is redacted. Status returns
`aoa_course_connection_profile_status_v1` with selected-source, auth,
semantic-provider, `ready_for_connected_run`, and connected-run readiness.
The same read-only state is exposed by `connection_profile_inspect` and
`connection_profile_status`. Apply updates only the local source registry; the
run bridge remains a plan until the network gate is explicit.

## Calibration

A fixture connected run exercises source registry sync, smoke, plan,
calibration, intake, and retrieval without network access. A live connected run
uses the same contract only after selected-source readiness and explicit
authorization.

Connected-run status preserves stage outcomes, artifacts, query plan, and
`repair_lanes`. Connected-run query returns
`aoa_course_connected_run_query_packet_v1` with source-backed answer, lesson
context, evidence, freshness, authority, and graph context. A partial connected
run stays partial; it is not converted into success by the query surface.

## Evals

Local eval groups cover install, adapter behavior, ingest coverage, corpus
integrity, retrieval, answer quality, freshness, authority, transcripts,
connected portfolio behavior, and calibration packet shape. Exact suites and
requirements live under `evals/`; proof and verdict authority remain with
`aoa-evals`.

## Command authority

Use the parser's nested help for exact syntax. The root `AGENTS.md` owns the
short operator route; the CI workflow and executable verifier own exhaustive
proof sequences. Adding a new CLI route requires implementation and tests, not
a copied command block in Markdown.
