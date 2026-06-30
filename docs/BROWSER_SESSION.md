# Browser Session Adapters

GetCourse and Skillspace are hard browser-session adapters.

The connector supports three browser-session routes:

1. `browser-fixture`: safe synthetic snapshots used by CI.
2. `browser-snapshot`: operator-provided JSON snapshot captured outside Git.
3. `browser-live`: optional Playwright capture using a connected user's local
   browser storage state.

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

## Snapshot Route

```bash
aoa-course materialize browser-snapshot /path/to/snapshot.json --platform getcourse --run my-getcourse-run
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

Live captures currently materialize one visible page at a time. Full course-tree
navigation is the next expansion layer.
