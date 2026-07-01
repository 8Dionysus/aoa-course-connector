# Status

## Current Proof

The repository has a working offline connector slice:

```bash
python scripts/validate_connector.py
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m aoa_course_connector.cli materialize fixture --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "bootloader unlock rollback" --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli mcp tools
```

This proves:

- canonical course fixture normalization;
- source-backed keyword search;
- deterministic local semantic/vector search with `local_hashing_v1`;
- optional `http_json_v1` semantic provider contract for operator-configured
  embedding endpoints, with provider metadata in the index artifact, query/MCP
  reuse of the same vector provider, and token-value redaction;
- read-only semantic provider preflight through CLI `preflight
  semantic-provider`, MCP `semantic_provider_preflight`, and embedded
  `readiness` packets. The preflight emits
  `aoa_course_semantic_provider_preflight_v1`, verifies normalized bundle
  presence plus `http_json_v1` endpoint/model/token-env readiness before any
  network call, and keeps `token_value_logged: false` and
  `network_touched: false`;
- graph construction for course/module/lesson/step/asset/topic/entity;
- answer packets with evidence chains and freshness timestamps;
- JSON-RPC stdio MCP tool surface with structured `tools/list` and
  `tools/call` responses;
- MCP `ingest_status` returns a read-only run readiness packet with normalized
  counts, materialization receipts, index/semantic/graph metadata, next
  commands, and `agent_query_ready`;
- CLI `readiness` and MCP `connector_readiness` return one read-only
  `aoa_course_connector_readiness_v1` route audit with install-route files,
  storage roots, source registry counts, selected run/index/graph readiness,
  semantic provider readiness, connected-source handoff status, compact
  `connected_run_handoff`, connected-run receipt status, MCP tool coverage,
  `operational_ready`, `connected_live_ready`, and next commands. The embedded
  connected plan
  preserves operator-selected `live_scope`, `include_step_sources`,
  `link_pattern`, `max_lessons`, `max_pages`, and `max_sources` through the
  ready connected-run handoff. If the selected connected-run receipt is partial
  and includes `repair_lanes`, the top-level readiness `next_commands` now
  surface those lane commands instead of replacing the receipt with fixture
  bootstrap;
- CLI `bootstrap fixture` returns `aoa_course_fixture_bootstrap_receipt_v1` and
  turns a fresh local state into a query-ready starter proof: storage roots,
  normalized starter bundle, keyword index, semantic index, graph, default
  GetCourse/Skillspace/Stepik fixture connected-run receipt, and embedded
  readiness without touching the network;
- CLI `goal audit` and MCP `goal_audit` return
  `aoa_course_goal_audit_v1`, a read-only DoD-oriented handoff that separates
  `ready_for_operator_connection` from `goal_complete`, keeps live account
  calibration in `remaining_live_requirements`, reports
  `network_touched: false`, and exits non-zero on the CLI with
  `--require-ready-for-connection` until offline starter, fixture connected-run,
  MCP, docs, schemas, storage, and privacy/source boundaries are all in place;
- MCP agent routes for graph neighborhoods, freshness reports, and compact
  evidence reports with source URL, course path, fetched timestamp, freshness
  state, authority tier, rank score, refresh report, and per-result refresh
  hints;
- answer/search/evidence packets now tell agents how to rebuild local indexes
  and graphs for the current run, how to run a bounded connected-source
  preflight, and which registry-matched live sync route can refresh GetCourse,
  Skillspace, or Stepik sources without touching the network during planning;
- `refresh query` now wraps those hints into `aoa_course_refresh_cycle_v1`:
  a read-only plan by default, a fixture-executable sync/checkpoint/rebuild
  loop for registered safe sources, and a live execution route gated behind
  explicit `--allow-network`; MCP exposes the read-only `refresh_plan` tool;
- source-registry sync routes and connected-source handoff commands support
  `--source-id` scoped refreshes, so an agent can refresh one selected source
  without forcing a full platform sync;
- fresh-copy agent install route.
- Stepik clean API adapter through fixture, bounded live public API smoke,
  source-registry sync checkpoints, batched full-course materialization route,
  optional authenticated step-source enrichment, account-level source discovery,
  active-enrollment filtering, and client pagination helpers.
- GetCourse and Skillspace browser-session snapshot adapters through fixtures
  and optional Playwright live capture route.
- GetCourse and Skillspace account-level browser discovery into the local source
  registry through fixtures, snapshot input, optional Playwright live discovery,
  bounded live next-page following, and source-registry evals.
- GetCourse and Skillspace source-registry driven browser sync with
  `SyncCheckpoint` records, optional per-source index/graph builds, CLI status,
  MCP status, and evals.
- GetCourse and Skillspace bounded course-tree crawlers through fixtures,
  snapshot input, optional Playwright live traversal, and answer evals.
- GetCourse and Skillspace visible progress/status and comments through browser
  fixtures, answer packets, index docs, graph edges, MCP context, and evals.
- GetCourse and Skillspace visible transcript/caption extraction into
  canonical Transcript objects, keyword-index documents, `lesson_has_transcript`
  graph edges, answer packets, and `browser-transcripts` eval coverage.
- GetCourse and Skillspace caption sidecar extraction from `<track>` resources
  and local snapshot `resources[]` into canonical Transcript objects,
  `browser_caption_sidecar` source authority, smoke `transcript_count`, answer
  packets, and `browser-transcripts` eval coverage.
- Browser-session materialization receipts count caption resources that parse
  without transcript text as caption parse errors, so live calibration does not
  mistake empty sidecar files for healthy transcript coverage.
- GetCourse and Skillspace paginated catalog fixture receipts with page-count
  and next-link evidence in discovery output.
- Browser catalog discovery rejects pagination links even when a broad
  `link_pattern` would otherwise match them.
- Browser-session parser heuristics for unannotated, aria-only, and
  not-started progress/status blocks plus compact visible
  comment/reply/discussion blocks.
- Browser-session smoke route for fixture, operator snapshot, and gated live
  calibration reports without printing private raw HTML.
- Browser-session auth-state onboarding through CLI planning, optional
  Playwright capture, expected-origin capture receipts, and redacted
  storage-state inspection. `auth plan-browser-state` and connected-source
  handoffs carry `--expect-origin-contains` so wrong-login or cross-school
  storage-state mismatches are visible before live discovery or sync.
- Read-only live preflight reports for Stepik tokens, browser storage-state
  usability, source-registry readiness, next commands, secret redaction, and
  MCP `live_preflight` structuredContent.
- Read-only connected-source launch plans through CLI `preflight
  connected-plan` and MCP `connected_source_plan`, turning source readiness into
  exact preflight, sync, smoke, calibration, and
  `connected_run_handoff` commands without touching the network or printing
  secrets. Ready handoffs preserve selected platforms, source ids, query, live
  scope, and browser `link_pattern` in the one-command
  `calibration connected-run --mode live --allow-network` route. Stepik launch
  plans default to bounded live smoke/sync commands, with
  full-course/source-enrichment commands gated behind explicit options.
- `preflight live`, `preflight connected-plan`, `readiness`, and MCP
  `source_ids` support source-scoped planning, so one ready registered source
  can produce its own preflight, sync, smoke, and connected-run handoff without
  being blocked by another source whose auth state or token is not ready yet.
- GetCourse and Skillspace connected plans now include browser auth handoff
  packets that group registered sources by host, show state-file readiness, and
  provide capture, redacted inspect, and recheck commands before live sync is
  allowed.
- Browser connected plans distinguish fixture/example registry entries from
  operator-owned live sources. Reserved hosts such as `*.example` are marked as
  `fixture_or_example_source` with `operator_live_candidate: false`; live
  browser sync and connected-run commands are withheld until a real
  operator-owned course URL is registered and auth state matches that host.
- Connected-source plans can write a redacted Markdown runbook under runtime
  artifact storage, giving operators and agents a concrete setup, sync, smoke,
  calibration, and connected-run checklist without committing private source
  state. Generated preflight, smoke, connected-run, and calibration packet
  commands use the portable
  `${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}` fallback and the
  real `runs/<run>/connected/...` and `runs/<run>/calibration/...` artifact
  layouts.
- Live preflight distinguishes Stepik `public_api` sources from token-gated
  `api_token`/`oauth` sources and checks browser-session storage state against
  each registered source host before marking sync ready.
- Stepik source-registry sync route with fixture checkpoint proof, optional
  index/graph builds, CLI status, MCP status, and eval coverage.
- Stepik fixture/live smoke report routes that combine source registration,
  source-registry sync, index/graph build, answer evidence, and privacy-safe
  local raw API path reporting.
- Bounded public Stepik live calibration has been exercised through the
  connected-source route: preflight plus `smoke stepik-live` produced an
  `ok` live calibration packet with source-backed answer evidence, timestamps,
  and clean raw/secret privacy guards.
- Semantic and hybrid query routes through CLI and MCP, backed by a portable
  local semantic index artifact and collision guardrails.
- Answer-quality eval coverage that checks top-result source id, platform,
  lesson path, snippet terms, freshness timestamps, evidence fields, and
  connector-local eval-port boundaries instead of only JSON term presence.
- Freshness-aware result ranking with visible `rank_score`/`rank_features` and
  a conflict fixture proving current source-backed material beats stale material
  when base relevance is tied.
- Authority-aware result ranking with visible `authority_tier`,
  `authority_boost`, `rank_score`, and a conflict fixture proving official
  lesson text and mentor comments beat learner comments when base relevance is
  tied.
- Adapter-derived authority metadata for browser-session comments and Stepik
  official API objects, with `adapter-authority` eval coverage proving the
  signal survives normalized bundles, indexes, and query packets.
- The machine-readable adapter and source registries cover the full planned
  platform topology from the goal: working GetCourse, Skillspace, and Stepik;
  future Moodle, Canvas, Coursera, Teachable, Thinkific, and Kajabi entries
  without claiming their ingestion routes are implemented yet.
- Browser live preflight rejects unsafe origin substring matches and withholds
  the live sync command until registered source hosts match the saved browser
  storage state.
- Fixture-safe live calibration packets through `eval live-calibration` and
  `calibration build`, covering GetCourse, Skillspace, and Stepik smoke reports,
  answer evidence/timestamps, transcript/caption health, caption-resource
  errors, local raw-path handling, and secret/raw-payload privacy guards.
- Live calibration intake reports through `calibration intake`, turning partial
  calibration packet failures into repair lanes and repo-local eval-intake
  candidates while leaving central proof authority in `aoa-evals`.
- Executable connected-source calibration receipts through `calibration
  connected-run`: fixture mode proves source-registry sync, smoke reports,
  connected plan/runbook, calibration packet, and intake without network access;
  live browser runs reuse the same default account storage-state path that
  preflight checked and record `source_selection` plus per-stage source ids in
  receipts/status packets; connected-run receipts/status packets also include
  `execution_options` with query, browser `link_pattern`, source limit, and
  traversal bounds so later calibration work knows how broad the run was;
  live mode is gated by explicit `--allow-network`.
- Bounded public Stepik live connected-run has been exercised end to end through
  `calibration connected-run --mode live --allow-network`: the runtime receipt
  produced an `ok` connected-source plan, live sync, live smoke, calibration
  packet, and intake with source-backed answer evidence, timestamps, and clean
  raw/secret privacy guards.
- Connected-run receipts are inspectable through CLI `calibration status` and
  MCP `connected_run_status`, giving agents read-only access to stage summaries,
  packet quality, privacy flags, failures, next steps, artifact paths,
  `execution_options`, and `query_handoff` entries after fixture or gated live
  runs. Query handoff entries now include CLI commands and MCP `mcp_commands`
  for `search`, `lesson_context`, and `evidence_report`, so agents can stay on
  the MCP surface after a connected run. Partial connected-run receipts also
  include `repair_lanes` for network gate, source auth/readiness, source
  selection, source sync, live smoke/selector, and calibration-packet intake
  failures with concrete next commands.

## Remaining Goal Work

The next layer is live connected-source work:

- run gated live smoke with connected GetCourse and Skillspace accounts to
  calibrate real login redirects, theme selectors, and pagination behavior
  after `preflight connected-plan` reports ready local auth/source state and
  emits the runtime smoke/calibration commands;
- broader live selector coverage for real GetCourse and Skillspace themes where
  progress, comment, transcript, caption, and caption-sidecar resources use
  unusual markup or protected text-resource behavior;
- gated live full-course Stepik runs against operator-selected authenticated
  courses to calibrate real course size, permissions, and source enrichment;
- broader Stepik live smoke calibration against operator-selected authenticated
  courses, account discovery output, and full-course source-registry runs after
  `preflight live --platform stepik` confirms token/source readiness;
- collect connected-source live calibration packets from real GetCourse,
  Skillspace, and Stepik accounts and run `calibration intake` against partial
  packets to drive selector, sync, retrieval, privacy, and eval-intake follow-up
  work;
- live calibration of operator-selected external embedding endpoints beyond the
  local CI `http_json_v1` contract proof, using `preflight semantic-provider`
  first and then `build-semantic-index --provider http_json_v1` against the
  connected run;
- live-calibrated authority tiers from adapter/source metadata beyond current
  fixture-proven browser-role and Stepik official API signals;
- richer live smoke routes gated away from CI secrets.
