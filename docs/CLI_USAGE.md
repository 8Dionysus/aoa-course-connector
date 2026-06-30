# CLI Usage

```bash
aoa-course doctor
aoa-course init
aoa-course adapters list
aoa-course sources add demo-course --platform offline_export --title "Demo Course"
aoa-course materialize fixture --run starter-fixture
aoa-course materialize stepik-fixture --run stepik-fixture
aoa-course materialize stepik-live 67 --run stepik-live-smoke --max-sections 1 --max-units-per-section 1 --max-steps-per-lesson 2
aoa-course materialize stepik-live 67 --run stepik-full-course --full-course --batch-size 20 --include-step-sources
aoa-course discover stepik 67 --register --title "Stepik course 67"
aoa-course sync stepik-fixture --run stepik-sync-fixture --build-artifacts
aoa-course sync stepik-live --run stepik-live-sync --full-course --batch-size 20 --include-step-sources --build-artifacts
aoa-course sync status --run stepik-sync-fixture --platform stepik
aoa-course preflight live --platform stepik --stepik-token-env STEPIK_API_TOKEN
aoa-course smoke stepik-fixture 67 --run stepik-smoke-fixture --query "Stepik public API evidence"
aoa-course smoke stepik-live 67 --run stepik-live-public-smoke --query "Python course"
aoa-course discover stepik-account --from-fixture --run stepik-account-discovery-fixture --register --source-limit 1
aoa-course discover stepik-account --run stepik-account-discovery-live --token-env STEPIK_API_TOKEN --register --max-pages 5
aoa-course auth plan-browser-state getcourse "https://school.example"
aoa-course auth capture-browser-state getcourse "https://school.example" --login-url "https://school.example/cms/system/login" --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json"
aoa-course auth inspect-browser-state "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --expect-origin-contains "school.example"
aoa-course preflight live --platform getcourse --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --expect-origin school.example
aoa-course discover browser-fixture --platform getcourse --run getcourse-browser-discovery-fixture --register --max-sources 50
aoa-course discover browser-snapshot /path/to/catalog-snapshot.json --platform getcourse --run getcourse-discovery --register --max-sources 50
aoa-course discover browser-live "https://school.example/teach/control/stream" --platform getcourse --run getcourse-live-discovery --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --register --max-sources 50 --max-pages 5
aoa-course sync browser-fixture --run browser-sync-fixture --build-artifacts
aoa-course sync browser-live --run browser-live-sync --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --max-lessons 50 --build-artifacts
aoa-course sync status --run browser-sync-fixture
aoa-course materialize browser-fixture --platform getcourse --run getcourse-browser-fixture
aoa-course materialize browser-fixture --platform skillspace --run skillspace-browser-fixture
aoa-course materialize browser-snapshot /path/to/snapshot.json --platform getcourse --run getcourse-snapshot
aoa-course materialize browser-live "https://school.example/lesson" --platform getcourse --run getcourse-live --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json"
aoa-course crawl browser-fixture --platform getcourse --run getcourse-browser-crawl-fixture --max-lessons 20
aoa-course crawl browser-snapshot /path/to/snapshot.json --platform getcourse --run getcourse-crawl --max-lessons 50
aoa-course crawl browser-live "https://school.example/teach/control/stream" --platform getcourse --run getcourse-live-crawl --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --max-lessons 50
aoa-course smoke browser-fixture --platform getcourse --run getcourse-browser-smoke-fixture
aoa-course smoke browser-snapshot --platform getcourse --catalog-snapshot /path/to/catalog.json --course-snapshot /path/to/course.json --query "course-specific question"
aoa-course smoke browser-live --platform getcourse --catalog-url "https://school.example/teach/control/stream" --course-url "https://school.example/teach/control/stream/view/id/201" --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --query "course-specific question"
aoa-course build-index --run starter-fixture
aoa-course build-semantic-index --run starter-fixture
aoa-course build-graph --run starter-fixture
aoa-course query "rollback" --run starter-fixture
aoa-course query "rollback" --run starter-fixture --mode semantic
aoa-course answer "bootloader rollback" --run starter-fixture --mode hybrid
aoa-course answer "bootloader unlock rollback" --run starter-fixture
aoa-course eval answer-quality
aoa-course materialize fixture --run freshness-ranking-fixture --fixture connector/fixtures/course/freshness_conflict_course.json
aoa-course build-index --run freshness-ranking-fixture
aoa-course build-semantic-index --run freshness-ranking-fixture
aoa-course eval freshness-ranking
aoa-course eval browser-progress-comments
aoa-course eval semantic-index
aoa-course mcp tools
aoa-course mcp call live_preflight '{"platforms":["getcourse","stepik"]}'
```
