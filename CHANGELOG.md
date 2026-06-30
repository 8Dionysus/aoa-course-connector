# Changelog

## 0.1.0 - Unreleased

- Initial public-ready repository skeleton.
- Added offline course fixture ingestion.
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
- Added transcript/caption health diagnostics to live calibration packets,
  including transcript source-authority counts, caption sidecar totals, browser
  reports with transcripts, and caption-resource error failures.
- Added read-only connected-source launch plans through CLI `preflight
  connected-plan` and MCP `connected_source_plan` so agents can inspect
  readiness and get exact preflight, sync, smoke, and calibration commands
  before touching live sources.
