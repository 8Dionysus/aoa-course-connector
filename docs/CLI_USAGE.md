# CLI Usage

```bash
aoa-course doctor
aoa-course init
aoa-course adapters list
aoa-course sources add demo-course --platform offline_export --title "Demo Course"
aoa-course materialize fixture --run starter-fixture
aoa-course materialize stepik-fixture --run stepik-fixture
aoa-course materialize stepik-live 67 --run stepik-live-smoke --max-sections 1 --max-units-per-section 1 --max-steps-per-lesson 2
aoa-course discover browser-fixture --platform getcourse --run getcourse-browser-discovery-fixture --register --max-sources 50
aoa-course discover browser-snapshot /path/to/catalog-snapshot.json --platform getcourse --run getcourse-discovery --register --max-sources 50
aoa-course discover browser-live "https://school.example/teach/control/stream" --platform getcourse --run getcourse-live-discovery --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --register --max-sources 50
aoa-course materialize browser-fixture --platform getcourse --run getcourse-browser-fixture
aoa-course materialize browser-fixture --platform skillspace --run skillspace-browser-fixture
aoa-course materialize browser-snapshot /path/to/snapshot.json --platform getcourse --run getcourse-snapshot
aoa-course materialize browser-live "https://school.example/lesson" --platform getcourse --run getcourse-live --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json"
aoa-course crawl browser-fixture --platform getcourse --run getcourse-browser-crawl-fixture --max-lessons 20
aoa-course crawl browser-snapshot /path/to/snapshot.json --platform getcourse --run getcourse-crawl --max-lessons 50
aoa-course crawl browser-live "https://school.example/teach/control/stream" --platform getcourse --run getcourse-live-crawl --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --max-lessons 50
aoa-course build-index --run starter-fixture
aoa-course build-graph --run starter-fixture
aoa-course query "rollback" --run starter-fixture
aoa-course answer "bootloader unlock rollback" --run starter-fixture
aoa-course mcp tools
```
