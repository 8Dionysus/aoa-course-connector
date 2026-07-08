# CLI Usage

```bash
aoa-course doctor
aoa-course bootstrap fixture --run starter-fixture --connected-run connected-calibration
aoa-course readiness --run starter-fixture
aoa-course connect profile --name operator-live --getcourse-url "https://school.example/teach/control/stream" --skillspace-url "https://academy.example/course/demo" --stepik-course-id 67 --run connected-live-calibration --query "course-specific question" --include-step-sources --max-step-sources all --step-source-timeout 0.5 --semantic-provider http_json_v1 --embedding-endpoint "https://embed.example/v1" --embedding-model "course-embedding" --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN --write "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json"
aoa-course connect inspect "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json"
aoa-course connect status "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json"
aoa-course connect apply "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json"
aoa-course connect run "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json" --platform getcourse
aoa-course readiness --platform stepik --query "course-specific question" --live-scope full-course --include-step-sources --max-step-sources all --step-source-timeout 0.5
aoa-course init
aoa-course adapters list
aoa-course sources add demo-course --platform offline_export --title "Demo Course"
aoa-course sources list --platform getcourse --no-source-refs --connected-run-limit 2
aoa-course sources answer "Stepik public API evidence" --platform stepik --mode hybrid
aoa-course sources answer-matrix --query "Stepik public API evidence" --query "canonical course objects" --platform stepik --mode hybrid
aoa-course eval source-registry-query --query "Stepik public API evidence" --query "canonical course objects" --platform stepik --kind smoke --mode hybrid
aoa-course sources answer "course-specific question" --source-id "source:getcourse:..." --mode hybrid
aoa-course materialize fixture --run starter-fixture
aoa-course materialize stepik-fixture --run stepik-fixture
aoa-course materialize stepik-live 67 --run stepik-live-smoke --max-sections 1 --max-units-per-section 1 --max-steps-per-lesson 2
aoa-course materialize stepik-live 67 --run stepik-full-course --full-course --batch-size 20 --include-step-sources --max-step-sources all
aoa-course discover stepik 67 --register --title "Stepik course 67"
aoa-course sync stepik-fixture --run stepik-sync-fixture --source-id "source:stepik:..." --build-artifacts
aoa-course sync stepik-live --run stepik-live-sync --source-id "source:stepik:..." --full-course --batch-size 20 --include-step-sources --max-step-sources all --build-artifacts
aoa-course sync status --run stepik-sync-fixture --platform stepik
aoa-course preflight live --platform stepik --stepik-token-env STEPIK_API_TOKEN
aoa-course smoke stepik-fixture 67 --run stepik-smoke-fixture --query "Stepik public API evidence"
aoa-course smoke stepik-live 67 --run stepik-live-public-smoke --query "Python course"
aoa-course discover stepik-account --from-fixture --run stepik-account-discovery-fixture --register --source-limit 1
aoa-course discover stepik-account --run stepik-account-discovery-live --token-env STEPIK_API_TOKEN --register --max-pages 5
aoa-course auth import-firefox-state stepik account --state-file "$AOA_COURSE_AUTH_ROOT/stepik/account.storage-state.json" --expect-origin-contains stepik.org
aoa-course auth capture-browser-state stepik account --login-url "https://stepik.org/users/me" --state-file "$AOA_COURSE_AUTH_ROOT/stepik/account.storage-state.json" --expect-origin-contains stepik.org
aoa-course discover stepik-account --state-file "$AOA_COURSE_AUTH_ROOT/stepik/account.storage-state.json" --register --max-pages 5
aoa-course sync stepik-live --state-file "$AOA_COURSE_AUTH_ROOT/stepik/account.storage-state.json" --source-id "source:stepik:..." --build-artifacts
aoa-course auth plan-browser-state getcourse "https://school.example"
aoa-course auth capture-browser-state getcourse "https://school.example" --login-url "https://school.example/cms/system/login" --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --expect-origin-contains "school.example"
aoa-course auth inspect-browser-state "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --expect-origin-contains "school.example"
aoa-course preflight live --platform getcourse --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --expect-origin school.example
aoa-course preflight connected-plan --live-scope full-course --platform stepik --source-id "source:stepik:..." --query "course-specific question" --include-step-sources --max-step-sources all --step-source-timeout 0.5
aoa-course discover browser-fixture --platform getcourse --run getcourse-browser-discovery-fixture --register --max-sources 50
aoa-course discover browser-snapshot /path/to/catalog-snapshot.json --platform getcourse --run getcourse-discovery --register --max-sources 50
aoa-course discover browser-live "https://school.example/teach/control/stream" --platform getcourse --run getcourse-live-discovery --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --register --max-sources 50 --max-pages 5
aoa-course sync browser-fixture --run browser-sync-fixture --source-id "source:getcourse:..." --build-artifacts
aoa-course sync browser-live --run browser-live-sync --source-id "source:getcourse:..." --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" --max-lessons 50 --build-artifacts
aoa-course sync status --run browser-sync-fixture
aoa-course materialize browser-fixture --platform getcourse --run getcourse-browser-fixture
aoa-course materialize browser-fixture --platform skillspace --run skillspace-browser-fixture
aoa-course inspect browser-snapshot /path/to/snapshot.json --platform getcourse --require-ready
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
aoa-course calibration query --run connected-fixture-proof --kind smoke
aoa-course calibration query --run connected-fixture-proof --kind sync --query "course-specific question" --entry-limit 3
aoa-course calibration query-matrix --run connected-fixture-proof --kind smoke --query "GetCourse bootloader rollback evidence" --query "Skillspace logcat bugreport evidence" --query "Stepik public API evidence"
aoa-course calibration connected-run --mode live --platform stepik --allow-network --live-scope bounded --source-limit 1 --run connected-stepik-live-calibration
aoa-course calibration connected-run --mode live --platform stepik --allow-network --live-scope full-course --include-step-sources --max-step-sources all --step-source-timeout 0.5 --source-id "source:stepik:..." --query "course-specific question" --run connected-stepik-full-course-calibration
aoa-course calibration build --run connected-live-calibration --report "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/getcourse-live-smoke.json" --report "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/stepik-live-smoke.json" --preflight-report "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/getcourse-preflight.json"
aoa-course calibration intake --run connected-live-calibration-intake --packet "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/connected-live-calibration/calibration/live_calibration_packet.json"
aoa-course build-index --run starter-fixture
aoa-course build-semantic-index --run starter-fixture
aoa-course preflight semantic-provider --run starter-fixture --provider http_json_v1 --embedding-endpoint "http://127.0.0.1:8000/embeddings" --embedding-model "local-course-embedding" --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN --require-ready
aoa-course build-semantic-index --run starter-fixture --provider http_json_v1 --embedding-endpoint "http://127.0.0.1:8000/embeddings" --embedding-model "local-course-embedding" --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN
aoa-course build-graph --run starter-fixture
aoa-course query "rollback" --run starter-fixture
aoa-course query "rollback" --run starter-fixture --mode semantic
aoa-course answer "bootloader rollback" --run starter-fixture --mode hybrid
aoa-course answer "bootloader unlock rollback" --run starter-fixture
aoa-course lesson-context "bootloader rollback" --run starter-fixture --mode hybrid --graph-limit 12
aoa-course refresh query "bootloader rollback" --run starter-fixture --mode hybrid
aoa-course refresh query "Stepik public API evidence" --run "<checkpoint-run-id>" --mode hybrid --strategy fixture --execute --sync-run stepik-refresh-cycle
aoa-course refresh query "course-specific question" --run "<checkpoint-run-id>" --strategy live --execute --allow-network --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json"
aoa-course graph neighbors lesson:starter:unlock-risk --run starter-fixture
aoa-course evidence inspect "rollback" --run starter-fixture --mode hybrid
aoa-course eval install-route
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
aoa-course mcp call answer '{"query":"bootloader rollback","run":"starter-fixture","mode":"hybrid"}'
aoa-course mcp call evidence_report '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call refresh_plan '{"query":"rollback","run":"starter-fixture","mode":"hybrid"}'
aoa-course mcp call semantic_provider_preflight '{"run":"starter-fixture","provider":"http_json_v1","embedding_endpoint":"http://127.0.0.1:8000/embeddings","embedding_model":"local-course-embedding","embedding_token_env":"AOA_COURSE_EMBEDDING_TOKEN"}'
aoa-course mcp call connection_profile_inspect '{"profile_path":"${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json"}'
aoa-course mcp call connection_profile_status '{"profile_path":"${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json"}'
aoa-course mcp call connection_profile_run_plan '{"profile_path":"${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json","platform":"getcourse"}'
aoa-course mcp call live_preflight '{}'
aoa-course mcp call connected_source_plan '{"live_scope":"full-course","platforms":["stepik"],"source_ids":["source:stepik:..."],"query":"course-specific question","include_step_sources":true,"max_step_sources":"all","step_source_timeout":0.5}'
aoa-course mcp call connected_run '{"run":"mcp-connected-fixture","mode":"fixture","platforms":["stepik"],"query":"Stepik public API evidence"}'
aoa-course mcp call connector_readiness '{"runs":["starter-fixture"]}'
aoa-course mcp call connector_readiness '{"platforms":["stepik"],"live_scope":"full-course","include_step_sources":true,"max_step_sources":"all","step_source_timeout":0.5,"max_lessons":50,"max_pages":5,"max_sources":50}'
```

Use `lesson-context` when an agent needs one CLI packet with the source-backed
answer and nearby course graph context. It returns
`aoa_course_lesson_context_packet_v1`, including the answer packet and
`aoa_course_lesson_graph_context_v1`; `--graph-limit` bounds the per-evidence
lesson neighborhood.
Use `sources list` when the agent needs the configured-source catalog from
shell without writing MCP JSON. It returns the canonical
`aoa_course_source_registry_list_v1` packet directly, accepts `--platform`,
repeated `--source-id`, `--include-disabled`, `--no-source-refs`,
`--no-connected-runs`, and connected-run scan limits, then reports source counts
and query-ready connected-run hints without touching the network.
Use `sources answer` when the agent should ask one question across configured
source-registry entries instead of naming a run id by hand. It reads local
query-ready connected-run receipts, accepts `--platform`, repeated
`--source-id`, `--kind`, retrieval limits, and `--include-source-refs`, then
returns `aoa_course_sources_answer_packet_v1` with one source-backed
answer/context/evidence packet per selected source. By default source refs stay
out of the packet.
Use `sources answer-matrix` when the agent should ask several questions across
the same configured source set without naming run ids by hand. It accepts
repeated `--query` plus the same source, mode, kind, and limit controls as
`sources answer`, then returns `aoa_course_sources_answer_matrix_v1` with one
`aoa_course_sources_answer_packet_v1` per question, aggregate quality,
per-query summaries, and `network_touched: false`.
The default `--coverage-mode all-sources` is strict: every selected source must
answer every query with evidence. Use `--coverage-mode portfolio` when the
agent is checking whether the selected source portfolio can answer each query
from at least one source-backed evidence chain.
Use `eval source-registry-query` as the read-only source-registry quality gate
after fixture or live connected runs. Pass repeated `--query` for an explicit
operator question set, or omit queries to sample non-placeholder saved queries
from recent query-ready connected-run receipts. It emits
`aoa_course_eval_source_registry_query_v1`, requires source-registry
`sources_answer_matrix` quality, evidence, ready-query breadth, and keeps
`source_ref` values out of the packet.
`answer`, `lesson-context`, MCP `answer`, and MCP `evidence_report` expose
`aoa_course_answer_quality_summary_v1` under `quality`; check `ready`,
`blockers`, provenance counts, refresh-hint counts, and `top_result` before
citing an answer.

Use `refresh query` or MCP `refresh_plan` when an agent needs the next exact
steps from a result. The packet includes local rebuild commands, local
`answer`, `lesson-context`, and `evidence inspect` commands for the same query,
and source refresh commands when a registry-matched connected source can be
refreshed.

Use `--source-id` on `preflight live`, `preflight connected-plan`, `readiness`,
and sync commands when an agent is preparing or refreshing one result from a
large source registry. Omitting it keeps the broader platform/source-ref
behavior available for batch refreshes. MCP uses the array form `source_ids`.
Scoped readiness and plan packets repeat the chosen ids in
`source_registry.selected_source_ids`.

Use `bootstrap fixture` as the one-command fresh-install starter route. It
creates storage roots, materializes the starter fixture, builds the keyword
index, semantic index, graph, and default fixture connected-run receipt, then
returns `aoa_course_fixture_bootstrap_receipt_v1` with embedded readiness. By
default it proves GetCourse, Skillspace, and Stepik fixture routes; pass
`--platform` only to narrow a diagnostic run. It is fixture-only and reports
`network_touched: false`.

Use `auth plan-browser-state` before browser live work. Its import, capture,
and inspect commands include `--expect-origin-contains` when the source ref has
a host. For Stepik, GetCourse, and Skillspace, `auth import-firefox-state` can
build the same local storage-state from an existing Firefox login without
touching the network when the expected host is known. `auth
capture-browser-state` remains the fresh-login fallback and repeats the
redacted origin check in the receipt through `expected_origin_matched`, so a
state file captured from the wrong school host is caught before discovery or
sync.
`preflight connected-plan` also emits `state_file_candidates` inside
`browser_auth_plans`: one per operator source host, with a host-specific
state-file path, Firefox import, capture, inspect, and source-scoped recheck
command. Use those per-host candidates when one GetCourse or Skillspace
platform plan contains several schools or custom domains.

Use `calibration connected-run --mode fixture` as the one-command local proof
that source registry sync, smoke reports, calibration packet, intake, and the
connected run receipt all write to portable runtime artifact storage. Use
`--mode live --allow-network` only after `preflight connected-plan` shows the
selected sources are ready; when the plan is ready, its `connected_run_plan`
contains the exact `calibration connected-run --mode live --allow-network`
command for the same platforms, source ids, query, live scope, and browser
`--link-pattern`. The same plan also carries `mcp_tool_call` and `mcp_command`
for MCP `connected_run`, preserving the same source ids, traversal bounds,
live scope, and explicit `allow_network`.
By default, `preflight connected-plan` and the MCP `connected_source_plan` route
cover GetCourse, Skillspace, and Stepik together; pass `--platform`/`platforms`
to narrow a diagnostic run and `--source-id`/`source_ids` to plan only one
registered source so another not-yet-authorized source does not block the
ready source's connected-run plan.
For Stepik, `--include-step-sources` is bounded by `--max-step-sources 10` and
`--step-source-timeout 5.0` unless you pass a different limit. The same fields
flow through `readiness`, `preflight connected-plan`, MCP `connector_readiness`,
MCP `connected_source_plan`, `connect profile`, `connect run`, and MCP
`connected_run`, so `--max-step-sources all` should be a deliberate long
enrichment run rather than an accidental default.
Fixture-discovered browser sources and reserved example hosts such as
`*.example` are install proof only. Live preflight marks them as
`fixture_or_example_source` with `operator_live_candidate: false`, does not
emit `sync browser-live` for them, and asks the operator to register a real
operator-owned course URL before live sync.
For browser-session sources, pass `--link-pattern` or MCP `link_pattern` when a
school needs a narrower course/lesson URL glob for live sync, smoke, and the
connected-run plan.
Use `calibration status --run <run>` to inspect the connected-run receipt
without re-running sync or touching the network. The status packet includes
`snapshot_audit`, `repair_lanes` for partial runs, and `query_plan` entries
with a selected `query_mode`, CLI `query`, `answer`, `sources answer`, and
`lesson-context` commands plus MCP `mcp_commands` for `source_answer`, `search`,
`answer`, `lesson_context`, and `evidence_report`. Sync-backed entries also
carry `stable_identity` with a fingerprint, counts, and samples for the
canonical IDs that should survive repeat refreshes of the same registered
source.

Use `calibration query --run <run>` when the next agent needs proof that the
connected run is actually queryable. It reads the same receipt, selects
query-ready entries, and returns `aoa_course_connected_run_query_packet_v1`
with source-backed `answer_packet`, `lesson_context`, `evidence_report`,
freshness, authority, graph context, blockers, and `network_touched: false`.
Entries from smoke runs can reuse their saved query; sync-only entries need an
explicit `--query`.

Use `calibration query-matrix --run <run> --query ... --query ...` to check
several real course questions against the same connected-run artifacts without
touching the network again:

```bash
aoa-course calibration query-matrix \
  --run connected-fixture-proof \
  --kind smoke \
  --query "GetCourse bootloader rollback evidence" \
  --query "Skillspace logcat bugreport evidence" \
  --query "Stepik public API evidence"
```

The packet is `aoa_course_connected_run_query_matrix_v1`. It keeps each
per-question `aoa_course_connected_run_query_packet_v1`, compact
`query_summaries`, aggregate result/evidence/graph-context quality, blockers,
and `network_touched: false`.

Use `eval retrieval-loop` for the offline agent retrieval contract. It prepares
the starter, GetCourse, Skillspace, and Stepik fixture runs, builds
keyword/semantic indexes and graphs, and verifies CLI answer, CLI
lesson-context, MCP search, MCP answer, MCP lesson_context, and MCP
evidence_report without touching the network.

Use `inspect browser-snapshot` before materializing operator snapshots. The
packet is `aoa_course_browser_snapshot_audit_v1`: it reports whether the file is
ready for discovery, crawl, materialization, or smoke; counts the visible course
links, lesson links, progress, comments, transcripts, caption sidecars,
caption-resource parse errors, and pagination; and emits repair lanes without
printing raw HTML or caption text.

Use `readiness` when an agent or operator needs one read-only route audit before
continuing. It emits `aoa_course_connector_readiness_v1` with install route
files, storage roots, source registry counts, per-run `agent_query_ready`,
source-registry query-ready connected receipts, connected-source
`connected_live_ready`, semantic provider readiness, `semantic_provider_ready`,
connected-run receipt status, MCP tool coverage, embedded `connected_run_plan`,
and next commands. If a selected starter run is missing but the source registry
already has query-ready connected-run receipts, `lanes.agent_query_ready` is
true through `lanes.source_registry_query_ready` and `next_commands` points to
`sources list`, `sources answer`, or `sources answer-matrix` before fixture
bootstrap. For
browser-session sources, `--link-pattern` flows into the embedded connected
plan and its ready connected-run plan. `--max-lessons`, `--max-pages`,
`--max-sources`, `--live-scope`, `--include-step-sources`,
`--max-step-sources`, and `--step-source-timeout` also flow into the embedded
connected plan, so a readiness packet can preserve either a bounded browser
crawl or an explicit Stepik full-course/source-enrichment plan.
Pass `--semantic-provider http_json_v1`, `--embedding-endpoint`,
`--embedding-model`, and `--embedding-token-env` when the readiness packet
should verify an operator-selected external embedding endpoint route. The
check is read-only: it verifies normalized bundle presence, endpoint/model
configuration, token env presence, and redaction policy without calling the
endpoint.
If the selected connected-run receipt is missing, `next_commands` still points
to fixture bootstrap. If the selected receipt exists as a partial connected-run
with `repair_lanes`, `readiness` surfaces those repair lane commands directly,
for example the read-only `preflight connected-plan` check and the gated
`calibration connected-run --mode live --allow-network` rerun, instead of
suggesting a blind fixture bootstrap.
`--require-ready` exits non-zero only when `operational_ready` is false; live
source execution remains gated behind the separate `--allow-network` commands.

Use `connect profile` when the operator is ready to
provide real source refs and provider choices. The command writes
`aoa_course_connection_profile_v1` under runtime artifact storage. It may
include operator course URLs and state-file paths, so keep it outside Git; it
does not include token values. `connect inspect` reads that profile and returns
source registration commands, browser-state Firefox import/capture/inspect
commands, per-platform `preflight connected-plan` commands, and semantic
provider preflight/build/query commands without mutating local state or
touching the network. `connect apply` registers the profile sources in the local source
registry only; browser login, Stepik API calls, semantic builds, and connected
live calibration remain separate explicit commands.
MCP `connection_profile_inspect` exposes the same read-only inspection for
agents that continue from the MCP surface.
Use `connect status` or MCP `connection_profile_status` when an agent needs the
compact `aoa_course_connection_profile_status_v1` go/no-go packet: it reports
`ready_for_connected_run`, `ready_for_semantic_build`, source/auth/plan counts,
blockers, next commands, and any ready
`calibration connected-run --mode live --allow-network` commands.
Use MCP `connection_profile_run_plan` when an agent needs the selected
`aoa_course_connection_profile_run_plan_v1` from the same profile without
leaving the MCP surface.
Use `connect run` as the executable profile bridge: by default it returns
`aoa_course_connection_profile_run_receipt_v1` with `network_touched: false`
and the selected platform/source run command; add `--allow-network` only after
that plan is ready to execute the live connected-run.

Use `preflight semantic-provider` before external vector calibration. The
`local_hashing_v1` route is ready whenever the normalized bundle exists.
The `http_json_v1` route requires an operator-configured endpoint, model name,
and token environment variable with a value. The packet is
`aoa_course_semantic_provider_preflight_v1`; it reports
`token_env_present`, `token_value_logged: false`, `network_touched: false`,
and exact `build-semantic-index`, semantic query, hybrid answer, and MCP
`semantic_search` commands. It never prints the token value.
