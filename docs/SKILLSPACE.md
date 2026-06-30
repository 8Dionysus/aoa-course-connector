# Skillspace Notes

Skillspace is a priority hard adapter.

Expected route:

- browser-session auth state under `AOA_COURSE_AUTH_ROOT`;
- discover available courses from the connected account;
- extract module/lesson hierarchy and lesson page content;
- preserve assignment, progress, comment, and asset metadata when visible;
- store evidence for every normalized object.

Skillspace public API coverage appears limited for full course-content export, so
the first live route should be browser-session discovery.

## Current Working Route

`aoa-course-connector` supports Skillspace through the shared browser-session
discovery, snapshot, and course-tree crawl adapters. Fixture proofs cover
paginated catalog receipts, visible course progress, and visible discussion
comments:

```bash
aoa-course discover browser-fixture --platform skillspace --run skillspace-browser-discovery-fixture --register --max-sources 50
aoa-course sources list
aoa-course sync browser-fixture --run browser-sync-fixture --platform skillspace --build-artifacts
aoa-course sync status --run browser-sync-fixture --platform skillspace

aoa-course materialize browser-fixture --platform skillspace --run skillspace-browser-fixture
aoa-course build-index --run skillspace-browser-fixture
aoa-course build-graph --run skillspace-browser-fixture
aoa-course answer "Skillspace logcat bugreport evidence" --run skillspace-browser-fixture
aoa-course answer "timestamp window reproduction step" --run skillspace-browser-fixture
aoa-course eval browser-progress-comments

aoa-course crawl browser-fixture --platform skillspace --run skillspace-browser-crawl-fixture --max-lessons 20
aoa-course build-index --run skillspace-browser-crawl-fixture
aoa-course build-graph --run skillspace-browser-crawl-fixture
aoa-course answer "Skillspace logcat bugreport evidence" --run skillspace-browser-crawl-fixture
```

For live operator-owned pages, use `discover browser-live` or
`crawl browser-live` with a local Playwright storage-state file under
`AOA_COURSE_AUTH_ROOT`. Start discovery from a visible course catalog page, then
crawl the selected course entrypoint:

```bash
aoa-course discover browser-live "https://academy.example/courses" \
  --platform skillspace \
  --run skillspace-live-discovery \
  --state-file "$AOA_COURSE_AUTH_ROOT/skillspace/account.storage-state.json" \
  --register \
  --max-sources 50 \
  --max-pages 5

aoa-course crawl browser-live "https://academy.example/course/mobile-debugging" \
  --platform skillspace \
  --run skillspace-live-crawl \
  --state-file "$AOA_COURSE_AUTH_ROOT/skillspace/account.storage-state.json" \
  --max-lessons 50

aoa-course sync browser-live \
  --run skillspace-live-sync \
  --platform skillspace \
  --state-file "$AOA_COURSE_AUTH_ROOT/skillspace/account.storage-state.json" \
  --max-lessons 50 \
  --build-artifacts
```
