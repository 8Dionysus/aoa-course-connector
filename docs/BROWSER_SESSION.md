# Browser Session Adapters

GetCourse and Skillspace are hard browser-session adapters.

The connector supports seven browser-session routes:

1. `browser-fixture`: safe synthetic snapshots used by CI.
2. `browser-snapshot`: operator-provided JSON snapshot captured outside Git.
3. `browser-live`: optional Playwright capture using a connected user's local
   browser storage state.
4. `crawl`: bounded course-tree traversal from an index page to visible lesson
   pages.
5. `discover`: account/catalog discovery that finds visible course entrypoints
   and can register them as local sources.
6. `sync`: source-registry driven refresh that writes checkpoints and optional
   keyword/semantic/graph artifacts.
7. `smoke`: gated operator check that combines discovery, course materialization,
   keyword/semantic/graph build, and optional answer verification into one
   report.

## Fixture Proof

```bash
aoa-course materialize browser-fixture --platform getcourse --run getcourse-browser-fixture
aoa-course build-index --run getcourse-browser-fixture
aoa-course build-graph --run getcourse-browser-fixture
aoa-course answer "GetCourse bootloader rollback evidence" --run getcourse-browser-fixture

aoa-course materialize browser-fixture --platform skillspace --run skillspace-browser-fixture
aoa-course build-index --run skillspace-browser-fixture
aoa-course build-graph --run skillspace-browser-fixture
aoa-course answer "Skillspace logcat bugreport evidence" --run skillspace-browser-fixture
aoa-course eval browser-hard-adapters
```

## Account Discovery Proof

Use `discover browser-fixture` to prove the source-registration route without
private account data:

```bash
aoa-course discover browser-fixture --platform getcourse --run getcourse-browser-discovery-fixture --register --max-sources 50
aoa-course discover browser-fixture --platform skillspace --run skillspace-browser-discovery-fixture --register --max-sources 50
aoa-course sources list
aoa-course eval browser-discovery
```

`--register` writes discovered course entrypoints into the local source registry
under `AOA_COURSE_DATA_ROOT`. Without `--register`, discovery is read-only and
emits a receipt only.

Fixture-discovered browser sources use reserved example hosts. They prove the
source-registry, sync, index, graph, and query route, but they are not operator
live sources. Before live sync, register a real operator-owned course URL with
`discover browser-live --register` or `sources add`; live preflight marks
example-host entries as `fixture_or_example_source` and
`operator_live_candidate: false`.

Fixture, snapshot, and live discovery receipts include `page_count` plus
pagination metadata such as `pagination.next_link_count`. This proves paginated
catalog captures can be represented without committing private account pages.
Live discovery follows visible next-page links up to `--max-pages` and stops on
seen URLs to avoid loops.

## Source Sync Proof

After discovery has registered sources, run a source-driven sync:

```bash
aoa-course sync browser-fixture --run browser-sync-fixture --build-artifacts
aoa-course sync status --run browser-sync-fixture
aoa-course eval browser-sync
aoa-course mcp call sync_status '{"sync_run":"browser-sync-fixture"}'
```

The sync route creates child runs for enabled `browser_session` sources, writes
`SyncCheckpoint` records under `AOA_COURSE_DATA_ROOT`, and can build keyword
indexes and graphs for each child run with `--build-artifacts`.

## Course-Tree Crawl Proof

Use `crawl browser-fixture` when testing the adapter as a course tree rather
than as a preassembled set of pages:

```bash
aoa-course crawl browser-fixture --platform getcourse --run getcourse-browser-crawl-fixture --max-lessons 20
aoa-course build-index --run getcourse-browser-crawl-fixture
aoa-course build-graph --run getcourse-browser-crawl-fixture
aoa-course answer "GetCourse bootloader rollback evidence" --run getcourse-browser-crawl-fixture

aoa-course crawl browser-fixture --platform skillspace --run skillspace-browser-crawl-fixture --max-lessons 20
aoa-course build-index --run skillspace-browser-crawl-fixture
aoa-course build-graph --run skillspace-browser-crawl-fixture
aoa-course answer "Skillspace logcat bugreport evidence" --run skillspace-browser-crawl-fixture
aoa-course eval browser-crawl
```

The crawler extracts lesson links from the course index, keeps module hints from
link metadata, matches already captured lesson pages by URL, and creates
`discovered_not_fetched` placeholders only when a linked lesson page is absent
from the snapshot. Those placeholders are indexed as discovery evidence, not as
full lesson content: their step authority is `discovered_link`, their source
authority is `browser_course_index_link`, and their graph nodes retain the
`discovered_not_fetched` or `fetch_error` freshness state so agents can ask for
source refresh before treating them as complete course knowledge.

## Progress, Comments, And Transcripts Proof

Browser snapshots extract visible progress/status blocks and visible discussion
comments when the page exposes them in accessible HTML. They also extract
visible transcript/caption blocks when the page exposes them as HTML text or
caption/transcript-marked blocks. They also resolve caption sidecar resources
when a page exposes `<track>` metadata and the raw snapshot carries matching
`resources[]` text, such as WebVTT or SRT payloads captured outside Git.
Extraction is data/aria-first and also handles compact unannotated blocks with
progress, comment, reply, discussion, transcript, caption, or subtitle class/id
hints. The normalized bundle keeps progress evidence at the course level and
discussion/transcript evidence under the lesson.
When comment blocks expose author-role metadata such as
`data-aoa-author-role`, the adapter preserves it as `role`, `authority_tier`,
`authority_label`, and `source_authority` so ranking can distinguish mentor,
instructor, learner, and generic discussion notes.
Transcript/caption text is normalized as canonical `Transcript` objects with
`authority_tier: transcript`. Visible blocks use
`source_authority: browser_visible_transcript`; sidecar captions use
`source_authority: browser_caption_sidecar`. The keyword index includes these
surfaces as searchable knowledge items, and the graph includes
`course_has_progress`, `lesson_has_transcript`, `lesson_has_comment_thread`, and
`thread_has_comment` edges.

```bash
aoa-course materialize browser-fixture --platform getcourse --run getcourse-browser-fixture
aoa-course build-index --run getcourse-browser-fixture
aoa-course build-graph --run getcourse-browser-fixture
aoa-course answer "mentor anti-rollback vendor boot" --run getcourse-browser-fixture
aoa-course answer "transcript excerpt vendor boot recovery plan" --run getcourse-browser-fixture
aoa-course answer "sidecar caption safe mode recovery logs" --run getcourse-browser-fixture

aoa-course materialize browser-fixture --platform skillspace --run skillspace-browser-fixture
aoa-course build-index --run skillspace-browser-fixture
aoa-course build-graph --run skillspace-browser-fixture
aoa-course answer "timestamp window reproduction step" --run skillspace-browser-fixture
aoa-course answer "caption bugreport timeline" --run skillspace-browser-fixture
aoa-course answer "sidecar subtitle ANR tombstone evidence" --run skillspace-browser-fixture

aoa-course eval adapter-authority
aoa-course eval browser-progress-comments
aoa-course eval browser-transcripts
```

## Smoke Route

Use `smoke browser-fixture` to prove the full operator-facing route without
private data:

```bash
aoa-course smoke browser-fixture --platform getcourse --run getcourse-browser-smoke-fixture
```

Use `smoke browser-snapshot` when an operator has exported safe local snapshots
outside Git:

```bash
aoa-course smoke browser-snapshot \
  --platform getcourse \
  --run getcourse-snapshot-smoke \
  --catalog-snapshot "$AOA_COURSE_DATA_ROOT/private/getcourse-catalog.json" \
  --course-snapshot "$AOA_COURSE_DATA_ROOT/private/getcourse-course.json" \
  --query "your course-specific question"
```

Use `smoke browser-live` only with a connected account and a local Playwright
storage-state file:

```bash
aoa-course smoke browser-live \
  --platform getcourse \
  --run getcourse-live-smoke \
  --catalog-url "https://school.example/teach/control/stream" \
  --course-url "https://school.example/teach/control/stream/view/id/201" \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --max-pages 5 \
  --max-lessons 20 \
  --query "your course-specific question"
```

Smoke reports include counts, including `transcript_count`, local artifact
paths, answer/evidence health, and privacy reminders. They do not print raw
private HTML or caption text; raw snapshots remain runtime state under
`AOA_COURSE_DATA_ROOT`. Browser smoke reports also embed compact
`snapshot_audits[]` summaries for the raw discovery/course snapshots, so live
calibration can route selector, caption, comment, transcript, and pagination
failures without reopening private HTML.

Use `eval live-calibration` for fixture-safe packet proof, then use
`calibration build` with saved `smoke browser-live` and `preflight live` JSON
reports when calibrating connected GetCourse or Skillspace accounts. See
`docs/LIVE_CALIBRATION.md`.

## Snapshot Route

```bash
aoa-course inspect browser-snapshot /path/to/snapshot.json --platform getcourse --require-ready
aoa-course materialize browser-snapshot /path/to/snapshot.json --platform getcourse --run my-getcourse-run
aoa-course discover browser-snapshot /path/to/catalog-snapshot.json --platform getcourse --run my-getcourse-discovery --register --max-sources 50
aoa-course crawl browser-snapshot /path/to/snapshot.json --platform getcourse --run my-getcourse-crawl --max-lessons 50
```

Snapshot files use `aoa_course_browser_snapshot_v1` and should be stored outside
Git. They contain page URLs, titles, captured timestamps, and HTML from pages the
connected account can legitimately view. Operator snapshots may include multiple
catalog pages when the account has paginated course lists; the connector records
pagination evidence in the discovery receipt.

`inspect browser-snapshot` emits `aoa_course_browser_snapshot_audit_v1` before
materialization. It is read-only, does not touch the network, and does not echo
raw HTML or caption text. Use it to check whether the snapshot is ready for
catalog discovery, course crawl, materialization, or smoke; it also reports
counts for course links, lesson links, visible progress, comments, transcripts,
caption sidecars, caption `resources[]` parse errors, pagination, and repair
lanes.

When a snapshot includes caption sidecars, store them as `resources[]` entries
with `url`, optional `kind`, optional `language`, optional `content_type`, and
`text`. The URL should match a visible `<track src="...">` URL in the lesson
HTML. The connector parses WebVTT/SRT cue text into canonical transcripts while
preserving the source URL as evidence.

## Live Route

Install the optional browser extra:

```bash
python -m pip install -e ".[browser]"
```

Create and verify a local Playwright storage-state file:

```bash
aoa-course auth capture-browser-state getcourse "https://school.example" \
  --login-url "https://school.example/cms/system/login" \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --expect-origin-contains "school.example"

aoa-course auth inspect-browser-state "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --expect-origin-contains "school.example"

aoa-course preflight live \
  --platform getcourse \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --expect-origin school.example
```

The capture receipt is safe to inspect: it reports counts and
`expected_origin_matched` without printing cookies, localStorage values, or
tokens. Treat a `warning` receipt as a blocked live route until the saved state
matches the operator-owned course host.

When an agent needs to decide the next live action for GetCourse browser
sources, narrow the read-only connected plan:

```bash
aoa-course preflight connected-plan \
  --platform getcourse \
  --live-scope bounded \
  --query "your course-specific question" \
  --write-runbook "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/getcourse-connected-runbook.md"
```

The plan reports which source hosts match the saved storage state and emits the
exact `sync browser-live`, `smoke browser-live`, `calibration build`, and
`connected_run_plan` commands only for ready sources. `--write-runbook`
turns the redacted JSON plan into a Markdown checklist under runtime artifact
storage; do not commit that file because ready-source smoke commands can
contain operator course URLs.
Use `--source-id "source:getcourse:..."` when the registry contains several
browser-session courses and the current auth state is meant for one selected
source. The same scoped selection is available to MCP as `source_ids`, and the
ready plan should repeat it under `connected_run_plan.source_ids`.
When the same ready source is executed through
`calibration connected-run --mode live --allow-network`, the runner uses the default
`${AOA_COURSE_AUTH_ROOT:-.connector-state/auth}/<platform>/account.storage-state.json`
path unless `--state-file` is supplied, and the receipt records
`source_selection` plus per-stage source ids. If `--link-pattern` was passed to
the plan, the connected-run plan preserves it for live sync and smoke.

Its `browser_auth_plans` section is the operator/agent checklist for
blocked browser sources. It groups registered sources by host, shows the
storage-state file to create or inspect, lists blocked hosts, and gives
portable `auth plan-browser-state`, `auth capture-browser-state`,
`auth inspect-browser-state`, and `preflight connected-plan` recheck commands.
When one GetCourse or Skillspace plan contains several schools or custom
domains, `browser_auth_plans[].state_file_candidates` gives one per-host
state-file path with capture, inspect, and source-scoped recheck commands, so
an agent does not accidentally reuse an auth state from the wrong school.

Then capture a visible page:

```bash
aoa-course materialize browser-live "https://school.example/teach/control/lesson/view/id/101" \
  --platform getcourse \
  --run getcourse-live-smoke \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json"
```

The `state-file` is a local Playwright storage-state file produced after the
operator logs in. Do not commit it.

Live materialization and live crawls attempt to fetch text-like caption
resources referenced by visible `<track>` tags through the same browser context.
Only small caption-like resources are stored, errors are recorded as metadata,
and private caption text stays in the local raw snapshot under
`AOA_COURSE_DATA_ROOT`.

To start from a course index and visit visible lesson pages in the same
authorized session, use `crawl browser-live`:

```bash
aoa-course crawl browser-live "https://school.example/teach/control/stream" \
  --platform getcourse \
  --run getcourse-live-crawl \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --max-lessons 50
```

To start from an account catalog page and register visible course entrypoints,
use `discover browser-live`:

```bash
aoa-course discover browser-live "https://school.example/teach/control/stream" \
  --platform getcourse \
  --run getcourse-live-discovery \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --register \
  --max-sources 50 \
  --max-pages 5
```

`--max-lessons` bounds the live traversal. `--link-pattern` can narrow discovery
when a platform or school theme emits noisy navigation links.
`--max-sources` bounds account-level source discovery. `--max-pages` bounds live
catalog pagination while preserving next-link evidence in the discovery receipt.

To sync all registered live browser sources:

```bash
aoa-course sync browser-live \
  --run browser-live-sync \
  --source-id "source:getcourse:..." \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --max-lessons 50 \
  --build-artifacts
```

Use `--source-id` when refreshing one selected source from an answer or
`refresh_plan`. Use `--platform` more than once only for intentional batch
refresh. Use `sync status` to inspect checkpoints before choosing which child
run to query.

`preflight live` is the safe plan check before these live routes. It reads
the local source registry and redacted browser storage-state status, reports
whether discovery/sync is ready, and suggests the next command without printing
private HTML, cookie values, or tokens.

For registered browser sources, preflight checks the saved storage state against
each source host before marking `browser_live_sync` ready. A state file captured
for `a.example` does not make a registered `b.example` source ready; capture or
select auth state for the matching host first. When several registered sources
share one host, `browser_auth_plans[].host_readiness` collapses their
blockers into one host-level item instead of repeating the same missing-state
message per source.

Catalog discovery also rejects pagination links before applying a custom
`link_pattern`, so broad patterns cannot accidentally register "next page"
links as course sources.
