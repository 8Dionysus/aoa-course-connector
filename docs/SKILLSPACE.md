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
snapshot and course-tree crawl adapters:

```bash
aoa-course materialize browser-fixture --platform skillspace --run skillspace-browser-fixture
aoa-course build-index --run skillspace-browser-fixture
aoa-course build-graph --run skillspace-browser-fixture
aoa-course answer "Skillspace logcat bugreport evidence" --run skillspace-browser-fixture

aoa-course crawl browser-fixture --platform skillspace --run skillspace-browser-crawl-fixture --max-lessons 20
aoa-course build-index --run skillspace-browser-crawl-fixture
aoa-course build-graph --run skillspace-browser-crawl-fixture
aoa-course answer "Skillspace logcat bugreport evidence" --run skillspace-browser-crawl-fixture
```

For live operator-owned pages, use `crawl browser-live` with a local Playwright
storage-state file under `AOA_COURSE_AUTH_ROOT` and start from a visible course
index page:

```bash
aoa-course crawl browser-live "https://academy.example/course/mobile-debugging" \
  --platform skillspace \
  --run skillspace-live-crawl \
  --state-file "$AOA_COURSE_AUTH_ROOT/skillspace/account.storage-state.json" \
  --max-lessons 50
```
