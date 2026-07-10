# Stepik Adapter

Stepik is the first clean API reference adapter.

## Fixture Route

```bash
aoa-course materialize stepik-fixture --run stepik-fixture
aoa-course build-index --run stepik-fixture
aoa-course build-graph --run stepik-fixture
aoa-course answer "Stepik public API evidence" --run stepik-fixture
```

## Live Public API Route

```bash
aoa-course materialize stepik-live 67 --run stepik-live-smoke --max-sections 1 --max-units-per-section 1 --max-steps-per-lesson 2
aoa-course build-index --run stepik-live-smoke
aoa-course build-graph --run stepik-live-smoke
aoa-course query "Python course" --run stepik-live-smoke
```

The bounded route is the default smoke path. It keeps CI and quick operator
checks small while still proving the API, normalization, index, graph, and query
chain.

## Full-Course API Route

```bash
export STEPIK_API_TOKEN=...
aoa-course materialize stepik-live 67 --run stepik-full-course --full-course --batch-size 20 --include-step-sources --max-step-sources all
aoa-course build-index --run stepik-full-course
aoa-course build-graph --run stepik-full-course
aoa-course answer "course-specific question" --run stepik-full-course
```

`--full-course` disables `--max-sections`, `--max-units-per-section`, and
`--max-steps-per-lesson` smoke limits. Use it only for an explicit
operator-selected course.

`--batch-size` controls Stepik multi-ID reads through `ids[]`. The adapter keeps
the course order stable while reducing one-request-per-object traversal.

`--include-step-sources` asks Stepik for step source payloads and prefers their
source block text during normalization. Some accounts or courses may not expose
step source data; those failures are stored as `step_source_error` on the raw
step object instead of failing the whole course sync.

Step source enrichment is bounded by default: `--max-step-sources 10` with
`--step-source-timeout 5.0`. Use `--max-step-sources N` to widen the enrichment
budget, or `--max-step-sources all` only for an explicit operator-selected run
where a long Stepik traversal is acceptable. Raw Stepik payloads record the
effective limits and `diagnostics.step_source_attempt_count` /
`diagnostics.step_source_skipped_count`. The same enrichment budget can be set
from `readiness`, `preflight connected-plan`, MCP `connector_readiness`, MCP
`connected_source_plan`, `connect profile`, and MCP `connected_run`; these
routes preserve it in the generated `connected_run_plan`.

Stepik normalized steps, assignments, and asset metadata carry
`authority_tier`, `authority_label`, and `source_authority` so official API or
step-source material remains distinguishable in the local index and query
packets. The fixture-safe `eval adapter-authority` route checks that this
adapter-derived metadata survives the retrieval path.

## Source Registry Sync Route

Register a Stepik course source once:

```bash
aoa-course discover stepik 67 --register --title "Stepik course 67"
aoa-course sources list
```

Stepik source refs may be plain course IDs such as `67` or course URLs such as
`https://stepik.org/course/67/syllabus`. Public course sources default to
`public_api`; use `--access-mode api_token` when the connected account is
required.

Safe fixture sync proves the same registry/checkpoint/artifact route without
touching the network:

```bash
aoa-course sync stepik-fixture --run stepik-sync-fixture --source-id "source:stepik:..." --build-artifacts
aoa-course sync status --run stepik-sync-fixture --platform stepik
aoa-course eval stepik-sync
```

Use `--source-id` for agent refresh of one selected course. Omit it only for an
intentional batch sync across all matching registered Stepik sources. Successful
checkpoints include `stable_identity.fingerprint`, which should stay stable
across repeat sync runs for the same Stepik course while fresh artifacts receive
their own child `run_id`.

Stepik raw payloads, receipts, and checkpoints also carry
`aoa_course_ingest_coverage_v1`. It compares referenced and fetched sections,
units, lessons, and steps, so `--full-course` can prove exhaustion of the
ordinary API tree. Teacher-only `step-sources` are reported as a separate
enrichment lane (`complete`, `bounded`, `partial`, `unavailable`, or
`not_requested`) and do not hide whether the core course tree is complete.

## Account Discovery Route

When the connected account can expose enrolled courses, discover those course
refs and register them as local Stepik sources:

```bash
export STEPIK_API_TOKEN=...
aoa-course preflight live --platform stepik --stepik-token-env STEPIK_API_TOKEN
aoa-course discover stepik-account \
  --run stepik-account-discovery-live \
  --token-env STEPIK_API_TOKEN \
  --register \
  --max-pages 5
```

The live route reads the current account through Stepik API auth, discovers
course IDs from enrollment and course-grade data, and writes only local
source-registry entries. It does not store or print the token value.

`preflight live --platform stepik` checks token presence, local Stepik browser
state, and registered Stepik sources without touching the network. It reports
`token_present` and storage-state readiness but never logs token or cookie
values, and it can be used with `--require-ready` in operator scripts.
Registered `public_api` sources can be sync-ready without `STEPIK_API_TOKEN`;
registered `api_token` or `oauth` sources still require the token before live
sync is ready. Browser-session sources require a matching `stepik.org` state
file. If Firefox already has a logged-in Stepik session, create that state
without a fresh login:

```bash
aoa-course auth import-firefox-state stepik account \
  --state-file "$AOA_COURSE_AUTH_ROOT/stepik/account.storage-state.json" \
  --expect-origin-contains stepik.org
```

Account discovery is treated as required only when no Stepik sources are
already registered.

After `sync stepik-live --build-artifacts`, source-registry queries can use the
sync checkpoints directly:

```bash
aoa-course sources answer "course-specific question" --platform stepik --mode hybrid
```

This keeps the agent-facing query route local and read-only after sync; it does
not require the caller to remember the child run id.

For a Stepik-focused agent plan, narrow the read-only connected plan:

```bash
aoa-course preflight connected-plan \
  --platform stepik \
  --stepik-token-env STEPIK_API_TOKEN \
  --live-scope bounded \
  --query "course-specific question"
```

The plan emits `sync stepik-live`, per-source `smoke stepik-live`, and
`calibration build` commands when registered Stepik sources are ready. It keeps
token values out of output and still marks `public_api` sources ready without a
token. The default `bounded` scope keeps live sync/smoke under smoke limits;
use `--live-scope full-course --include-step-sources` only for an explicit
operator-selected full-course/source-enrichment run.

Account discovery filters inactive or deleted enrollments before registering
course sources, so stale account records do not become live sync targets.

Safe fixture discovery proves the same registration route without network
access:

```bash
aoa-course discover stepik-account --from-fixture --run stepik-account-discovery-fixture --register
aoa-course sources list
```

Live source-registry sync uses the registered course refs:

```bash
aoa-course sync stepik-live --run stepik-live-sync --source-id "source:stepik:..." --full-course --batch-size 20 --include-step-sources --max-step-sources all --build-artifacts
aoa-course mcp call sync_status '{"sync_run":"stepik-live-sync","platform":"stepik"}'
```

## Smoke Reports

Stepik smoke reports combine source registration, sync, optional
keyword/semantic/graph builds, answer evidence, and privacy-safe local path
reporting.

```bash
aoa-course smoke stepik-fixture 67 --run stepik-smoke-fixture --query "Stepik public API evidence"
aoa-course smoke stepik-live 67 --run stepik-live-public-smoke --query "Python course"
```

`smoke stepik-fixture` is safe for CI and fresh-agent validation because it does
not touch the network. `smoke stepik-live` is an operator action and returns an
`aoa_course_stepik_smoke_report_v1` payload with `network_touched: true`.

Use `eval live-calibration` for fixture-safe packet proof, then use
`calibration build` with saved `smoke stepik-live` and `preflight live` JSON
reports when calibrating connected Stepik courses. See
`docs/LIVE_CALIBRATION.md`.

Live materialization stores raw API responses and normalized bundles under
`AOA_COURSE_DATA_ROOT`; generated indexes and graphs go under
`AOA_COURSE_ARTIFACT_ROOT`.

Set `STEPIK_API_TOKEN` when accessing data that requires an authenticated Stepik
account. Public course reads can work without it.

## Mapped API Shape

The adapter follows the Stepik API shape:

`course -> sections -> units -> lessons -> steps`

Object fanout uses `ids[]` batching. Collection helpers support `meta.has_next`
pagination for future routes that need account- or catalog-level Stepik
discovery.

Only bounded live slices should be used for smoke checks. Full-course ingestion
should be an explicit operator action.
