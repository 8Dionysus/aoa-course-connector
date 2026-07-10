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
PYTHONPATH=src python -m aoa_course_connector.cli eval connected-portfolio
PYTHONPATH=src python -m aoa_course_connector.cli eval ingest-coverage
PYTHONPATH=src python -m aoa_course_connector.cli eval corpus-integrity
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
- graph construction for course/module/lesson/step/asset/transcript/assignment/
  discussion/topic/entity objects;
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
- Cross-source summaries now rerank per-source winners with comparable
  `portfolio_rank_score` and expose lexical/path coverage, term proximity, and
  `portfolio_confidence`. Portfolio mode compares each source's local Top-K
  candidates while retaining `source_result_rank`. Compound and inflected terms such as
  `онлайн-школу` versus `онлайн-школы` no longer lose to unrelated run-local
  semantic scores, while low-confidence unrelated queries remain visible as
  abstentions.
- CLI `eval connected-portfolio` returns
  `aoa_course_eval_connected_portfolio_v1`. Its public fixture suite checks
  GetCourse, Skillspace, Stepik, a cross-source collision, Top-1 native paths,
  source/freshness fields, and one negative query without network access.
- Browser and Stepik raw payloads, materialization receipts, sync checkpoints,
  connected query plans, and source catalogs carry
  `aoa_course_ingest_coverage_v1`. Browser runs count the visible lesson
  inventory before applying `max_lessons`; Stepik runs compare referenced and
  fetched section/unit/lesson/step IDs and report `step_sources` separately as
  optional enrichment.
- Sync checkpoints carry `aoa_course_identity_continuity_v1`, comparing each
  refresh with the previous normalized snapshot by canonical IDs while keeping
  prior run artifacts intact. Bounded refresh removals are marked
  `inconclusive_incomplete_ingest` instead of being mistaken for source
  deletion.
- CLI `eval ingest-coverage` proves complete fixture inventories for
  GetCourse, Skillspace, and Stepik, stable refresh history, and a deliberate
  bounded-browser probe. `--skip-prepare` applies the same read-only gate to
  operator checkpoints.
- CLI `eval corpus-integrity` returns
  `aoa_course_eval_corpus_integrity_v1` and selects the latest checkpoint for
  each source, including failures. Its independent normalized-object inventory
  rejects missing or duplicate index/graph records, dangling edges, invalid
  vectors/postings, invalid BM25 scoring metadata, evidence gaps, stale artifact metadata, and retrieval
  misses. The isolated fixture proof passes 7/7 GetCourse, Skillspace, and
  Stepik sources with place-grounded Recall@5 of 1.0.
- MCP `artifact_integrity` exposes the same per-run
  `aoa_course_artifact_integrity_v1` read-only contract. It does not invoke an
  external semantic provider during audit, preserving `network_touched: false`.
- The current private runtime proof passes 6/6 latest connected GetCourse and
  Stepik sources: 2,854 keyword/semantic documents, 3,286 graph nodes, complete
  evidence and graph coverage, zero dangling edges/posting failures, valid BM25
  contracts, and 521/521 deterministic place-grounded Recall@5 probes. Strict
  exact-document Recall@5 remains a separate 0.775432 diagnostic for duplicate
  records inside the correct native hierarchy. Runtime reports and source data
  remain gitignored.
- Keyword artifacts now carry a validated BM25 contract with body-text length
  normalization, IDF, and a content-aware query stop-term gate. Legacy TF
  artifacts remain query-readable but do not satisfy corpus integrity until
  rebuilt.
- Hybrid ranking uses a deeper candidate pool and transparent BM25, semantic,
  lexical, full-query, and native-path alignment components. Technical IDs do
  not count as human breadcrumbs; regression tests prove exact short matches
  and all-term candidates survive long or partially matching distractors.
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
  source-scoped `sources_answer` retrieval. Its fixture state is isolated, so
  the operator source registry and checkpoints remain byte-identical;
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
- Private runtime validation has exercised multiple authorized GetCourse and
  Stepik sources through discovery, full-course sync, stable refresh, local
  keyword/semantic/graph builds, access-state handling, and CLI/MCP query
  matrices. Retrieval remained local after ingest (`network_touched: false`),
  and the shareable proof exposed no raw payloads or secret values.
- The anonymized connected-source gate passed six sources, 2,854 index
  documents, 3,286 graph nodes, 521/521 place-grounded Recall@5 probes, and
  11/11 subject/path/morphology/collision/negative portfolio cases. Operator
  source references, source IDs, course titles, run names, timestamps,
  fingerprints, and benchmark inputs remain only in gitignored runtime
  storage.
- Stepik full-course smoke can reuse a completed sync instead of traversing the
  source twice. Optional step-source enrichment is explicitly budgeted and the
  selected limits flow through CLI/MCP readiness, connected plans, connection
  profiles, and connected-run execution.
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

## Known Platform Gap

Live Skillspace validation still requires an authorized operator account and
source. The repository already contains the fixture-proven hard adapter,
storage-state capture/import route, discovery and sync contracts, local
index/graph/query path, gated live commands, and manual validation guide needed
to exercise that final platform-specific route without another architecture
slice.
