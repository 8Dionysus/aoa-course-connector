# CLI Usage

```bash
aoa-course doctor
aoa-course bootstrap fixture --run starter-fixture --connected-run connected-calibration
aoa-course readiness --run starter-fixture
aoa-course init
aoa-course adapters list
aoa-course sources add demo-course --platform offline_export --title "Demo Course"
aoa-course materialize fixture --run starter-fixture
aoa-course materialize stepik-fixture --run stepik-fixture
aoa-course materialize stepik-live 67 --run stepik-live-smoke --max-sections 1 --max-units-per-section 1 --max-steps-per-lesson 2
aoa-course materialize stepik-live 67 --run stepik-full-course --full-course --batch-size 20 --include-step-sources
aoa-course discover stepik 67 --register --title "Stepik course 67"
aoa-course sync stepik-fixture --run stepik-sync-fixture --source-id "source:stepik:..." --build-artifacts
aoa-course sync stepik-live --run stepik-live-sync --source-id "source:stepik:..." --full-course --batch-size 20 --include-step-sources --build-artifacts
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
aoa-course preflight connected-plan --live-scope bounded --query "course-specific question" --link-pattern "*/lessons/*" --write-runbook "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connected-source-runbook.md"
aoa-course discover browser-fixture --platform getcourse --run getcourse-browser-discovery-fixture --register --max-sources 50
aoa-course discover browser-snapshot /path/to/catalog-snapshot.json --platform getcourse --run getcourse-discovery --register --max-sources 50
aoa-course discover browser-live "https://school.example/teach/control/stream" --platform getcourse --run getcourse-live-discovery --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --register --max-sources 50 --max-pages 5
aoa-course sync browser-fixture --run browser-sync-fixture --source-id "source:getcourse:..." --build-artifacts
aoa-course sync browser-live --run browser-live-sync --source-id "source:getcourse:..." --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --max-lessons 50 --build-artifacts
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
aoa-course eval live-calibration
aoa-course calibration connected-run --mode fixture --run connected-fixture-proof
aoa-course calibration status --run connected-fixture-proof
aoa-course calibration connected-run --mode live --platform stepik --allow-network --live-scope bounded --source-limit 1 --run connected-stepik-live-calibration
aoa-course calibration build --run connected-live-calibration --report "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/getcourse-live-smoke.json" --report "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/stepik-live-smoke.json" --preflight-report "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/getcourse-preflight.json"
aoa-course calibration intake --run connected-live-calibration-intake --packet "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/connected-live-calibration/calibration/live_calibration_packet.json"
aoa-course build-index --run starter-fixture
aoa-course build-semantic-index --run starter-fixture
aoa-course build-semantic-index --run starter-fixture --provider http_json_v1 --embedding-endpoint "http://127.0.0.1:8000/embeddings" --embedding-model "local-course-embedding" --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN
aoa-course build-graph --run starter-fixture
aoa-course query "rollback" --run starter-fixture
aoa-course query "rollback" --run starter-fixture --mode semantic
aoa-course answer "bootloader rollback" --run starter-fixture --mode hybrid
aoa-course answer "bootloader unlock rollback" --run starter-fixture
aoa-course refresh query "bootloader rollback" --run starter-fixture --mode hybrid
aoa-course refresh query "Stepik public API evidence" --run "<checkpoint-run-id>" --mode hybrid --strategy fixture --execute --sync-run stepik-refresh-cycle
aoa-course refresh query "course-specific question" --run "<checkpoint-run-id>" --strategy live --execute --allow-network --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json"
aoa-course graph neighbors lesson:starter:unlock-risk --run starter-fixture
aoa-course evidence inspect "rollback" --run starter-fixture --mode hybrid
aoa-course eval answer-quality
aoa-course materialize fixture --run freshness-ranking-fixture --fixture connector/fixtures/course/freshness_conflict_course.json
aoa-course build-index --run freshness-ranking-fixture
aoa-course build-semantic-index --run freshness-ranking-fixture
aoa-course eval freshness-ranking
aoa-course materialize fixture --run authority-ranking-fixture --fixture connector/fixtures/course/authority_conflict_course.json
aoa-course build-index --run authority-ranking-fixture
aoa-course build-semantic-index --run authority-ranking-fixture
aoa-course eval authority-ranking
aoa-course eval adapter-authority
aoa-course eval browser-progress-comments
aoa-course eval browser-transcripts
aoa-course eval semantic-index
aoa-course mcp tools
aoa-course mcp call ingest_status '{"run":"starter-fixture"}'
aoa-course mcp call graph_neighbors '{"node_id":"lesson:starter:unlock-risk","run":"starter-fixture"}'
aoa-course mcp call freshness_report '{"run":"starter-fixture"}'
aoa-course mcp call evidence_report '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call refresh_plan '{"query":"rollback","run":"starter-fixture","mode":"hybrid"}'
aoa-course mcp call live_preflight '{}'
aoa-course mcp call connected_source_plan '{"live_scope":"bounded","query":"course-specific question","link_pattern":"*/lessons/*"}'
aoa-course mcp call connector_readiness '{"runs":["starter-fixture"]}'
```

Use `--source-id` on sync commands when an agent is refreshing one result from a
large source registry. Omitting it keeps the broader platform/source-ref sync
behavior available for batch refreshes.

Use `bootstrap fixture` as the one-command fresh-install starter route. It
creates storage roots, materializes the starter fixture, builds the keyword
index, semantic index, graph, and default fixture connected-run receipt, then
returns `aoa_course_fixture_bootstrap_receipt_v1` with embedded readiness. By
default it proves GetCourse, Skillspace, and Stepik fixture routes; pass
`--platform` only to narrow a diagnostic run. It is fixture-only and reports
`network_touched: false`.

Use `calibration connected-run --mode fixture` as the one-command local proof
that source registry sync, smoke reports, calibration packet, intake, and the
connected run receipt all write to portable runtime artifact storage. Use
`--mode live --allow-network` only after `preflight connected-plan` shows the
selected sources are ready; when the plan is ready, its `connected_run_handoff`
contains the exact `calibration connected-run --mode live --allow-network`
command for the same platforms, source ids, query, live scope, and browser
`--link-pattern`.
By default, `preflight connected-plan` and the MCP `connected_source_plan` route
cover GetCourse, Skillspace, and Stepik together; pass `--platform` or
`platforms` only to narrow a diagnostic run.
For browser-session sources, pass `--link-pattern` or MCP `link_pattern` when a
school needs a narrower course/lesson URL glob for live sync, smoke, and the
connected-run handoff.
Use `calibration status --run <run>` to inspect the connected-run receipt
without re-running sync or touching the network.

Use `readiness` when an agent or operator needs one read-only route audit before
continuing. It emits `aoa_course_connector_readiness_v1` with install route
files, storage roots, source registry counts, per-run `agent_query_ready`,
connected-source `connected_live_ready`, connected-run receipt status, MCP tool
coverage, embedded `connected_run_handoff`, and next commands. For
browser-session sources, `--link-pattern` flows into the embedded connected
plan and its ready connected-run handoff. `--require-ready` exits non-zero only
when `operational_ready` is false; live source execution remains gated behind
the separate `--allow-network` commands.
