# GetCourse Notes

GetCourse is a priority hard adapter.

Expected route:

- browser-session auth state under `AOA_COURSE_AUTH_ROOT`;
- discover visible trainings/courses;
- discover lesson groups and lessons;
- extract lesson title, text blocks, attachments metadata, available captions or
  transcripts, comments when visible, and source URLs;
- record media as asset metadata unless permitted resolution is explicitly
  enabled.

The connector should not depend on media download to deliver useful knowledge.

## Current Working Route

`aoa-course-connector` supports GetCourse through the shared browser-session
discovery, snapshot, and course-tree crawl adapters. Fixture proofs cover
paginated catalog receipts, visible course progress, and visible discussion
comments:

```bash
aoa-course discover browser-fixture --platform getcourse --run getcourse-browser-discovery-fixture --register --max-sources 50
aoa-course sources list
aoa-course sync browser-fixture --run browser-sync-fixture --platform getcourse --build-artifacts
aoa-course sync status --run browser-sync-fixture --platform getcourse

aoa-course materialize browser-fixture --platform getcourse --run getcourse-browser-fixture
aoa-course build-index --run getcourse-browser-fixture
aoa-course build-graph --run getcourse-browser-fixture
aoa-course answer "GetCourse bootloader rollback evidence" --run getcourse-browser-fixture
aoa-course answer "mentor anti-rollback vendor boot" --run getcourse-browser-fixture
aoa-course eval browser-progress-comments

aoa-course crawl browser-fixture --platform getcourse --run getcourse-browser-crawl-fixture --max-lessons 20
aoa-course build-index --run getcourse-browser-crawl-fixture
aoa-course build-graph --run getcourse-browser-crawl-fixture
aoa-course answer "GetCourse bootloader rollback evidence" --run getcourse-browser-crawl-fixture
```

For live operator-owned pages, use `discover browser-live` or
`crawl browser-live` with a local Playwright storage-state file under
`AOA_COURSE_AUTH_ROOT`. Start discovery from a visible stream/catalog page, then
crawl the selected course entrypoint:

```bash
aoa-course discover browser-live "https://school.example/teach/control/stream" \
  --platform getcourse \
  --run getcourse-live-discovery \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --register \
  --max-sources 50 \
  --max-pages 5

aoa-course crawl browser-live "https://school.example/teach/control/stream" \
  --platform getcourse \
  --run getcourse-live-crawl \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --max-lessons 50

aoa-course sync browser-live \
  --run getcourse-live-sync \
  --platform getcourse \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --max-lessons 50 \
  --build-artifacts
```
