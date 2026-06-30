# Browser Session Adapters

GetCourse and Skillspace are hard browser-session adapters.

The connector supports six browser-session routes:

1. `browser-fixture`: safe synthetic snapshots used by CI.
2. `browser-snapshot`: operator-provided JSON snapshot captured outside Git.
3. `browser-live`: optional Playwright capture using a connected user's local
   browser storage state.
4. `crawl`: bounded course-tree traversal from an index page to visible lesson
   pages.
5. `discover`: account/catalog discovery that finds visible course entrypoints
   and can register them as local sources.
6. `sync`: source-registry driven refresh that writes checkpoints and optional
   index/graph artifacts.
7. `smoke`: gated operator check that combines discovery, course materialization,
   index/graph build, and optional answer verification into one report.

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
from the snapshot.

## Progress And Comments Proof

Browser snapshots extract visible progress/status blocks and visible discussion
comments when the page exposes them in accessible HTML. Extraction is
data/aria-first and also handles compact unannotated blocks with progress,
comment, reply, or discussion class/id hints. The normalized bundle keeps
progress evidence at the course level and discussion evidence under the lesson.
When comment blocks expose author-role metadata such as
`data-aoa-author-role`, the adapter preserves it as `role`, `authority_tier`,
`authority_label`, and `source_authority` so ranking can distinguish mentor,
instructor, learner, and generic discussion notes.
The keyword index includes both as searchable knowledge items, and the graph
includes `course_has_progress`, `lesson_has_comment_thread`, and
`thread_has_comment` edges.

```bash
aoa-course materialize browser-fixture --platform getcourse --run getcourse-browser-fixture
aoa-course build-index --run getcourse-browser-fixture
aoa-course build-graph --run getcourse-browser-fixture
aoa-course answer "mentor anti-rollback vendor boot" --run getcourse-browser-fixture

aoa-course materialize browser-fixture --platform skillspace --run skillspace-browser-fixture
aoa-course build-index --run skillspace-browser-fixture
aoa-course build-graph --run skillspace-browser-fixture
aoa-course answer "timestamp window reproduction step" --run skillspace-browser-fixture

aoa-course eval adapter-authority
aoa-course eval browser-progress-comments
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

Smoke reports include counts, local artifact paths, answer/evidence health, and
privacy reminders. They do not print raw private HTML; raw snapshots remain
runtime state under `AOA_COURSE_DATA_ROOT`.

## Snapshot Route

```bash
aoa-course materialize browser-snapshot /path/to/snapshot.json --platform getcourse --run my-getcourse-run
aoa-course discover browser-snapshot /path/to/catalog-snapshot.json --platform getcourse --run my-getcourse-discovery --register --max-sources 50
aoa-course crawl browser-snapshot /path/to/snapshot.json --platform getcourse --run my-getcourse-crawl --max-lessons 50
```

Snapshot files use `aoa_course_browser_snapshot_v1` and should be stored outside
Git. They contain page URLs, titles, captured timestamps, and HTML from pages the
connected account can legitimately view. Operator snapshots may include multiple
catalog pages when the account has paginated course lists; the connector records
pagination evidence in the discovery receipt.

## Live Route

Install the optional browser extra:

```bash
python -m pip install -e ".[browser]"
```

Create and verify a local Playwright storage-state file:

```bash
aoa-course auth capture-browser-state getcourse "https://school.example" \
  --login-url "https://school.example/cms/system/login" \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json"

aoa-course auth inspect-browser-state "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --expect-origin-contains "school.example"

aoa-course preflight live \
  --platform getcourse \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --expect-origin school.example
```

Then capture a visible page:

```bash
aoa-course materialize browser-live "https://school.example/teach/control/lesson/view/id/101" \
  --platform getcourse \
  --run getcourse-live-smoke \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json"
```

The `state-file` is a local Playwright storage-state file produced after the
operator logs in. Do not commit it.

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
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --max-lessons 50 \
  --build-artifacts
```

Use `--platform` more than once to narrow the source set. Use `sync status` to
inspect checkpoints before choosing which child run to query.

`preflight live` is the safe handoff check before these live routes. It reads
the local source registry and redacted browser storage-state status, reports
whether discovery/sync is ready, and suggests the next command without printing
private HTML, cookie values, or tokens.

For registered browser sources, preflight checks the saved storage state against
each source host before marking `browser_live_sync` ready. A state file captured
for `a.example` does not make a registered `b.example` source ready; capture or
select auth state for the matching host first.

Catalog discovery also rejects pagination links before applying a custom
`link_pattern`, so broad patterns cannot accidentally register "next page"
links as course sources.
