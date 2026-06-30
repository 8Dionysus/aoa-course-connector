# Browser Session Adapters

GetCourse and Skillspace are hard browser-session adapters.

The connector supports five browser-session routes:

1. `browser-fixture`: safe synthetic snapshots used by CI.
2. `browser-snapshot`: operator-provided JSON snapshot captured outside Git.
3. `browser-live`: optional Playwright capture using a connected user's local
   browser storage state.
4. `crawl`: bounded course-tree traversal from an index page to visible lesson
   pages.
5. `discover`: account/catalog discovery that finds visible course entrypoints
   and can register them as local sources.

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

## Snapshot Route

```bash
aoa-course materialize browser-snapshot /path/to/snapshot.json --platform getcourse --run my-getcourse-run
aoa-course discover browser-snapshot /path/to/catalog-snapshot.json --platform getcourse --run my-getcourse-discovery --register --max-sources 50
aoa-course crawl browser-snapshot /path/to/snapshot.json --platform getcourse --run my-getcourse-crawl --max-lessons 50
```

Snapshot files use `aoa_course_browser_snapshot_v1` and should be stored outside
Git. They contain page URLs, titles, captured timestamps, and HTML from pages the
connected account can legitimately view.

## Live Route

Install the optional browser extra:

```bash
python -m pip install -e ".[browser]"
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
  --max-sources 50
```

`--max-lessons` bounds the live traversal. `--link-pattern` can narrow discovery
when a platform or school theme emits noisy navigation links.
`--max-sources` bounds account-level source discovery.
