# MCP Usage

The server package name is `aoa-course-connector-mcp`.

Initial tools:

- `list_sources`
- `connector_readiness`
- `ingest_status`
- `sync_status`
- `live_preflight`
- `connected_source_plan`
- `connection_profile_inspect`
- `connection_profile_status`
- `connection_profile_run_plan`
- `semantic_provider_preflight`
- `browser_snapshot_audit`
- `connected_run`
- `connected_run_status`
- `refresh_plan`
- `search`
- `semantic_search`
- `hybrid_search`
- `answer`
- `lesson_context`
- `graph_neighbors`
- `freshness_report`
- `evidence_report`

CLI smoke:

```bash
aoa-course mcp tools
aoa-course mcp call search '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call search '{"query":"rollback","run":"starter-fixture","mode":"hybrid"}'
aoa-course mcp call semantic_search '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call hybrid_search '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call answer '{"query":"bootloader rollback","run":"starter-fixture","mode":"hybrid"}'
aoa-course mcp call connector_readiness '{"runs":["starter-fixture"]}'
aoa-course mcp call ingest_status '{"run":"starter-fixture"}'
aoa-course mcp call lesson_context '{"query":"mentor anti-rollback vendor boot","run":"getcourse-browser-fixture","graph_limit":12}'
aoa-course mcp call graph_neighbors '{"node_id":"lesson:starter:unlock-risk","run":"starter-fixture"}'
aoa-course mcp call freshness_report '{"run":"starter-fixture"}'
aoa-course mcp call evidence_report '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call refresh_plan '{"query":"rollback","run":"starter-fixture","mode":"hybrid"}'
aoa-course mcp call sync_status '{"sync_run":"browser-sync-fixture"}'
aoa-course mcp call sync_status '{"sync_run":"stepik-sync-fixture","platform":"stepik"}'
aoa-course mcp call live_preflight '{}'
aoa-course mcp call connected_source_plan '{"live_scope":"bounded","source_ids":["source:getcourse:..."],"query":"course-specific question","link_pattern":"*/lessons/*"}'
aoa-course mcp call connection_profile_inspect '{"profile_path":".connector-state/artifacts/connections/operator-live.connection-profile.json"}'
aoa-course mcp call connection_profile_status '{"profile_path":".connector-state/artifacts/connections/operator-live.connection-profile.json"}'
aoa-course mcp call connection_profile_run_plan '{"profile_path":".connector-state/artifacts/connections/operator-live.connection-profile.json","platform":"getcourse"}'
aoa-course mcp call semantic_provider_preflight '{"run":"starter-fixture","provider":"http_json_v1","embedding_endpoint":"http://127.0.0.1:8000/embeddings","embedding_model":"local-course-embedding","embedding_token_env":"AOA_COURSE_EMBEDDING_TOKEN"}'
aoa-course mcp call browser_snapshot_audit '{"snapshot_path":"connector/fixtures/browser/getcourse_starter_snapshot.json","platform":"getcourse"}'
aoa-course mcp call connected_run '{"run":"mcp-connected-fixture","mode":"fixture","platforms":["stepik"],"query":"Stepik public API evidence"}'
aoa-course mcp call connected_run_status '{"run":"connected-fixture-proof"}'
aoa-course mcp call connector_readiness '{"platforms":["stepik"],"live_scope":"full-course","include_step_sources":true,"max_lessons":50,"max_pages":5,"max_sources":50}'
```

`semantic_search` follows the semantic index artifact for the requested run. If
that artifact was built with `http_json_v1`, the MCP route uses the same
operator-configured endpoint and token environment variable name for query
vectors; token values are read from the environment and are not written to the
artifact or tool result.

`semantic_provider_preflight` is the read-only MCP route for external semantic provider
connection. It returns `aoa_course_semantic_provider_preflight_v1`
with normalized bundle readiness, semantic index artifact path, provider
configuration, `token_env_present`, `token_value_logged: false`,
`network_touched: false`, and exact build/query/MCP follow-up commands. Use it
before `build-semantic-index --provider http_json_v1` so missing endpoint,
model, or token env state is visible before the first network call.

`browser_snapshot_audit` is the read-only MCP route for local GetCourse and
Skillspace browser snapshot diagnostics. It returns
`aoa_course_browser_snapshot_audit_v1` with discovery, crawl,
materialization, and smoke readiness; visible course/lesson link, progress,
comment, transcript, caption sidecar, caption-resource error, and pagination
counts; repair lanes; and next commands. It does not touch the network and does
not include raw HTML or caption text in `structuredContent`.

`ingest_status` is the read-only run readiness packet. It reports normalized
bundle counts, materialization receipt summaries, keyword/semantic index
metadata, graph node/edge counts, `agent_query_ready`, and next build/query
commands without reading private raw payloads into `structuredContent`.

`connector_readiness` is the read-only whole-connector route audit. It returns
`aoa_course_connector_readiness_v1` with install route files, storage roots,
source registry counts, selected run readiness, connected-source plan summary,
connected-run receipt status, MCP tool coverage, `operational_ready`,
`connected_live_ready`, embedded `connected_run_plan`, and next commands.
For browser-session sources, pass `link_pattern` when the whole-connector audit
should preserve a narrowed course/lesson glob in the connected-source plan and
ready connected-run plan. Pass `max_lessons`, `max_pages`, `max_sources`,
`live_scope`, and `include_step_sources` when that audit must preserve the same
bounded or full-course traversal breadth an operator expects the later
connected run to use. It is the first MCP packet an agent should inspect when
deciding whether to install, build starter artifacts, connect sources, run
fixture calibration, or move into gated live work.
On a fresh state, its `next_commands` can point to CLI `bootstrap fixture`,
which creates the local starter artifacts and default fixture connected-run
receipt before the agent returns to MCP queries.
When the selected connected-run receipt already exists but is partial or
otherwise non-ok, `connector_readiness` lifts its `repair_lanes` into the
top-level `next_commands`. Agents should follow those lane commands, such as
`preflight connected-plan` and the gated
`calibration connected-run --mode live --allow-network` rerun, instead of
treating the receipt as missing and running fixture bootstrap again.
When `platforms` is omitted, `live_preflight`, `connected_source_plan`, and
`connector_readiness` use the full priority set: GetCourse, Skillspace, and
Stepik. Pass `platforms` only to narrow a diagnostic or platform-specific run.
Pass `source_ids` when a large registry contains several sources but the agent
is preparing one selected source. The source scope applies before any
network-touching command is emitted, so a ready source is not blocked by another
source whose browser state or token is not ready yet.
`connector_readiness` also embeds a compact `semantic_provider_preflight`
packet. Pass `semantic_provider`, `embedding_endpoint`, `embedding_model`, and
`embedding_token_env` when the MCP audit should check the same external
embedding endpoint that will later build the connected-run semantic index.

## JSON-RPC Stdio

The package entrypoint `aoa-course-connector-mcp` also speaks MCP-style
JSON-RPC over stdio. It supports:

- `initialize`
- `ping`
- `tools/list`
- `tools/call`
- `notifications/initialized`

On `initialize`, the server returns the supported protocol version
`2025-11-25`. If a client sends an unsupported protocol version, the response
falls back to the supported version instead of echoing an unusable value.

Example smoke:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"local-agent","version":"0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search","arguments":{"query":"rollback","run":"starter-fixture"}}}' \
  '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"refresh_plan","arguments":{"query":"rollback","run":"starter-fixture","mode":"keyword"}}}' \
  '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"live_preflight","arguments":{}}}' \
  '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"connected_source_plan","arguments":{"live_scope":"bounded"}}}' \
  '{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"connected_run","arguments":{"run":"mcp-connected-fixture","mode":"fixture","platforms":["stepik"]}}}' \
  '{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"connected_run_status","arguments":{"run":"mcp-connected-fixture"}}}' \
  '{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"browser_snapshot_audit","arguments":{"snapshot_path":"connector/fixtures/browser/getcourse_starter_snapshot.json","platform":"getcourse"}}}' \
  '{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"connector_readiness","arguments":{"runs":["starter-fixture"]}}}' \
  | aoa-course-connector-mcp
```

Tool calls return both text content and `structuredContent` so agents can keep
source-backed result objects, `score`/`rank_score`, `authority_tier`,
rank features, evidence chains, freshness/authority reports, refresh hints, and
graph packets without reparsing prose. `answer` returns the full
`aoa_course_answer_packet_v1` through MCP, including evidence, freshness,
authority, refresh, and quality reports. `lesson_context` returns the answer
packet plus `aoa_course_lesson_graph_context_v1`, which follows each distinct
evidence lesson into nearby course/module/topic/asset/comment/transcript graph
neighbors. Use `graph_limit` to bound the per-lesson neighborhood.

`evidence_report` is the compact agent plan for a query. It returns the
evidence chain, freshness report, authority report, refresh report, and result
references with source URL, matched snippet, course path, fetched timestamp,
freshness state, authority tier, source authority, rank score, rank features,
and `refresh_hint`. It also returns the answer packet `quality` summary, so an
MCP-side agent can check proof-field readiness and blockers without fetching
the full answer packet.
The hint always gives local
`build-index`, `build-semantic-index`, and `build-graph` rebuild commands, plus
local `answer`, `lesson-context`, and `evidence inspect` commands for rerunning
the same query after rebuild or source refresh. For GetCourse, Skillspace, and
Stepik it also points agents to `preflight connected-plan` first, and only
exposes live sync commands when the result source matches the local source
registry. Those sync commands are
`--source-id` scoped so refreshing one result does not accidentally refresh an
entire platform registry.

`refresh_plan` is the read-only MCP plan for the full refresh loop. It
returns an `aoa_course_refresh_cycle_v1` packet with the current answer packet,
selected source-backed result, planned local rebuild/query/source commands,
refresh hint, optional connected-source plan, and `network_touched: false`. Network or
filesystem-mutating refresh execution stays on the CLI side through
`aoa-course refresh query --strategy fixture --execute` or the explicitly gated
live form with `--strategy live --execute --allow-network`.

`live_preflight` is read-only and returns `network_touched: false`. It lets an
agent inspect Stepik token presence, browser storage-state readiness, registered
source readiness, and next commands before attempting live discovery or sync.
It reports token/cookie/localStorage presence and counts only; secret values are
not included in `structuredContent`.

`connected_source_plan` is also read-only and returns `network_touched: false`.
It wraps the live preflight report into an operator plan plan with exact
preflight-report, source sync, per-source smoke, `calibration build`, and
`connected_run_plan` commands. Ready `connected_run_plan` entries include both
the CLI command and `mcp_tool_call`/`mcp_command` for MCP `connected_run`, with
the same source ids, traversal bounds, live scope, and explicit
`allow_network`. Agents should use it before connected live
work so blocked sources, missing auth state, missing Stepik token env, runtime
report paths, and calibration packet inputs are explicit before
network-touching commands run.
When `source_ids` is supplied, `source_plans`, platform readiness, and
`connected_run_plan.source_ids` are scoped to those ids. The same selection
is surfaced in `source_registry.selected_source_ids` for agent-side evidence.
Browser fixture sources and reserved example hosts such as `*.example` are not
treated as operator live candidates. They remain useful install proof, but
`connected_source_plan` marks them with `fixture_or_example_source` and
`operator_live_candidate: false`, withholds browser live sync commands, and
points the operator to register real operator-owned course URLs first.
For browser-session platforms, pass `link_pattern` when a school needs a
narrower course/lesson URL glob in live sync, smoke, and connected-run
commands.
For browser-session platforms, read `browser_auth_plans` first: it groups
GetCourse/Skillspace sources by host, reports missing or mismatched
storage-state, and provides the exact auth capture, redacted inspect, and
recheck commands needed to turn blocked sources into sync-ready sources.
When one platform contains several schools or custom domains, use
`browser_auth_plans[].state_file_candidates`: each entry gives a per-host
state-file path plus capture, inspect, and source-scoped recheck commands.
When a shell-side operator plan is needed, run the CLI equivalent with
`--write-runbook "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connected-source-runbook.md"`; MCP
keeps the structured plan in `structuredContent`, while the CLI writes the
Markdown checklist as runtime-only artifact state.
The default `live_scope` is `bounded`; set `live_scope: "full-course"` and
`include_step_sources: true` only when the operator intentionally wants the
larger Stepik full-course/source-enrichment route.

`connection_profile_inspect` is the MCP-side reader for a local
`aoa_course_connection_profile_v1` file created by `aoa-course connect
profile`. It returns `aoa_course_connection_profile_inspection_v1` with source
registration state, browser auth capture/inspect commands, per-platform
connected-plan commands, semantic-provider preflight/build/query commands, and
`network_touched: false`. It does not mutate the source registry; use CLI
`connect apply` when the operator wants to register the profile's non-secret
source refs.
`connection_profile_status` is the compact MCP go/no-go reader for the same
profile. It returns `aoa_course_connection_profile_status_v1` with
the nested `aoa_course_connection_profile_readiness_v1`,
`ready_for_connected_run`, `ready_for_semantic_build`, source/auth/plan counts,
blockers, next commands, and ready
`calibration connected-run --mode live --allow-network` commands when all
selected profile sources are registered and authorized.
`connection_profile_run_plan` returns the selected
`aoa_course_connection_profile_run_plan_v1` for a profile, platform, and
optional `source_ids` without touching the network. MCP remains read-only here;
use CLI `connect run <profile> --platform <platform> --allow-network` only when
the operator wants explicit live execution from the selected profile route.

`connected_run` executes the same connected-source calibration backend as CLI
`calibration connected-run`. Use `mode: "fixture"` for a no-network MCP proof
that writes the connected receipt, plan, runbook, smoke reports, calibration
packet, intake report, and query plan under runtime artifact storage. Use
`mode: "live"` only after `connected_source_plan` is ready; live mode still
returns a partial network-gate receipt unless `allow_network: true` is present.
The result schema is `aoa_course_connected_calibration_run_receipt_v1`.

`connected_run_status` is the read-only MCP plan after CLI
`calibration connected-run` or MCP `connected_run`. It returns
`aoa_course_connected_calibration_run_status_v1` with status, stages,
artifact paths, `source_selection`, `execution_options`, `query_plan`,
packet quality, privacy flags, failures, `repair_lanes`, and next steps from
`connected_calibration_receipt.json`.
The `snapshot_audit` child packet is
`aoa_course_connected_snapshot_audit_status_v1`: it summarizes browser smoke
snapshot-audit coverage, failure counts, filtered
`browser_snapshot_diagnostics` repair lanes, and the next diagnostic commands.
`repair_lanes` classify partial connected-run failures into network gate,
source auth/readiness, source selection, sync, live smoke/selector, and
calibration-packet intake routes with concrete next commands.
`execution_options` records the query, browser `link_pattern`, source limit,
and traversal bounds used by the connected run without exposing token values.
`query_plan` gives agents the run ids, local keyword/semantic/graph/answer
paths, the selected `query_mode`, and ready CLI `query`, `answer`, and
`lesson-context` commands produced by sync and smoke actions. Each entry also
includes `mcp_commands` for `search`, `answer`, `lesson_context`, and
`evidence_report`, so an MCP-side agent can query the connected run without
switching back to shell planning or reparsing artifact paths. It never executes
network work; missing receipts return
`status: "missing"` so agents can ask for the fixture or live connected-run
command instead of guessing from the
filesystem.

`aoa-course eval retrieval-loop` is the fixture-safe MCP/CLI contract check: it
prepares starter, GetCourse, Skillspace, and Stepik runs, then verifies MCP
`search`, `answer`, `lesson_context`, and `evidence_report` alongside CLI
answer and lesson-context packets.
