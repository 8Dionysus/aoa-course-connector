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
PYTHONPATH=src python -m aoa_course_connector.cli eval install-route
PYTHONPATH=src python -m aoa_course_connector.cli sources answer "Stepik public API evidence" --platform stepik --mode hybrid
PYTHONPATH=src python -m aoa_course_connector.cli sources answer-matrix --query "Stepik public API evidence" --query "canonical course objects" --platform stepik --mode hybrid
PYTHONPATH=src python -m aoa_course_connector.cli eval source-registry-query --query "Stepik public API evidence" --query "canonical course objects" --platform stepik --kind smoke --mode hybrid
PYTHONPATH=src python -m aoa_course_connector.cli eval retrieval-loop
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
- CLI `lesson-context` returns one `aoa_course_lesson_context_packet_v1` with
  source-backed answer evidence plus nearby graph context for each distinct
  evidence lesson;
- CLI `eval retrieval-loop` prepares starter, GetCourse, Skillspace, and
  Stepik fixture runs, builds keyword/semantic indexes and graphs, and verifies
  CLI answer, CLI lesson-context, MCP search, MCP answer, MCP lesson_context,
  and MCP evidence_report in one network-free agent retrieval contract;
- evidence chains preserve freshness state, authority tier, source authority,
  rank score, rank features, and refresh hints alongside source URLs and
  fetched timestamps, so agents can cite and refresh the exact proof item;
- answer packets and MCP `answer`/`evidence_report` expose
  `aoa_course_answer_quality_summary_v1`, giving agents a compact `ready` flag,
  blockers, result/evidence counts, provenance coverage, refresh-hint coverage,
  and top-result identity before citation;
- JSON-RPC stdio MCP tool surface with structured `tools/list` and
  `tools/call` responses;
- MCP `list_sources` returns a read-only
  `aoa_course_source_registry_list_v1` catalog with registry path,
  platform/access-mode counts, `source_ids` and platform filters,
  disabled-source inclusion, `network_touched: false`, privacy flags, and an
  `include_source_refs: false` mode for agents that only need source ids and
  counts. The catalog also attaches bounded per-source
  `latest_connected_runs[]` from recent connected-run receipts, giving agents
  local query-ready run ids, query modes, artifact paths, CLI commands, and MCP
  commands without touching the network;
- CLI `sources list` returns the same
  `aoa_course_source_registry_list_v1` catalog directly, with platform/source-id
  filters, disabled-source inclusion, source-ref hiding, connected-run scan
  bounds, and no network access;
- MCP `source_answer` selects one configured source, finds its latest
  query-ready connected run, and returns answer, lesson-context, evidence, and
  quality packets without touching the network or exposing `source_ref` unless
  explicitly requested;
- MCP `sources_answer` asks one question across selected query-ready sources and
  returns per-source answer/context/evidence packets with aggregate quality,
  blockers, and `network_touched: false`, preserving provenance instead of
  collapsing results into an opaque summary;
- MCP `sources_answer_matrix` asks several questions across selected
  query-ready sources and returns one sources-answer packet per question plus
  aggregate breadth quality, per-query summaries, blockers, and
  `network_touched: false`;
- CLI/MCP `sources_answer_matrix` supports explicit `coverage_mode`: the
  default `all-sources` keeps strict per-source readiness, while `portfolio`
  reports ready when each query has at least one source-backed evidence chain
  across the selected source set. This prevents broad live-source matrices from
  looking failed only because unrelated but query-ready sources had no matching
  evidence for a specific question.
- CLI `eval source-registry-query` returns
  `aoa_course_eval_source_registry_query_v1`, a read-only gate over the current
  source registry that uses explicit operator queries or non-placeholder saved
  connected-run query samples, requires `sources_answer_matrix` ready-query
  breadth, evidence, response counts, `network_touched: false`, and
  `source_ref` redaction;
- connected-run query plans and source catalogs now attach direct CLI
  `sources answer` commands beside lower-level run-id `query`, `answer`, and
  `lesson-context` commands, so shell-side agents can ask one question against
  selected source ids without hand-writing MCP JSON;
- MCP `ingest_status` returns a read-only run readiness packet with normalized
  counts, materialization receipts, index/semantic/graph metadata, next
  commands, and `agent_query_ready`;
- fixture, Stepik, browser materialize, and browser source-sync receipts now
  include explicit `content_counts` plus top-level content counters for courses,
  modules, lessons, steps, assets, transcripts, assignments, threads, comments,
  topics, entities, and evidence, so agents can distinguish a bounded smoke
  sample from a full-course ingestion without reopening raw data;
- CLI `readiness` and MCP `connector_readiness` return one read-only
  `aoa_course_connector_readiness_v1` route audit with install-route files,
  storage roots, source registry counts, selected run/index/graph readiness,
  semantic provider readiness, connected-source plan status, compact
  `connected_run_plan`, connected-run receipt status, MCP tool coverage,
  registry-backed source query readiness, `operational_ready`,
  `connected_live_ready`, and next commands. When starter run artifacts are
  missing but recent source-registry connected-run receipts are query-ready,
  `lanes.source_registry_query_ready` keeps agent retrieval ready and
  `next_commands` points to `sources list`, `sources answer`, or
  `sources answer-matrix` before fixture bootstrap. The embedded connected plan
  preserves operator-selected `live_scope`, `include_step_sources`,
  `max_step_sources`, `step_source_timeout`, `link_pattern`, `max_lessons`,
  `max_pages`, and `max_sources` through the ready connected-run plan. If the
  selected connected-run receipt is partial
  and includes `repair_lanes`, the top-level readiness `next_commands` now
  surface those lane commands instead of replacing the receipt with fixture
  bootstrap;
- CLI `bootstrap fixture` returns `aoa_course_fixture_bootstrap_receipt_v1` and
  turns a fresh local state into a query-ready starter proof: storage roots,
  normalized starter bundle, keyword index, semantic index, graph, default
  GetCourse/Skillspace/Stepik fixture connected-run receipt, and embedded
  readiness without touching the network;
- CLI `eval install-route` returns `aoa_course_eval_install_route_v1` and proves
  the fresh-agent install path without network access: route docs, storage
  roots, bootstrap, readiness, CLI hybrid answer, MCP answer, connected-run
  status, query-plan readiness, source registry setup, and CLI/MCP
  source-scoped `sources_answer` retrieval;
- `scripts/verify_agent_install_route.py --skip-pytest` copies the repo into a
  temporary install-like workspace and verifies the same offline route plus MCP
  stdio direct `answer`, `connected_run_query`, and `sources_answer` packets
  plus the direct CLI `sources answer` route;
- CLI `connect profile`, `connect inspect`, `connect apply`, and MCP
  `connection_profile_inspect` provide the next operator-connection plan:
  a local `aoa_course_connection_profile_v1` runtime artifact for source refs,
  browser state-file paths, Stepik token env names, and semantic provider
  settings; a read-only `aoa_course_connection_profile_inspection_v1` for
  source registration/auth/connected-plan/semantic next commands, including
  browser-session Firefox import, capture, inspect, and preflight commands; and
  a registry-only apply step that does not touch the network or log token values.
  CLI `connect status` and MCP
  `connection_profile_status` return `aoa_course_connection_profile_status_v1`
  with `ready_for_connected_run`, `ready_for_semantic_build`, blockers,
  source/auth/plan counts, and ready live connected-run commands. CLI
  `connect run` and MCP `connection_profile_run_plan` turn the same profile
  into a selected platform/source plan without network by default:
  `aoa_course_connection_profile_run_receipt_v1` for CLI and
  `aoa_course_connection_profile_run_plan_v1` for MCP, with live execution only
  behind explicit CLI `--allow-network`;
- MCP agent routes for direct answer packets, lesson context, graph
  neighborhoods, freshness reports, and compact evidence reports. `answer`
  returns the source-backed `aoa_course_answer_packet_v1`, `lesson_context`
  returns that answer packet plus per-evidence lesson graph neighborhoods, and
  `evidence_report` keeps source URL, course path, fetched timestamp, freshness
  state, authority tier, rank score, refresh report, and per-result refresh
  hints;
- MCP `connected_run` executes the same connected-source calibration backend as
  CLI `calibration connected-run`: fixture mode proves the full connected route
  without network access and live mode remains gated behind explicit
  `allow_network`;
- answer/search/evidence packets now tell agents how to rebuild local indexes
  and graphs for the current run, how to run a bounded connected-source
  preflight, which local `answer`, `lesson-context`, and `evidence inspect`
  commands rerun the current query, and which registry-matched live sync route
  can refresh GetCourse, Skillspace, or Stepik sources without touching the
  network during planning;
- `refresh query` now wraps those hints into `aoa_course_refresh_cycle_v1`:
  a read-only plan by default with planned rebuild/query/source commands, a
  fixture-executable sync/checkpoint/rebuild loop for registered safe sources,
  and a live execution route gated behind explicit `--allow-network`; MCP
  exposes the read-only `refresh_plan` tool;
- source-registry sync routes and connected-source plan commands support
  `--source-id` scoped refreshes, so an agent can refresh one selected source
  without forcing a full platform sync;
- browser live crawl, materialize, sync, smoke, and connected-run routes
  preserve registered source ids in normalized bundles, answer evidence, stable
  identity summaries, and refresh hints. Generated browser smoke commands now
  include `--source-id`, so direct operator runs remain registry-refreshable
  instead of falling back to generic crawl source ids or lesson URL
  registration;
- sync checkpoints now carry a `stable_identity` fingerprint over canonical
  source/course/module/lesson/step/asset/transcript/assignment/discussion/evidence
  IDs, and evals require that fingerprint alongside keyword/semantic/graph
  artifact paths;
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
  `SyncCheckpoint` records, optional per-source keyword/semantic/graph builds,
  CLI status, MCP status, and evals.
- GetCourse and Skillspace bounded course-tree crawlers through fixtures,
  snapshot input, optional Playwright live traversal, and answer evals.
- Browser course-tree placeholders for unfetched lesson links now remain
  explicit discovery evidence in normalized bundles, indexes, answer packets,
  refresh hints, and graph nodes instead of being ranked as fetched official
  lesson text.
- Browser course-tree pages that are fetched but reveal a platform access
  denial, locked lesson, or unmet prerequisite notice now remain explicit
  access-state evidence. They are normalized with
  `freshness_state: access_denied`, `access_state: access_denied`,
  `authority_tier: access_notice`, and
  `source_authority: browser_access_denied`; graph confidence is reduced, and
  prerequisite boilerplate is not indexed as ordinary official lesson text.
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
- GetCourse live catalog discovery now also reads Chatium/app-proxy JSON
  training blocks from student app pages such as `/c/s/index`, so SPA-rendered
  training cards without plain `<a href>` links can still register canonical
  `/teach/control/stream/view/id/<id>` browser-session sources.
- Browser catalog discovery rejects pagination links even when a broad
  `link_pattern` would otherwise match them.
- Browser-session parser heuristics for unannotated, aria-only, and
  not-started progress/status blocks plus compact visible
  comment/reply/discussion blocks.
- Browser-session smoke route for fixture, operator snapshot, and gated live
  calibration reports without printing private raw HTML.
- Browser-session snapshot audit through CLI `inspect browser-snapshot`,
  returning `aoa_course_browser_snapshot_audit_v1` with discovery/crawl/
  materialization/smoke readiness, visible progress/comment/transcript/caption
  and pagination counts, caption sidecar repair lanes, and no raw HTML or
  caption text in the report. MCP exposes the same read-only audit as
  `browser_snapshot_audit` so agents can diagnose runtime snapshots without
  leaving the MCP surface. Browser smoke reports now embed compact
  `snapshot_audits[]` summaries for discovery/course raw snapshots, and live
  calibration packets aggregate snapshot-audit counts, readiness, failures, and
  repair lanes.
- Browser-session auth-state onboarding through CLI planning, optional
  Firefox cookie import, Playwright capture, expected-origin capture receipts,
  and redacted storage-state inspection. `auth plan-browser-state` and
  connected-source plans carry `--expect-origin-contains` so wrong-login or
  cross-school storage-state mismatches are visible before live discovery or
  sync.
- Stepik, GetCourse, and Skillspace browser-session onboarding can import
  matching cookies from an existing local Firefox profile into a
  Playwright-compatible storage-state file, with a redacted no-network receipt
  and no cookie values printed.
- Stepik account discovery uses both enrollment data and `course-grades`, so
  accounts whose current `/enrollments` endpoint is empty can still expose
  queryable course sources.
- Read-only live preflight reports for Stepik tokens, browser storage-state
  usability, source-registry readiness, next commands, secret redaction, and
  MCP `live_preflight` structuredContent.
- Source-registry answer routes can now use query-ready sync checkpoints in
  addition to connected-run receipts, so `sources answer` works after a direct
  source sync with indexes and graph artifacts.
- Read-only connected-source launch plans through CLI `preflight
  connected-plan` and MCP `connected_source_plan`, turning source readiness into
  exact preflight, sync, smoke, calibration, and
  `connected_run_plan` commands without touching the network or printing
  secrets. Ready plans preserve selected platforms, source ids, query, live
  scope, browser `link_pattern`, and Stepik `include_step_sources` budget in the
  one-command `calibration connected-run --mode live --allow-network` route.
  Stepik launch plans default to bounded live smoke/sync commands, with
  full-course/source-enrichment commands gated behind explicit options. Ready
  `connected_run_plan` entries now also expose `mcp_tool_call` and
  `mcp_command` for MCP `connected_run`, preserving source ids, traversal
  bounds, live scope, `max_step_sources`, `step_source_timeout`, and explicit
  `allow_network`. Partial plans with at least
  one smoke-ready source now expose a `scope: ready_subset`
  `connected_run_plan` for the ready platform/source ids while keeping blockers
  for missing Skillspace auth, Stepik tokens, or other unready sources visible;
- `preflight live`, `preflight connected-plan`, `readiness`, and MCP
  `source_ids` support source-scoped planning, so one ready registered source
  can produce its own preflight, sync, smoke, and connected-run plan without
  being blocked by another source whose auth state or token is not ready yet.
- GetCourse and Skillspace connected plans now include browser auth plan
  packets that group registered sources by host, show state-file readiness, and
  provide Firefox import, capture, redacted inspect, and recheck commands
  before live sync is allowed.
- Browser auth plans include per-host `state_file_candidates` with
  host-specific state-file paths plus Firefox import, capture, inspect, and
  source-scoped recheck commands for multi-school/custom-domain GetCourse and
  Skillspace registries.
- Browser connected plans distinguish fixture/example registry entries from
  operator-owned live sources. Reserved hosts such as `*.example` are marked as
  `fixture_or_example_source` with `operator_live_candidate: false`; live
  browser sync and connected-run commands are withheld until a real
  operator-owned course URL is registered and auth state matches that host.
- Connected-source plans emit concrete setup, sync, smoke, calibration, and
  connected-run commands without committing private source state. Generated
  preflight, smoke, connected-run, and calibration packet
  commands use the portable
  `${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}` fallback and the
  real `runs/<run>/connected/...` and `runs/<run>/calibration/...` artifact
  layouts.
- Live preflight distinguishes Stepik `public_api` sources from token-gated
  `api_token`/`oauth` sources; Stepik `browser_session` sources can now use a
  captured `stepik.org` storage-state file for account discovery, live sync,
  smoke, and connected-run execution without printing cookie values.
- Stepik source-registry sync route with fixture checkpoint proof, optional
  keyword/semantic/graph builds, CLI status, MCP status, and eval coverage.
- Stepik fixture/live smoke report routes that combine source registration,
  source-registry sync, keyword/semantic/graph build, answer evidence, and
  privacy-safe local raw API path reporting.
- Bounded public Stepik live calibration has been exercised through the
  connected-source route: preflight plus `smoke stepik-live` produced an
  `ok` live calibration packet with source-backed answer evidence, timestamps,
  and clean raw/secret privacy guards.
- Semantic and hybrid query routes through CLI and MCP, backed by a portable
  local semantic index artifact and collision guardrails.
- Answer-quality eval coverage that checks top-result source id, platform,
  lesson path, snippet terms, freshness timestamps, evidence fields, and
  connector-local eval-port boundaries instead of only JSON term presence.
- Browser and Stepik smoke reports embed
  `aoa_course_answer_quality_summary_v1` proof-field checks, so connected
  calibration packets fail into retrieval-quality repair lanes when answer
  results lack source ids, source URLs, timestamps, lesson paths, platform
  matches, freshness/authority fields, refresh hints, or complete provenance.
- Freshness-aware result ranking with visible `rank_score`/`rank_features` and
  a conflict fixture proving current source-backed material beats stale material
  when base relevance is tied. Answer packets also include
  `aoa_course_temporal_answer_report_v1`, so agents can see timestamp coverage,
  version groups, and detected current/stale conflicts without recomputing the
  graph.
- Place-aware ranking preserves native hierarchy fields such as thread title,
  author label, attachment title/URL, access state, and download state in index
  docs and evidence chains, with `place-ranking` proving source-path accuracy
  and evidence attribution for thread/comment and attachment lookups.
- Authority-aware result ranking with visible `authority_tier`,
  `authority_boost`, `rank_score`, and a conflict fixture proving official
  lesson text and mentor comments beat learner comments when base relevance is
  tied.
- Adapter-derived authority metadata for browser-session comments and Stepik
  official API objects, with `adapter-authority` eval coverage proving the
  signal survives normalized bundles, indexes, and query packets.
- The machine-readable adapter and source registries cover the full planned
  platform topology: working GetCourse, Skillspace, and Stepik;
  future Moodle, Canvas, Coursera, Teachable, Thinkific, and Kajabi entries
  without claiming their ingestion routes are implemented yet.
- Browser live preflight rejects unsafe origin substring matches, tracking-only
  storage states without an auth signal, and withholds the live sync command
  until registered source hosts match the saved browser storage state.
- Fixture-safe live calibration packets through `eval live-calibration` and
  `calibration build`, covering GetCourse, Skillspace, and Stepik smoke reports,
  answer evidence/timestamps, transcript/caption health, caption-resource
  errors, local raw-path handling, and secret/raw-payload privacy guards.
- Live calibration intake reports through `calibration intake`, turning partial
  calibration packet failures into repair lanes and repo-local eval-intake
  candidates while leaving central proof authority in `aoa-evals`.
- Executable connected-source calibration receipts through `calibration
  connected-run`: fixture mode proves source-registry sync, smoke reports,
  connected plan, calibration packet, and intake without network access;
  live browser runs reuse the same default account storage-state path that
  preflight checked and record `source_selection` plus per-stage source ids in
  receipts/status packets; connected-run receipts/status packets also include
  `execution_options` with query, browser `link_pattern`, source limit, and
  traversal bounds plus compact `snapshot_audit` health/repair status so later
  calibration work knows how broad the run was and whether browser snapshots
  need diagnostics;
  live mode is gated by explicit `--allow-network`.
- Bounded public Stepik live connected-run has been exercised end to end through
  `calibration connected-run --mode live --allow-network`: the runtime receipt
  produced an `ok` connected-source plan, live sync, live smoke, calibration
  packet, and intake with source-backed answer evidence, timestamps, and clean
  raw/secret privacy guards.
- A runtime-only Stepik full-course sync for course `268845` has been exercised
  locally through source `source:stepik:2df698200b`: sync run
  `stepik-full-course-telegram-counts-20260708` completed `ok` at
  `2026-07-08T08:45:45Z`, produced 1 course, 4 modules, 15 lessons, 101 steps,
  81 assignments, 117 evidence items, keyword/semantic/graph artifacts, and a
  materialization receipt with matching `content_counts`. CLI
  `sources answer-matrix` answered 4/4 aiogram/Telegram-bot questions with 20
  total evidence items, and MCP `sources_answer_matrix` answered 3/3 with 15
  total evidence items; both retrieval checks used the local indexes/graphs
  with `network_touched: false` and top results from the same fresh sync run.
- A runtime-only Stepik full-course connected run for course `6667`
  (`source:stepik:9b777d98bf`) has been exercised locally through
  `calibration connected-run --mode live --allow-network --live-scope
  full-course --include-step-sources`: run
  `stepik-full-course-live-nosmoke-refetch-20260708` completed `ok` at
  `2026-07-08T09:39:28Z`, produced 1 course, 5 modules, 60 lessons, 556 steps,
  401 assignments, 71 assets, 617 evidence items, keyword/semantic/graph
  artifacts, and stable identity fingerprint
  `sha256:6edf0c0d75042b94ed86632c55f5d2d342f4546dddf9432e19391980e7c29494`.
  The Stepik smoke stage reused the completed sync receipt
  (`source_mode: stepik_live_smoke_from_sync`) and stayed
  `network_touched: false`, avoiding a second live Stepik traversal after sync.
  CLI `calibration query-matrix` and MCP `connected_run_query_matrix` each
  answered 2/2 philosophy-course questions from local indexes/graphs with 20
  total evidence items, graph context for every query, and
  `network_touched: false`. Step-source enrichment is now budgeted: this run
  attempted 10 step-source payloads, skipped 546 by `max_step_sources`, and
  recorded the effective limits plus diagnostics in the raw Stepik payload. The
  same budget now flows through CLI/MCP `readiness`, `connected_source_plan`,
  connection profiles, and MCP `connected_run` arguments instead of only the
  direct CLI live command.
- A runtime-only multi-source GetCourse plus Stepik connected run has been
  exercised locally: run `connected-ready-getcourse-stepik-20260708` completed
  `ok` at `2026-07-08T08:54:25Z` across 6 ready sources
  (`source:getcourse:15b891afce`, `source:getcourse:c991bf28c8`, and four
  Stepik sources). It produced healthy live sync, live smoke, calibration
  packet, and intake stages, 0 repair lanes, clean raw/secret privacy flags, 2
  healthy browser snapshot audits, 14 visible transcripts, and 21 source-backed
  smoke evidence items. CLI `calibration query-matrix` then answered 3/3
  operator questions from local indexes/graphs with `network_touched: false`,
  41 evidence items, 43 results, and graph context for every query. MCP
  `connected_run_query_matrix` answered the same 3/3 questions with
  `network_touched: false`, 55 evidence items, 57 results, all 6 source ids,
  and graph context for every query.
- Operator-owned GetCourse live connected-run has been exercised locally with
  runtime-only artifacts: preflight, live sync, smoke, calibration packet,
  intake, CLI `calibration query`, and MCP `connected_run_query` returned `ok`;
  answer evidence and refresh hints preserved the registered source id with
  `registry_match: true` and no raw payloads or secret values in shareable
  packets.
- A runtime-only operator GetCourse access-state proof has been exercised
  locally: one bounded live run produced one visible/current lesson and six
  `access_denied` lesson notices, kept raw/secret privacy guards clean, passed
  CLI and MCP `calibration query-matrix` for three course questions from local
  indexes/graphs, and ranked an access-intent query first to
  `access_notice`/`browser_access_denied` without touching the network during
  retrieval.
- A runtime-only ready-subset GetCourse proof has been exercised locally: a
  default connected-source plan stayed `partial` because Skillspace auth and
  Stepik token state were not ready, but exposed a `scope: ready_subset`
  `connected_run_plan` for two ready GetCourse source ids. The gated live run
  returned `ok`, selected both sources, produced no repair lanes, kept
  raw/secret privacy guards clean, and CLI/MCP `connected_run_query_matrix`
  answered two questions across both sync runs with evidence, graph context,
  and `network_touched: false`.
- A runtime-only GetCourse Chatium/student-app discovery proof has been
  exercised locally: `/user/my/profile` still exposed no course links, while
  `/c/s/index` returned two registered training sources through the app-proxy
  JSON route and no raw secrets were printed. The newly expected free-course
  source was not visible in the connected account during this bounded check.
- Connected-run receipts are inspectable through CLI `calibration status` and
  MCP `connected_run_status`, giving agents read-only access to stage summaries,
  packet quality, `snapshot_audit`, privacy flags, failures, next steps,
  artifact paths, `execution_options`, and `query_plan` entries after fixture
  or gated live runs. Query plan entries now include selected `query_mode`, CLI
  commands, and MCP `mcp_commands` for `search`, `answer`, `lesson_context`,
  and `evidence_report`, plus direct CLI `lesson-context`, so agents can inspect
  source-backed answer and graph
  context after a connected run. Partial connected-run receipts also include
  `repair_lanes` for network gate, source auth/readiness, source
  selection, source sync, live smoke/selector, and calibration-packet intake
  failures with concrete next commands; Stepik repair/rerun commands preserve
  the selected `include_step_sources`, `max_step_sources`, and
  `step_source_timeout` budget from `execution_options`.
- CLI `calibration query` and MCP `connected_run_query` execute that
  connected-run query plan without touching the network, returning
  `aoa_course_connected_run_query_packet_v1` with per-entry source-backed
  answer packets, lesson context, evidence reports, freshness/authority quality
  summaries, graph-context status, rebuild/query blockers, and direct
  `network_touched: false` retrieval proof after fixture or gated live
  connected runs.
- CLI `calibration query-matrix` and MCP `connected_run_query_matrix` execute
  several course-specific questions against the same connected-run query plan
  without touching the network, returning
  `aoa_course_connected_run_query_matrix_v1` with one per-question
  `aoa_course_connected_run_query_packet_v1`, compact top-result summaries,
  aggregate evidence/result/graph-context quality, blockers, and replay
  commands. This gives agents a breadth check for whether one connected run can
  answer multiple real questions from local indexes and graphs instead of only
  replaying a single smoke query.

## Remaining Connector Work

The next layer is broader live connected-source work:

- connect a Skillspace account/source into
  `${AOA_COURSE_AUTH_ROOT:-.connector-state/auth}/skillspace/account.storage-state.json`
  and the source registry, then run the same gated live sync, smoke,
  calibration, CLI query-matrix, and MCP query-matrix route that is now proven
  for the GetCourse plus Stepik ready subset;
- run gated live smoke with additional operator-owned GetCourse courses to
  calibrate real login redirects, theme selectors, and pagination behavior
  after `preflight connected-plan` reports ready local auth/source state and
  emits the runtime smoke/calibration commands;
- broader live selector coverage for real GetCourse and Skillspace themes where
  progress, comment, transcript, caption, and caption-sidecar resources use
  unusual markup or protected text-resource behavior;
- additional gated live full-course Stepik runs against operator-selected
  authenticated courses, including deliberately wider `--max-step-sources`
  budgets where needed, to calibrate course size variance, permissions, and
  source enrichment beyond the currently proven courses;
- broader Stepik live smoke calibration against operator-selected authenticated
  courses, account discovery output, and full-course source-registry runs after
  `preflight live --platform stepik` confirms token/source readiness;
- collect connected-source live calibration packets from real GetCourse,
  Skillspace, and Stepik accounts; run `calibration query-matrix`/MCP
  `connected_run_query_matrix` over multiple operator questions; and run
  `calibration intake` against partial packets to drive selector, sync,
  retrieval, privacy, and eval-intake follow-up work;
- live calibration of operator-selected external embedding endpoints beyond the
  local CI `http_json_v1` contract proof, using `preflight semantic-provider`
  first and then `build-semantic-index --provider http_json_v1` against the
  connected run;
- live-calibrated authority tiers from adapter/source metadata beyond current
  fixture-proven browser-role and Stepik official API signals;
- richer live smoke routes gated away from CI secrets.
