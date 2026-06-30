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
