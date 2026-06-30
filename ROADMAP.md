# Roadmap

## Now

- Prove offline course fixture ingestion, index, graph, query, and JSON-RPC
  stdio MCP tool shape.
- Prove Stepik as the first clean API reference adapter.
- Prove GetCourse and Skillspace through shared browser-session snapshot
  adapters.
- Prove GetCourse and Skillspace account-level source discovery into the local
  source registry from safe browser fixtures and optional live Playwright auth
  state.
- Prove source-registry driven sync checkpoints with optional per-source
  index/graph builds and MCP status.
- Prove MCP graph, freshness, and evidence-report calls so agents can inspect
  source-backed results without shelling into lower-level CLI internals.
- Prove bounded GetCourse and Skillspace course-tree crawling from safe browser
  fixtures and optional live Playwright auth state.
- Prove visible browser-session progress/status, comments, and paginated catalog
  receipt metadata from safe GetCourse and Skillspace fixtures.
- Prove visible browser-session transcript/caption extraction from safe
  GetCourse and Skillspace fixtures into canonical transcripts, index docs, and
  graph edges.
- Prove browser-session caption sidecar extraction from `<track>` resources and
  local snapshot `resources[]` into canonical transcripts, index docs, graph
  edges, smoke counts, and answer evals.
- Prove bounded GetCourse and Skillspace live discovery pagination route and
  unannotated DOM heuristics for progress/status/comments.
- Prove fixture/snapshot/live browser smoke reports that combine discovery,
  ingestion, index/graph build, and optional answer evidence checks.
- Prove browser-session auth-state planning, capture, and redacted inspection
  so live GetCourse/Skillspace routes have a reproducible onboarding step.
- Prove read-only live preflight reports so agents can verify Stepik token
  presence, browser auth-state usability, registered source readiness, and next
  commands through CLI and MCP before touching live sources.
- Prove read-only connected-source launch plans so agents can convert preflight
  readiness into exact preflight-report, source sync, per-source smoke, and
  calibration packet commands before touching live sources, with bounded
  Stepik commands by default and explicit full-course escalation.
- Prove browser auth handoff packets for GetCourse and Skillspace so blocked
  source hosts turn into exact storage-state capture, redacted inspection, and
  connected-plan recheck steps instead of vague missing-auth blockers.
- Prove connected-source runbook generation so the redacted plan becomes a
  runtime Markdown checklist for setup, sync, smoke, and calibration.
- Prove connector-local answer-quality evals that validate source identity,
  evidence fields, lesson path, snippets, freshness, and platform nuance beyond
  simple term presence.
- Prove freshness-aware ranking so current source-backed course material wins
  over stale material when base relevance is tied or close.
- Prove authority-aware ranking so official lessons and mentor comments win
  over learner comments when base relevance is tied or close.
- Prove adapter-derived authority metadata so browser-session roles and Stepik
  official API/source signals survive normalization, indexing, and query.
- Prove live calibration packets that summarize GetCourse, Skillspace, and
  Stepik smoke/preflight reports, answer evidence, transcript/caption health,
  and caption-resource errors without committing private payloads.
- Prove live calibration intake reports that classify partial packet failures
  into repair lanes and local eval-intake candidates without taking over
  `aoa-evals` central proof authority.
- Prove Stepik batched full-course API materialization with optional
  authenticated step-source enrichment.
- Prove Stepik source-registry driven sync checkpoints with optional
  index/graph builds, MCP status, and eval coverage.
- Prove Stepik account-level discovery into the source registry through a safe
  fixture and optional authenticated live route.
- Prove Stepik fixture/live smoke reports that combine registration, sync,
  artifacts, answer evidence, and privacy-safe local raw API path reporting.
- Prove a deterministic semantic/vector index baseline behind the stable keyword
  contract, including collision-only result guardrails.
- Document GetCourse and Skillspace hard-adapter strategy.
- Keep storage portable and safe for public clones.

## Next

- Run the gated live smoke route on connected GetCourse and Skillspace accounts
  after `preflight connected-plan` reports ready local state, then calibrate
  login redirects, pagination, DOM heuristics, and live calibration packet
  failures against real themes.
- Broaden GetCourse and Skillspace live DOM selectors for unusual progress,
  status, comments, transcript/caption, sidecar resources, and discussion
  markup found by live smoke.
- Run gated live full-course Stepik sync on an operator-selected authenticated
  course and calibrate permission/source-enrichment behavior.
- Broaden Stepik live smoke calibration beyond public bounded course checks.
- Calibrate Stepik account-level discovery against operator-selected
  authenticated accounts after `preflight live --platform stepik` reports token
  and source readiness where official scopes expose enough catalog data.
- Calibrate operator-selected external embedding endpoints against real course
  runs now that the stable `http_json_v1` semantic index contract exists.
- Calibrate adapter-provided authority tiers against live GetCourse,
  Skillspace, and Stepik source metadata beyond fixture-safe role/API signals.
- Broaden answer-quality evals against live-calibrated GetCourse, Skillspace,
  and Stepik runs once operator credentials are connected and
  `calibration intake` identifies recurring local eval pressure.

## Later

- Add Moodle, Canvas, Teachable, Thinkific, Kajabi, and Coursera adapters.
- Broaden transcript/caption extraction beyond WebVTT/SRT sidecars and visible
  browser-session blocks.
- Add richer eval suites for answer quality, freshness, and evidence coverage.
