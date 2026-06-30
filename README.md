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
PYTHONPATH=src python -m aoa_course_connector.cli materialize fixture --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "bootloader unlock rollback"
PYTHONPATH=src python -m aoa_course_connector.cli answer "bootloader rollback" --mode hybrid
```

The starter path creates:

- normalized course objects from a safe fixture;
- a local keyword index;
- a deterministic local semantic/vector index (`local_hashing_v1`);
- an optional HTTP JSON semantic provider (`http_json_v1`) for
  operator-configured embedding endpoints;
- a course graph;
- an answer packet with source-backed evidence.
- answer packets with source-backed evidence.

To build the same semantic index contract through an external embedding
endpoint, keep the token in the environment and pass only the env var name:

```bash
export AOA_COURSE_EMBEDDING_TOKEN=...
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run starter-fixture --provider http_json_v1 --embedding-endpoint "http://127.0.0.1:8000/embeddings" --embedding-model "local-course-embedding" --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN
PYTHONPATH=src python -m aoa_course_connector.cli query "bootloader rollback" --run starter-fixture --mode semantic
```

The semantic index artifact records provider metadata and the token environment
variable name, but not the token value. MCP `semantic_search` reads the same
provider contract as the CLI query route.

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

For live source-registry sync, register the course once and run:

```bash
export STEPIK_API_TOKEN=...
PYTHONPATH=src python -m aoa_course_connector.cli preflight live --platform stepik --stepik-token-env STEPIK_API_TOKEN
PYTHONPATH=src python -m aoa_course_connector.cli discover stepik-account --run stepik-account-discovery-live --token-env STEPIK_API_TOKEN --register --max-pages 5
PYTHONPATH=src python -m aoa_course_connector.cli sync stepik-live --run stepik-live-sync --source-id "source:stepik:..." --full-course --batch-size 20 --include-step-sources --build-artifacts
```

`preflight live --platform stepik` treats registered `public_api` sources as
sync-ready without `STEPIK_API_TOKEN`; token-gated `api_token` and `oauth`
sources still require the token. Account discovery ignores inactive or deleted
enrollments before registering sources.

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
materialization, index/graph build, and optional answer checks into one
operator-facing report for fixture, snapshot, or gated live sources.

For live operator-owned browser sessions, create and inspect auth state first:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli auth plan-browser-state getcourse "https://school.example"
PYTHONPATH=src python -m aoa_course_connector.cli auth capture-browser-state getcourse "https://school.example" --login-url "https://school.example/cms/system/login" --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json"
PYTHONPATH=src python -m aoa_course_connector.cli auth inspect-browser-state "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --expect-origin-contains "school.example"
PYTHONPATH=src python -m aoa_course_connector.cli preflight live --platform getcourse --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --expect-origin school.example
```

Browser preflight checks saved storage state against each registered source
host before marking live sync ready. A state file captured for one school host
does not make another registered host ready.

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
```

For operator-connected sources, save `preflight live`, `smoke browser-live`,
and `smoke stepik-live` JSON reports under runtime artifact storage, then build
one redacted handoff packet:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli preflight connected-plan \
  --platform getcourse \
  --platform stepik \
  --live-scope bounded \
  --query "course-specific question" \
  --write-runbook "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connected-source-runbook.md"
```

`preflight connected-plan` is read-only. It inspects the source registry and
auth readiness, then emits exact preflight, sync, smoke, and
`calibration build` commands with runtime artifact paths. It is also exposed to
agents as MCP `connected_source_plan`. The default `--live-scope bounded`
keeps Stepik live sync/smoke commands under smoke limits; use
`--live-scope full-course --include-step-sources` only for an explicit
operator-selected full-course run. `--write-runbook` writes the same redacted
handoff as Markdown under runtime artifact storage so an operator or agent can
execute the setup, sync, smoke, and calibration steps without rereading raw
JSON.

For GetCourse and Skillspace, the plan also includes
`browser_auth_handoffs`: one per browser-session platform. Each handoff groups
registered sources by host, reports whether the saved storage-state matches
those hosts, and gives the exact `auth plan-browser-state`,
`auth capture-browser-state`, `auth inspect-browser-state`, and recheck
commands needed before live sync can start.

`calibration connected-run` is the executable route over the same contract.
`--mode fixture` runs safe GetCourse, Skillspace, and Stepik fixtures end to
end, writes smoke reports, a connected-source plan, a runbook, a calibration
packet, an intake report, and one
`aoa_course_connected_calibration_run_receipt_v1` under runtime artifact
storage. `--mode live` refuses to touch connected sources unless
`--allow-network` is present; use it only after reviewing the connected plan and
local auth/source readiness:

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
work.

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
| GetCourse | Working browser-session discovery with paginated fixture/snapshot/live receipts, source sync checkpoints, snapshot progress/comments extraction, and bounded course-tree crawl adapter; live Playwright routes gated by local auth state |
| Skillspace | Working browser-session discovery with paginated fixture/snapshot/live receipts, source sync checkpoints, snapshot progress/comments extraction, and bounded course-tree crawl adapter; live Playwright routes gated by local auth state |
| Stepik | Working clean API reference adapter with fixture/live smoke reports, source-registry sync checkpoints, batched full-course materialization, and optional authenticated step-source enrichment |
| Moodle / Canvas | Future clean LMS adapters |
| Teachable / Thinkific / Kajabi | Future platform adapters with API/browser-session split |

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
PYTHONPATH=src python -m aoa_course_connector.cli mcp call search '{"query":"rollback","run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call semantic_search '{"query":"rollback","run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call hybrid_search '{"query":"rollback","run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call lesson_context '{"query":"mentor anti-rollback vendor boot","run":"getcourse-browser-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call graph_neighbors '{"node_id":"lesson:starter:unlock-risk","run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call freshness_report '{"run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call evidence_report '{"query":"rollback","run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call refresh_plan '{"query":"rollback","run":"starter-fixture","mode":"hybrid"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call sync_status '{"sync_run":"browser-sync-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call live_preflight '{"platforms":["getcourse","stepik"]}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call connected_source_plan '{"platforms":["getcourse","stepik"]}'
```

Runtime deployment in the full Abyss stack belongs in `abyss-stack`; this repo
keeps the source server independently installable.
