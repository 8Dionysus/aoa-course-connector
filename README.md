# aoa-course-connector

`aoa-course-connector` is a GitHub-publishable AoA connector for turning
authorized course-platform access into local searchable course knowledge,
evidence packets, and course graphs.

The connector is not a downloader first. Its job is to let an agent answer
questions from course sources with lesson paths, snippets, freshness, and source
evidence.

## Offline Starter Proof

```bash
python scripts/validate_connector.py
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m aoa_course_connector.cli doctor
PYTHONPATH=src python -m aoa_course_connector.cli bootstrap fixture --run starter-fixture --connected-run connected-calibration
PYTHONPATH=src python -m aoa_course_connector.cli readiness --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli materialize fixture --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli preflight semantic-provider --run starter-fixture --require-ready
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "bootloader unlock rollback"
PYTHONPATH=src python -m aoa_course_connector.cli answer "bootloader rollback" --mode hybrid
PYTHONPATH=src python -m aoa_course_connector.cli lesson-context "bootloader rollback" --mode hybrid --graph-limit 12
PYTHONPATH=src python -m aoa_course_connector.cli eval install-route
PYTHONPATH=src python -m aoa_course_connector.cli sources answer "Stepik public API evidence" --platform stepik --mode hybrid
PYTHONPATH=src python -m aoa_course_connector.cli sources answer-matrix --query "Stepik public API evidence" --query "canonical course objects" --platform stepik --mode hybrid
PYTHONPATH=src python -m aoa_course_connector.cli eval source-registry-query --query "Stepik public API evidence" --query "canonical course objects" --platform stepik --kind smoke --mode hybrid
PYTHONPATH=src python -m aoa_course_connector.cli eval connected-portfolio
PYTHONPATH=src python -m aoa_course_connector.cli eval ingest-coverage
PYTHONPATH=src python -m aoa_course_connector.cli eval corpus-integrity
PYTHONPATH=src python -m aoa_course_connector.cli eval retrieval-loop
```

The starter path creates:

- normalized course objects from a safe fixture;
- a local keyword index;
- a deterministic local semantic/vector index (`local_hashing_v1`);
- an optional HTTP JSON semantic provider (`http_json_v1`) for
  operator-configured embedding endpoints;
- a course graph;
- answer packets with source-backed evidence.

`eval retrieval-loop` is the fixture-safe agent contract for the complete
retrieval path. It prepares starter, GetCourse, Skillspace, and Stepik runs,
builds keyword/semantic indexes and graphs, then checks CLI answer, CLI
lesson-context, MCP search, MCP answer, MCP lesson_context, and MCP
evidence_report with source evidence, graph context, and answer `quality`
readiness.

`eval connected-portfolio` is the fixture-safe cross-source quality gate. It
proves that GetCourse, Skillspace, and Stepik questions select the expected
platform and native course path, that cross-run results are reranked by
query/path alignment rather than incomparable run-local scores, and that an
unrelated query is not reported as a confident match. Pass `--suite` with a
gitignored runtime suite and `--skip-prepare` to apply the same contract to
already connected operator sources without touching the network.

`eval ingest-coverage` is the fixture-safe structural completeness and refresh
continuity gate. It proves that source inventories are exhausted for the
selected scope, limits and fetch gaps are explicit, canonical IDs remain
stable, and previous snapshots survive refresh. Its bounded probe must report
truncation instead of presenting omitted lessons as source deletions. Use
`--skip-prepare` with platform/source filters to audit existing checkpoints.

`eval corpus-integrity` independently compares normalized canonical objects
with keyword and semantic documents, vectors, inverted postings, evidence, and
graph nodes/edges. Deterministic probes report strict exact-document Recall@K
and place-grounded Recall@K for the correct course or lesson. The default run
uses isolated fixtures; `--skip-prepare` audits the latest selected source
checkpoints without touching the network or returning source URLs.

`bootstrap fixture` is the shortest fresh-install route. It creates storage,
materializes the starter fixture, builds keyword/semantic indexes and the graph,
runs fixture connected-source calibration for GetCourse, Skillspace, and Stepik,
and returns the final readiness packet without touching the network.
`eval install-route` is the executable fresh-agent proof for that route: it
checks route docs, storage roots, bootstrap, readiness, CLI hybrid answer, MCP
answer, CLI/MCP source-scoped `sources_answer`, connected-run status,
query-plan readiness, and source registry setup with `network_touched: false`.
It uses isolated temporary storage and does not add fixture sources or
checkpoints to the operator registry.
`connect profile` turns those operator inputs into a local runtime JSON
contract, `aoa_course_connection_profile_v1`. It stores source refs, state-file
paths, token env names, and semantic-provider settings under artifact storage,
but never stores token values. `connect inspect` is read-only and returns the
source registration, browser auth, connected-plan, and semantic-provider next
commands with `network_touched: false`. `connect apply` mutates only the local
source registry, then returns the same inspection so the next `preflight connected-plan` or MCP
`connection_profile_inspect` call can continue from registered sources.
`connect status` and MCP
`connection_profile_status` return the compact
`aoa_course_connection_profile_status_v1` go/no-go packet with
`ready_for_connected_run`, blockers, counts, and any ready
`calibration connected-run --mode live --allow-network` commands. MCP
`connection_profile_run_plan` exposes the same selected
`aoa_course_connection_profile_run_plan_v1` without touching the network.
`connect run` loads the same profile and selected platform/source, returns a
no-network `aoa_course_connection_profile_run_receipt_v1` plan by default, and
executes the ready live connected-run only when `--allow-network` is present.

`readiness` is the read-only agent plan for the whole connector surface. It
returns `aoa_course_connector_readiness_v1` with storage roots, source registry
counts, run/index/graph readiness, connected-source plan status, MCP tool
coverage, semantic provider readiness, `operational_ready`,
`connected_live_ready`, and concrete next commands without touching the
network. For browser-session sources,
`--link-pattern` flows into the embedded connected-source plan so a ready
readiness packet can expose the same narrowed `connected_run_plan` command.
Use `--max-lessons`, `--max-pages`, `--max-sources`, `--live-scope`, and
`--include-step-sources` when the whole-connector audit must preserve the same
operator-selected live traversal bounds that will later be used by the
connected run.

To build the same semantic index contract through an external embedding
endpoint, keep the token in the environment and pass only the env var name:

```bash
export AOA_COURSE_EMBEDDING_TOKEN=...
PYTHONPATH=src python -m aoa_course_connector.cli preflight semantic-provider --run starter-fixture --provider http_json_v1 --embedding-endpoint "http://127.0.0.1:8000/embeddings" --embedding-model "local-course-embedding" --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN --require-ready
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run starter-fixture --provider http_json_v1 --embedding-endpoint "http://127.0.0.1:8000/embeddings" --embedding-model "local-course-embedding" --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN
PYTHONPATH=src python -m aoa_course_connector.cli query "bootloader rollback" --run starter-fixture --mode semantic
```

`preflight semantic-provider` is read-only and does not call the endpoint. It
checks the normalized bundle, endpoint/model configuration, token environment
variable presence, and redaction policy before the first network-touching
semantic build. The semantic index artifact records provider metadata and the
token environment variable name, but not the token value. MCP
`semantic_search` reads the same provider contract as the CLI query route.

The retrieval loop also exposes a base relevance `score`,
`authority_tier`, and a freshness/authority/provenance adjusted `rank_score`.
To prove current evidence wins over stale evidence when relevance is tied:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli materialize fixture --run freshness-ranking-fixture --fixture connector/fixtures/course/freshness_conflict_course.json
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run freshness-ranking-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run freshness-ranking-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval freshness-ranking
```

To prove higher-authority evidence wins over lower-authority evidence when
relevance is tied:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli materialize fixture --run authority-ranking-fixture --fixture connector/fixtures/course/authority_conflict_course.json
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run authority-ranking-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run authority-ranking-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval authority-ranking
```

## Stepik Clean API Proof

The first clean API adapter is Stepik. CI uses a safe Stepik-shaped fixture:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli materialize stepik-fixture --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "Stepik public API evidence" --run stepik-fixture
```

For a bounded live public API smoke:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli materialize stepik-live 67 --run stepik-live-smoke --max-sections 1 --max-units-per-section 1 --max-steps-per-lesson 2
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run stepik-live-smoke
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run stepik-live-smoke
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run stepik-live-smoke
PYTHONPATH=src python -m aoa_course_connector.cli query "Python course" --run stepik-live-smoke --mode hybrid
```

For an operator-selected full-course Stepik sync:

```bash
export STEPIK_API_TOKEN=...
PYTHONPATH=src python -m aoa_course_connector.cli materialize stepik-live 67 --run stepik-full-course --full-course --batch-size 20 --include-step-sources
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run stepik-full-course
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run stepik-full-course
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run stepik-full-course
PYTHONPATH=src python -m aoa_course_connector.cli answer "course-specific question" --run stepik-full-course --mode hybrid
```

`--full-course` removes the smoke limits, `--batch-size` uses Stepik `ids[]`
multi-ID API reads, and `--include-step-sources` performs best-effort source
enrichment when the connected account is allowed to read it.

Stepik also participates in the source registry and sync checkpoint route:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli discover stepik-account --from-fixture --run stepik-account-discovery-fixture --register --source-limit 1
PYTHONPATH=src python -m aoa_course_connector.cli discover stepik 67 --register --title "Stepik course 67"
PYTHONPATH=src python -m aoa_course_connector.cli sync stepik-fixture --run stepik-sync-fixture --source-id "source:stepik:..." --build-artifacts
PYTHONPATH=src python -m aoa_course_connector.cli sync status --run stepik-sync-fixture --platform stepik
PYTHONPATH=src python -m aoa_course_connector.cli refresh query "Stepik public API evidence" --run "<checkpoint-run-id>" --mode hybrid --strategy fixture --execute --sync-run stepik-refresh-cycle
PYTHONPATH=src python -m aoa_course_connector.cli eval stepik-sync
```

Successful sync checkpoints include `stable_identity.fingerprint`, counts, and
samples for canonical course/lesson/step/evidence IDs. Repeat sync runs for the
same registered source should keep that fingerprint stable while producing a
new child `run_id` for fresh artifacts.

For live source-registry sync, register the course once and run:

```bash
export STEPIK_API_TOKEN=...
PYTHONPATH=src python -m aoa_course_connector.cli preflight live --platform stepik --stepik-token-env STEPIK_API_TOKEN
PYTHONPATH=src python -m aoa_course_connector.cli discover stepik-account --run stepik-account-discovery-live --token-env STEPIK_API_TOKEN --register --max-pages 5
PYTHONPATH=src python -m aoa_course_connector.cli sync stepik-live --run stepik-live-sync --source-id "source:stepik:..." --full-course --batch-size 20 --include-step-sources --build-artifacts
```

If the operator already captured a Stepik browser session, the same account
discovery and sync route can use local browser-state cookies instead of a
separate API token:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli auth import-firefox-state stepik account --state-file "$AOA_COURSE_AUTH_ROOT/stepik/account.storage-state.json" --expect-origin-contains stepik.org
PYTHONPATH=src python -m aoa_course_connector.cli auth capture-browser-state stepik account --login-url "https://stepik.org/users/me" --state-file "$AOA_COURSE_AUTH_ROOT/stepik/account.storage-state.json" --expect-origin-contains stepik.org
PYTHONPATH=src python -m aoa_course_connector.cli discover stepik-account --state-file "$AOA_COURSE_AUTH_ROOT/stepik/account.storage-state.json" --register --max-pages 5
PYTHONPATH=src python -m aoa_course_connector.cli sync stepik-live --state-file "$AOA_COURSE_AUTH_ROOT/stepik/account.storage-state.json" --source-id "source:stepik:..." --full-course --batch-size 20 --include-step-sources --build-artifacts
```

`preflight live --platform stepik` treats registered `public_api` sources as
sync-ready without `STEPIK_API_TOKEN`; token-gated `api_token` and `oauth`
sources require the token, while `browser_session` sources require matching
Stepik storage state. `auth import-firefox-state` is the no-network shortcut
when the operator is already logged in through Firefox; `auth
capture-browser-state` remains the fresh-login fallback. Account discovery
ignores inactive or deleted enrollments before registering sources. Token and
cookie values are never printed.

For a single Stepik operator smoke report:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli smoke stepik-fixture 67 --run stepik-smoke-fixture --query "Stepik public API evidence"
PYTHONPATH=src python -m aoa_course_connector.cli smoke stepik-live 67 --run stepik-live-public-smoke --query "Python course"
```

## Browser-Session Hard Adapter Proof

GetCourse and Skillspace now have a shared browser-session snapshot route. CI
uses safe synthetic snapshots; live operator-owned pages can be captured with
the optional Playwright browser extra. The `discover` route finds visible course
entrypoints, follows bounded live pagination, and can register results as local
sources. The `crawl` route starts from a course index and expands visible lesson
links into a course-tree snapshot. The `sync` route runs configured sources and
records checkpoints. Browser fixtures also prove visible progress/status,
discussion comments, and paginated catalog receipts flow into answer packets,
indexes, and graphs. The `smoke` route combines discovery, course
materialization, keyword/semantic/graph build, and optional answer checks into
one operator-facing report for fixture, snapshot, or gated live sources.
For direct live browser crawl, materialize, or smoke commands, pass the
registered `--source-id` (or use an exact registered course URL) so normalized
bundles, answer evidence, and refresh hints remain tied to the source registry.

For live operator-owned browser sessions, create and inspect auth state first:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli auth plan-browser-state getcourse "https://school.example"
PYTHONPATH=src python -m aoa_course_connector.cli auth import-firefox-state getcourse "https://school.example" --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --expect-origin-contains "school.example"
PYTHONPATH=src python -m aoa_course_connector.cli auth capture-browser-state getcourse "https://school.example" --login-url "https://school.example/cms/system/login" --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --expect-origin-contains "school.example"
PYTHONPATH=src python -m aoa_course_connector.cli auth inspect-browser-state "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --expect-origin-contains "school.example"
PYTHONPATH=src python -m aoa_course_connector.cli preflight live --platform getcourse --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --expect-origin school.example
```

Browser preflight checks saved storage state against each registered source
host before marking live sync ready. A state file captured for one school host
does not make another registered host ready.
`auth import-firefox-state` is the no-network shortcut when Firefox already has
a logged-in session for that host; `auth capture-browser-state` is the
fresh-login fallback and also runs the same redacted origin check in its receipt
with `expected_origin_matched`, so a wrong-login or redirect host mismatch is
visible before discovery or sync.
Fixture-discovered GetCourse and Skillspace entries use reserved example hosts
to prove the install route. Live preflight marks those entries as
`fixture_or_example_source` with `operator_live_candidate: false` and will not
emit `sync browser-live` until a real operator-owned course URL is registered.
Before turning an operator snapshot into indexes, inspect it without printing
raw HTML:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli inspect browser-snapshot "$AOA_COURSE_DATA_ROOT/private/getcourse-course.json" --platform getcourse --require-ready
PYTHONPATH=src python -m aoa_course_connector.cli mcp call browser_snapshot_audit '{"snapshot_path":"connector/fixtures/browser/getcourse_starter_snapshot.json","platform":"getcourse"}'
```

The audit reports discovery/materialization readiness, lesson/course links,
visible progress, comments, transcripts, caption sidecar resources, pagination,
repair lanes, and next commands while keeping raw page text out of the report.
Browser smoke reports embed the same compact audit summaries under
`snapshot_audits[]`; live calibration packets aggregate those summaries into
quality fields and repair lanes.

```bash
PYTHONPATH=src python -m aoa_course_connector.cli discover browser-fixture --platform getcourse --run getcourse-browser-discovery-fixture --register
PYTHONPATH=src python -m aoa_course_connector.cli discover browser-fixture --platform skillspace --run skillspace-browser-discovery-fixture --register
PYTHONPATH=src python -m aoa_course_connector.cli sources list
PYTHONPATH=src python -m aoa_course_connector.cli sync browser-fixture --run browser-sync-fixture --build-artifacts
PYTHONPATH=src python -m aoa_course_connector.cli sync status --run browser-sync-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval browser-sync

PYTHONPATH=src python -m aoa_course_connector.cli materialize browser-fixture --platform getcourse --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "GetCourse bootloader rollback evidence" --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "transcript excerpt vendor boot recovery plan" --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "sidecar caption safe mode recovery logs" --run getcourse-browser-fixture

PYTHONPATH=src python -m aoa_course_connector.cli materialize browser-fixture --platform skillspace --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "Skillspace logcat bugreport evidence" --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "caption bugreport timeline" --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "sidecar subtitle ANR tombstone evidence" --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval adapter-authority
PYTHONPATH=src python -m aoa_course_connector.cli eval browser-progress-comments
PYTHONPATH=src python -m aoa_course_connector.cli eval browser-transcripts
PYTHONPATH=src python -m aoa_course_connector.cli smoke browser-fixture --platform getcourse --run getcourse-browser-smoke-fixture

PYTHONPATH=src python -m aoa_course_connector.cli crawl browser-fixture --platform getcourse --run getcourse-browser-crawl-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run getcourse-browser-crawl-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run getcourse-browser-crawl-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "GetCourse bootloader rollback evidence" --run getcourse-browser-crawl-fixture

PYTHONPATH=src python -m aoa_course_connector.cli crawl browser-fixture --platform skillspace --run skillspace-browser-crawl-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run skillspace-browser-crawl-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run skillspace-browser-crawl-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "Skillspace logcat bugreport evidence" --run skillspace-browser-crawl-fixture
```

## Live Calibration Packet

Before expanding connected-source work, run the fixture-safe calibration eval:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli eval live-calibration
PYTHONPATH=src python -m aoa_course_connector.cli calibration connected-run --mode fixture --run connected-fixture-proof
PYTHONPATH=src python -m aoa_course_connector.cli calibration status --run connected-fixture-proof
PYTHONPATH=src python -m aoa_course_connector.cli calibration query --run connected-fixture-proof --kind smoke
```

For operator-connected sources, save `preflight live`, `smoke browser-live`,
and `smoke stepik-live` JSON reports under runtime artifact storage, then build
one redacted plan packet:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli preflight connected-plan \
  --live-scope bounded \
  --query "course-specific question" \
  --link-pattern "*/lessons/*"
```

`preflight connected-plan` is read-only. It inspects the source registry and
auth readiness, then emits exact preflight, sync, smoke, `calibration build`,
and one-command `calibration connected-run --mode live --allow-network`
plans with runtime artifact paths. It is also exposed to agents as MCP
`connected_source_plan`. The default `--live-scope bounded` plans GetCourse,
Skillspace, and Stepik together, while keeping Stepik live sync/smoke commands
under smoke limits. If only some selected platforms are ready, the plan remains
`status: partial`/`ready: false`, but `connected_run_plan` can still be
`ready: true` with `scope: ready_subset`; that command executes only the ready
platform/source ids and keeps the missing platform blockers visible. Use
`--platform` only to narrow a diagnostic run, and use `--source-id` to plan one
registered source without being blocked by other not-yet-authorized sources in
the same registry. MCP accepts the same scope as `source_ids`. Use
`--live-scope full-course --include-step-sources` only for an explicit
operator-selected full-course run. For browser-session sources,
`--link-pattern` carries the same lesson/course URL glob into planned sync,
smoke, and connected-run commands.

For GetCourse and Skillspace, the plan also includes
`browser_auth_plans`: one per browser-session platform. Each plan groups
registered sources by host, reports whether the saved storage-state matches
those hosts, and gives the exact `auth plan-browser-state`,
`auth import-firefox-state`, `auth capture-browser-state`,
`auth inspect-browser-state`, and recheck commands needed before live sync can
start. Per-host `state_file_candidates` include the same Firefox import,
capture, inspect, and source-scoped recheck commands when a platform registry
spans multiple schools or custom domains.

`calibration connected-run` is the executable route over the same contract; a
ready connected plan exposes the exact command as `connected_run_plan`.
`--mode fixture` runs safe GetCourse, Skillspace, and Stepik fixtures end to
end, writes smoke reports, a connected-source plan, a calibration packet, an
intake report, and one
`aoa_course_connected_calibration_run_receipt_v1` under runtime artifact
storage. `--mode live` refuses to touch connected sources unless
`--allow-network` is present; use it only after reviewing the connected plan and
local auth/source readiness. For GetCourse and Skillspace, ready sources use the
same default browser state file checked by preflight,
`${AOA_COURSE_AUTH_ROOT:-.connector-state/auth}/<platform>/account.storage-state.json`,
unless `--state-file` overrides it:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli calibration connected-run \
  --mode live \
  --platform stepik \
  --allow-network \
  --live-scope bounded \
  --source-limit 1 \
  --run connected-stepik-live-calibration
```

The bounded public Stepik path has been field-smoked through this route without
private credentials: a local runtime receipt produced an `ok` connected-source
plan, live sync, live smoke, calibration packet, and intake while keeping raw
API payloads and secret values out of shareable output.
After a run, inspect the same receipt through `calibration status --run <run>`
or MCP `connected_run_status`; both are read-only and do not repeat network
work. Live receipts and status packets include `source_selection`, so agents can
see requested, selected, ready, and blocked source ids before deciding the next
sync or repair. Partial receipts include `repair_lanes`, classifying network
gate, source readiness, source selection, sync, smoke/selector, and packet
intake failures into concrete next commands. Stepik repair and rerun commands
preserve the selected `--include-step-sources`, `--max-step-sources`, and
`--step-source-timeout` budget so an operator-selected enrichment run is not
silently narrowed during follow-up. CLI `readiness` and MCP
`connector_readiness` surface those lane commands at the top-level when a
selected connected-run receipt is partial, while a missing receipt still points
to fixture bootstrap or connected-run commands.
Use `calibration query --run <run>` or MCP `connected_run_query` for the next
retrieval proof: it reads the connected receipt, selects query-ready smoke or
sync entries, and returns `aoa_course_connected_run_query_packet_v1` with
source-backed answer, lesson context, evidence report, freshness, authority,
graph context, blockers, and `network_touched: false`. Pass `--query` for
sync-only entries that do not already have a smoke query.
Use MCP `source_answer` when the agent already knows a configured `source_id`
from `list_sources`: it selects that source's latest query-ready connected run,
prefers sync entries when available, and returns the answer packet, lesson
context, evidence report, and selected run metadata without repeating live
source access. By default it keeps `source_ref` out of the result; pass
`include_source_refs:true` only when the operator wants those refs in context.
Use MCP `sources_answer` when one question should be asked across every selected
query-ready source. It returns one per-source answer/context/evidence packet
plus aggregate quality, blockers, and `network_touched: false`, preserving each
source's provenance instead of merging evidence into an untraceable summary.
Use the CLI equivalent when a shell-side agent should do the same without
handwriting MCP JSON:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli sources list --platform getcourse --no-source-refs --connected-run-limit 2
PYTHONPATH=src python -m aoa_course_connector.cli sources answer "Stepik public API evidence" --platform stepik --mode hybrid
PYTHONPATH=src python -m aoa_course_connector.cli sources answer-matrix --query "Stepik public API evidence" --query "canonical course objects" --platform stepik --mode hybrid
PYTHONPATH=src python -m aoa_course_connector.cli eval source-registry-query --query "Stepik public API evidence" --query "canonical course objects" --platform stepik --kind smoke --mode hybrid
PYTHONPATH=src python -m aoa_course_connector.cli sources answer "course-specific question" --source-id "source:getcourse:..." --mode hybrid
```

Use `sources answer-matrix` or MCP `sources_answer_matrix` when a selected
source set needs a breadth check across several operator questions without
naming run ids by hand. It returns `aoa_course_sources_answer_matrix_v1` with
one source-scoped answer packet per question, aggregate quality, per-query
summaries, and `network_touched: false`.
Use `eval source-registry-query` after fixture or live connected runs when an
agent needs one go/no-go packet proving the selected source registry can answer
several questions through local `sources_answer_matrix` with evidence,
freshness, graph context, and `source_ref` redaction.

Use `calibration query-matrix --run <run> --query ... --query ...` or MCP
`connected_run_query_matrix` when one saved connected run needs to prove several
course questions at once. It reuses the same local query plan without repeating
live crawling, returns one `aoa_course_connected_run_query_packet_v1` per
question plus an `aoa_course_connected_run_query_matrix_v1` aggregate, and
keeps per-question evidence, freshness, graph-context, blockers, and
`network_touched: false`.
Status packets also include `query_plan`, a compact list of queryable
sync/smoke run ids with index, semantic index, graph, answer packet paths,
selected `query_mode`, and ready-to-run CLI `query`, `answer`,
`sources answer`, and `lesson-context` commands plus MCP `source_answer`, `search`, `answer`,
`lesson_context`, and `evidence_report` commands for agents that should stay on
the MCP surface.

```bash
ARTIFACT_ROOT="${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}"
PYTHONPATH=src python -m aoa_course_connector.cli calibration build \
  --run connected-live-calibration \
  --report "$ARTIFACT_ROOT/getcourse-live-smoke.json" \
  --report "$ARTIFACT_ROOT/stepik-live-smoke.json" \
  --preflight-report "$ARTIFACT_ROOT/getcourse-preflight.json"
PYTHONPATH=src python -m aoa_course_connector.cli calibration intake \
  --run connected-live-calibration-intake \
  --packet "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/connected-live-calibration/calibration/live_calibration_packet.json"
```

The packet uses `aoa_course_live_calibration_packet_v1`, checks answer evidence,
timestamps, local raw-path handling, and secret/raw-payload guards, and should
not be committed when it comes from live private sources. `calibration intake`
classifies packet failures into repair lanes and repo-local eval-intake
candidates without promoting them into central proof. See
`docs/LIVE_CALIBRATION.md` for the full route.

## Answer Quality Eval

After the starter, Stepik fixture, and GetCourse browser fixture artifacts have
been built, run:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli eval answer-quality
```

This local suite checks source id, platform, lesson path, snippets, freshness,
and evidence fields rather than only term presence. It is repo-local support
evidence; central proof verdicts and scoring stay with `aoa-evals`.

## Priority Platforms

| Platform | Route |
| --- | --- |
| GetCourse | Working browser-session discovery with paginated fixture/snapshot/live receipts plus Chatium/app-proxy training-card extraction, source sync checkpoints with keyword/semantic/graph artifacts, snapshot progress/comments extraction, and bounded course-tree crawl adapter; live Playwright routes gated by local auth state |
| Skillspace | Working browser-session discovery with paginated fixture/snapshot/live receipts, source sync checkpoints with keyword/semantic/graph artifacts, snapshot progress/comments extraction, and bounded course-tree crawl adapter; live Playwright routes gated by local auth state |
| Stepik | Working clean API reference adapter with fixture/live smoke reports, source-registry sync checkpoints with keyword/semantic/graph artifacts, batched full-course materialization, and optional authenticated step-source enrichment |
| Moodle / Canvas | Future clean LMS adapters |
| Coursera / Teachable / Thinkific / Kajabi | Future platform adapters with OAuth/API/browser-session split |

## Storage

Portable env roots:

```bash
export AOA_COURSE_DATA_ROOT=.connector-state/data
export AOA_COURSE_CACHE_ROOT=.connector-state/cache
export AOA_COURSE_AUTH_ROOT=.connector-state/auth
export AOA_COURSE_ARTIFACT_ROOT=.connector-state/artifacts
```

On this Abyss machine, the recommended external storage example is:

```bash
export AOA_COURSE_INSTANCE_ROOT=/srv/abyss-machine/storage/connectors/aoa-course-connector
```

That path is an example only, not a public default.

## MCP

The MCP server package is named `aoa-course-connector-mcp`, speaks JSON-RPC over
stdio, and exposes the same local artifacts used by the CLI:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli mcp tools
PYTHONPATH=src python -m aoa_course_connector.cli mcp call list_sources '{"include_source_refs":false,"connected_run_limit":2}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call source_answer '{"source_id":"source:stepik:...","query":"Stepik public API evidence"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call sources_answer '{"platforms":["stepik"],"query":"Stepik public API evidence"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call sources_answer_matrix '{"platforms":["stepik"],"queries":["Stepik public API evidence","canonical course objects"]}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call search '{"query":"rollback","run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call semantic_search '{"query":"rollback","run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call hybrid_search '{"query":"rollback","run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call answer '{"query":"bootloader rollback","run":"starter-fixture","mode":"hybrid"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call lesson_context '{"query":"mentor anti-rollback vendor boot","run":"getcourse-browser-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call graph_neighbors '{"node_id":"lesson:starter:unlock-risk","run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call freshness_report '{"run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call evidence_report '{"query":"rollback","run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call refresh_plan '{"query":"rollback","run":"starter-fixture","mode":"hybrid"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call sync_status '{"sync_run":"browser-sync-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call live_preflight '{}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call connected_source_plan '{"live_scope":"bounded"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call semantic_provider_preflight '{"run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call connected_run '{"run":"mcp-connected-fixture","mode":"fixture","platforms":["stepik"],"query":"Stepik public API evidence"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call ingest_status '{"run":"starter-fixture"}'
```

Runtime deployment in the full Abyss stack belongs in `abyss-stack`; this repo
keeps the source server independently installable.
