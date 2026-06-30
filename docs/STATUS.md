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
- graph construction for course/module/lesson/step/asset/topic/entity;
- answer packets with evidence chains and freshness timestamps;
- JSON-RPC stdio MCP tool surface with structured `tools/list` and
  `tools/call` responses;
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
  Playwright capture, and redacted storage-state inspection.
- Read-only live preflight reports for Stepik tokens, browser storage-state
  usability, source-registry readiness, next commands, secret redaction, and
  MCP `live_preflight` structuredContent.
- Read-only connected-source launch plans through CLI `preflight
  connected-plan` and MCP `connected_source_plan`, turning source readiness into
  exact preflight, sync, smoke, and calibration commands without touching the
  network or printing secrets. Stepik launch plans default to bounded live
  smoke/sync commands, with full-course/source-enrichment commands gated behind
  explicit options.
- GetCourse and Skillspace connected plans now include browser auth handoff
  packets that group registered sources by host, show state-file readiness, and
  provide capture, redacted inspect, and recheck commands before live sync is
  allowed.
- Connected-source plans can write a redacted Markdown runbook under runtime
  artifact storage, giving operators and agents a concrete setup, sync, smoke,
  and calibration checklist without committing private source state. Generated
  preflight, smoke, and calibration packet commands use the portable
  `${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}` fallback and the
  real `runs/<run>/calibration/...` artifact layout.
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
  local CI `http_json_v1` contract proof;
- live-calibrated authority tiers from adapter/source metadata beyond current
  fixture-proven browser-role and Stepik official API signals;
- richer live smoke routes gated away from CI secrets.
