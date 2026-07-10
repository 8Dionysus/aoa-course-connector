# Changelog

## 0.1.0 - Unreleased

- Replaced raw term-frequency keyword ordering with a versioned BM25 contract,
  body-text length normalization, IDF, content-aware query stop-term handling,
  legacy-index read compatibility, and corpus-integrity validation.
- Deepened hybrid candidate retrieval and reranking with explicit lexical,
  full-query, and native-path alignment; machine path IDs no longer act as
  human breadcrumb matches.
- Strengthened place-grounded retrieval probes to preserve course/module/lesson
  query context and recognize equivalent native hierarchy paths while keeping
  exact-document recall as a separate diagnostic.
- Added `aoa_course_artifact_integrity_v1`, CLI `eval corpus-integrity`, and MCP
  `artifact_integrity` to cross-check canonical normalized objects against
  keyword/semantic indexes, vectors, postings, evidence, graph records, and
  deterministic exact/place-grounded Recall@K without touching the network.
- Added assignment graph nodes and `lesson_has_assignment` edges; the new gate
  exposed and repaired missing assignment coverage across existing Stepik
  corpora while preserving diagnostic exact-document ambiguity separately from
  correct course/lesson retrieval.
- Isolated `eval install-route` from operator storage so repeated fresh-install
  proofs cannot add fixture sources or checkpoints to a connected registry.
- Fixed hybrid candidate pooling so a lexically exact semantic candidate keeps
  an explicit `keyword_fallback` even when raw term frequency places it just
  outside the bounded keyword pool.
- Initial public-ready repository skeleton.
- Added offline course fixture ingestion.
- Added comparable cross-source portfolio reranking and
  `eval connected-portfolio` with expected Top-1 source/path, collision,
  confidence, and negative-query checks for fixture and runtime suites.
- Added structural ingest coverage and canonical-ID continuity to browser and
  Stepik raw/receipt/checkpoint/catalog surfaces, plus `eval ingest-coverage`
  with isolated completeness and bounded-refresh probes.
- Added keyword index, graph builder, answer packet, CLI, MCP skeleton, and
  validation route.
- Added Stepik clean API adapter with fixture and bounded live materialization.
- Added shared GetCourse/Skillspace browser-session snapshot adapters with
  fixture materialization and optional Playwright live capture.
- Added GetCourse/Skillspace browser-session account discovery into the local
  source registry with fixture, snapshot, live Playwright CLI routes, and evals.
- Added source-registry driven browser sync with `SyncCheckpoint` records,
  `sync status`, MCP `sync_status`, and optional per-source index/graph builds.
- Hardened sync checkpoint identity so repeated sync runs for the same source
  keep per-run history instead of overwriting each other.
- Hardened browser catalog discovery so course slugs containing words like
  `lesson` or `task` are not rejected as non-course pages.
- Added bounded GetCourse/Skillspace course-tree crawl routes with fixture,
  snapshot, live Playwright CLI commands, CI smoke checks, and answer evals.
- Hardened browser asset metadata extraction for unannotated file links and
  Stepik live step block resolution for richer source-backed text.
- Added browser-session progress/status extraction, visible comment indexing,
  comment/progress graph edges, paginated catalog receipts, MCP context smoke,
  and `browser-progress-comments` eval coverage.
- Added bounded live discovery next-page following with `--max-pages` and
  unannotated DOM heuristics for visible progress/status and compact comments.
- Added `smoke browser-fixture`, `smoke browser-snapshot`, and gated
  `smoke browser-live` reports for operator calibration without printing raw
  private HTML.
- Added Stepik `ids[]` batched course traversal, `--full-course` live
  materialization, `--batch-size`, optional `--include-step-sources`
  enrichment, and `meta.has_next` pagination helpers.
- Added Stepik source-registry discovery/registration, fixture/live sync
  commands, sync checkpoints, MCP-visible status, and `stepik-sync` eval
  coverage.
- Added `smoke stepik-fixture` and gated `smoke stepik-live` reports for
  Stepik registration, sync, artifacts, answer evidence, and privacy-safe raw
  API path reporting.
- Added deterministic `local_hashing_v1` semantic/vector index, semantic and
  hybrid query modes, CLI build/query/answer support, MCP semantic/hybrid search
  tools, and semantic index eval coverage.
- Added optional `http_json_v1` semantic embedding provider support, keeping
  provider metadata in the semantic index artifact, using the same provider for
  query/MCP vectors, and redacting token values from artifacts.
- Hardened smoke/sync guardrails so catalog-only browser smoke queries report a
  partial blocked answer and Stepik fixture sync refuses non-fixture course IDs.
- Added browser-session auth-state onboarding commands for Playwright state
  capture and redacted state inspection before live GetCourse/Skillspace sync.
- Added JSON-RPC stdio support to `aoa-course-connector-mcp`, including
  `initialize`, `tools/list`, and `tools/call` responses with structured tool
  results.
- Hardened deterministic semantic search against hash-collision-only matches
  and made index manifest schema requirements variant-specific.
- Hardened browser auth-state inspection so cookie-domain-only Playwright state
  can still satisfy expected-origin checks.
- Hardened browser progress parsing for aria-valuenow-only progress bars and
  explicit not-started states.
- Added Stepik account-level course discovery with fixture/live routes and
  optional source-registry registration for connected accounts.
- Added read-only live preflight reports for Stepik token presence,
  browser-session storage-state readiness, registered sources, next commands,
  and secret-redacted operator handoff.
- Added MCP `live_preflight` so agents can inspect connected-source readiness
  through structuredContent without touching the network or printing secrets.
- Repaired the local eval-port contract and added `eval answer-quality` for
  source id, path, snippet, freshness, and evidence-field checks.
- Added freshness-aware `rank_score`/`rank_features` for keyword, semantic, and
  hybrid results plus `eval freshness-ranking` with a current-vs-stale conflict
  fixture.
- Added authority-aware `authority_tier` and `authority_boost` ranking signals
  plus `eval authority-ranking` with official-vs-learner and mentor-vs-learner
  conflict fixtures.
- Added adapter-derived authority metadata for browser-session comments and
  Stepik official API objects plus `eval adapter-authority` to prove the signal
  survives normalization, indexing, and query packets.
- Hardened browser auth-state origin matching so source hosts must match exactly
  instead of by unsafe substring, and preflight no longer suggests live sync
  until every registered source host is ready.
- Hardened live readiness and discovery edges: Stepik public API sources can
  preflight as sync-ready without an account token, inactive/deleted Stepik
  enrollments are ignored, browser storage state is checked per registered
  source host, pagination links cannot pass catalog `link_pattern`, and MCP
  initialize falls back to the supported protocol version.
- Added live calibration packets plus `eval live-calibration` and
  `calibration build` so GetCourse, Skillspace, and Stepik smoke/preflight
  reports can be summarized without committing private payloads.
- Added `calibration intake` so live calibration packets can be turned into
  repo-local repair lanes and eval-intake candidates while keeping central proof
  authority in `aoa-evals`.
- Added MCP `evidence_report` and strengthened graph/freshness/evidence MCP
  validation so agents can inspect source-backed results, freshness, authority,
  and graph context through structured tool output.
- Added browser-session visible transcript/caption extraction for GetCourse and
  Skillspace fixtures plus `eval browser-transcripts` coverage through
  normalized transcript objects, index docs, graph edges, and answer packets.
- Tightened live calibration privacy checks so generic token/API-key fields are
  rejected as secret-bearing source-report payloads.
- Added browser-session caption sidecar extraction from `<track>` resources,
  including WebVTT/SRT cue cleanup, live caption-resource collection guardrails,
  smoke `transcript_count`, and source-authority checks in
  `eval browser-transcripts`.
- Hardened browser-session materialization receipts so caption sidecar
  resources that parse without transcript text count as caption parse errors
  instead of silently looking healthy.
- Hardened fixture, Stepik, browser materialize, and browser source-sync
  receipts with explicit `content_counts` for course/module/lesson/step and
  related content totals, then exercised an authorized Stepik full-course sync
  with local CLI/MCP answer-matrix retrieval proof.
- Added transcript/caption health diagnostics to live calibration packets,
  including transcript source-authority counts, caption sidecar totals, browser
  reports with transcripts, and caption-resource error failures.
- Added read-only connected-source launch plans through CLI `preflight
  connected-plan` and MCP `connected_source_plan` so agents can inspect
  readiness and get exact preflight, sync, smoke, and calibration commands
  before touching live sources.
- Hardened connected-source launch plans so Stepik live commands default to a
  bounded smoke/sync scope, with `full-course` and step-source enrichment only
  emitted after an explicit operator/agent option.
- Added browser auth handoff packets to connected-source plans so GetCourse and
  Skillspace sources are grouped by host with state-file readiness, auth
  capture, redacted inspect, and connected-plan recheck commands.
- Added `preflight connected-plan --write-runbook` so the redacted
  connected-source plan can be written as a runtime Markdown checklist for
  operator setup, sync, smoke, and calibration.
- Hardened generated connected-source plan artifact paths so preflight, smoke,
  and calibration commands use the portable artifact-root fallback and
  `runs/<run>/calibration/...` packet layout.
- Verified the bounded public Stepik live calibration route through preflight,
  live smoke, answer evidence, timestamp checks, and live calibration packet
  privacy guards.
- Added per-result `refresh_hint` and answer/MCP `refresh_report` metadata so
  agents can rebuild local artifacts, run bounded connected-source preflight,
  and identify registry-matched live sync routes for source freshness handoff.
- Added `refresh query` and MCP `refresh_plan` so agents can turn evidence
  hints into a refresh cycle plan, execute fixture-backed source refreshes, pick
  the new checkpoint run, rebuild indexes/graphs, and compare refreshed answer
  evidence before gated live execution.
- Added `--source-id` scoped sync support and source-scoped connected-plan
  commands so incremental refresh can target one registry source instead of a
  whole platform batch.
- Added `calibration connected-run` with fixture-safe executable receipts and a
  live `--allow-network` gate so agents can run source sync, smoke reports,
  connected plan/runbook, calibration packet, and intake as one connected-source
  workflow.
- Verified the bounded public Stepik live connected-run route end to end through
  a local runtime receipt with live sync, live smoke, calibration packet,
  intake, answer evidence, timestamps, and privacy guards.
- Added read-only connected-run receipt inspection through CLI
  `calibration status` and MCP `connected_run_status`.
- Added CLI `calibration query` and MCP `connected_run_query` so agents can
  execute connected-run query-plan entries into source-backed answer, lesson
  context, evidence, freshness, authority, and graph-context packets without
  touching the network.
- Added `eval preauth-readiness` as the executable stop-line before operator
  authorization: it prepares the starter proof, writes/applies an
  `operator-preauth` profile, creates redacted runbooks, verifies CLI/MCP
  profile/preflight/plan/query routes, and returns
  `aoa_course_eval_preauth_readiness_v1` with
  `ready_until_authorization` and `pause_boundary`.
- Hardened live connected-run browser execution so ready GetCourse/Skillspace
  sources use the same default account storage-state checked by preflight and
  receipts expose `source_selection` for source-scoped auditability.
- Expanded MCP `ingest_status` into a read-only run readiness packet with
  normalized counts, receipt summaries, index/semantic/graph metadata, and next
  commands.
