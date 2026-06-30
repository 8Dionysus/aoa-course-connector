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
- graph construction for course/module/lesson/step/asset/topic/entity;
- answer packets with evidence chains and freshness timestamps;
- JSON-RPC stdio MCP tool surface with structured `tools/list` and
  `tools/call` responses;
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
- Live preflight distinguishes Stepik `public_api` sources from token-gated
  `api_token`/`oauth` sources and checks browser-session storage state against
  each registered source host before marking sync ready.
- Stepik source-registry sync route with fixture checkpoint proof, optional
  index/graph builds, CLI status, MCP status, and eval coverage.
- Stepik fixture/live smoke report routes that combine source registration,
  source-registry sync, index/graph build, answer evidence, and privacy-safe
  local raw API path reporting.
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
  answer evidence/timestamps, local raw-path handling, and secret/raw-payload
  privacy guards.

## Remaining Goal Work

The next layer is live connected-source work:

- run gated live smoke with connected GetCourse and Skillspace accounts to
  calibrate real login redirects, theme selectors, and pagination behavior
  after `preflight live` reports ready local auth/source state;
- broader live selector coverage for real GetCourse and Skillspace themes where
  progress and comment blocks use unusual markup;
- gated live full-course Stepik runs against operator-selected authenticated
  courses to calibrate real course size, permissions, and source enrichment;
- broader Stepik live smoke calibration against operator-selected authenticated
  courses, account discovery output, and full-course source-registry runs after
  `preflight live --platform stepik` confirms token/source readiness;
- collect connected-source live calibration packets from real GetCourse,
  Skillspace, and Stepik accounts and use their failures to drive selector,
  sync, and eval-intake follow-up work;
- external embedding provider integration behind the existing semantic index
  contract;
- live-calibrated authority tiers from adapter/source metadata beyond current
  fixture-proven browser-role and Stepik official API signals;
- richer live smoke routes gated away from CI secrets.
