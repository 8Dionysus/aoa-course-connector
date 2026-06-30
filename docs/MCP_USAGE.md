# MCP Usage

The server package name is `aoa-course-connector-mcp`.

Initial tools:

- `list_sources`
- `connector_readiness`
- `ingest_status`
- `sync_status`
- `live_preflight`
- `connected_source_plan`
- `connected_run_status`
- `refresh_plan`
- `search`
- `semantic_search`
- `hybrid_search`
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
aoa-course mcp call connector_readiness '{"runs":["starter-fixture"],"platforms":["getcourse","stepik"]}'
aoa-course mcp call ingest_status '{"run":"starter-fixture"}'
aoa-course mcp call lesson_context '{"query":"mentor anti-rollback vendor boot","run":"getcourse-browser-fixture"}'
aoa-course mcp call graph_neighbors '{"node_id":"lesson:starter:unlock-risk","run":"starter-fixture"}'
aoa-course mcp call freshness_report '{"run":"starter-fixture"}'
aoa-course mcp call evidence_report '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call refresh_plan '{"query":"rollback","run":"starter-fixture","mode":"hybrid"}'
aoa-course mcp call sync_status '{"sync_run":"browser-sync-fixture"}'
aoa-course mcp call sync_status '{"sync_run":"stepik-sync-fixture","platform":"stepik"}'
aoa-course mcp call live_preflight '{"platforms":["getcourse","stepik"]}'
aoa-course mcp call connected_source_plan '{"platforms":["getcourse","stepik"],"live_scope":"bounded","query":"course-specific question"}'
aoa-course mcp call connected_run_status '{"run":"connected-fixture-proof"}'
```

`semantic_search` follows the semantic index artifact for the requested run. If
that artifact was built with `http_json_v1`, the MCP route uses the same
operator-configured endpoint and token environment variable name for query
vectors; token values are read from the environment and are not written to the
artifact or tool result.

`ingest_status` is the read-only run readiness packet. It reports normalized
bundle counts, materialization receipt summaries, keyword/semantic index
metadata, graph node/edge counts, `agent_query_ready`, and next build/query
commands without reading private raw payloads into `structuredContent`.

`connector_readiness` is the read-only whole-connector route audit. It returns
`aoa_course_connector_readiness_v1` with install route files, storage roots,
source registry counts, selected run readiness, connected-source plan summary,
connected-run receipt status, MCP tool coverage, `operational_ready`,
`connected_live_ready`, and next commands. It is the first MCP packet an agent
should inspect when deciding whether to install, build starter artifacts,
connect sources, run fixture calibration, or move into gated live work.
On a fresh state, its `next_commands` can point to CLI `bootstrap fixture`,
which creates the local starter artifacts and default fixture connected-run
receipt before the agent returns to MCP queries.

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
  '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"live_preflight","arguments":{"platforms":["stepik"]}}}' \
  '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"connected_source_plan","arguments":{"platforms":["stepik"]}}}' \
  '{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"connected_run_status","arguments":{"run":"connected-fixture-proof"}}}' \
  '{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"connector_readiness","arguments":{"runs":["starter-fixture"],"platforms":["stepik"]}}}' \
  | aoa-course-connector-mcp
```

Tool calls return both text content and `structuredContent` so agents can keep
source-backed result objects, `score`/`rank_score`, `authority_tier`,
rank features, evidence chains, freshness/authority reports, refresh hints, and
graph packets without reparsing prose.

`evidence_report` is the compact agent handoff for a query. It returns the
evidence chain, freshness report, authority report, refresh report, and result
references with source URL, course path, fetched timestamp, freshness state,
authority tier, rank score, and `refresh_hint`. The hint always gives local
`build-index`, `build-semantic-index`, and `build-graph` rebuild commands. For
GetCourse, Skillspace, and Stepik it also points agents to
`preflight connected-plan` first, and only exposes live sync commands when the
result source matches the local source registry. Those sync commands are
`--source-id` scoped so refreshing one result does not accidentally refresh an
entire platform registry.

`refresh_plan` is the read-only MCP handoff for the full refresh loop. It
returns an `aoa_course_refresh_cycle_v1` packet with the current answer packet,
selected source-backed result, planned local rebuild/source commands, refresh
hint, optional connected-source plan, and `network_touched: false`. Network or
filesystem-mutating refresh execution stays on the CLI side through
`aoa-course refresh query --strategy fixture --execute` or the explicitly gated
live form with `--strategy live --execute --allow-network`.

`live_preflight` is read-only and returns `network_touched: false`. It lets an
agent inspect Stepik token presence, browser storage-state readiness, registered
source readiness, and next commands before attempting live discovery or sync.
It reports token/cookie/localStorage presence and counts only; secret values are
not included in `structuredContent`.

`connected_source_plan` is also read-only and returns `network_touched: false`.
It wraps the live preflight report into an operator handoff plan with exact
preflight-report, source sync, per-source smoke, and `calibration build`
commands. Agents should use it before connected live work so blocked sources,
missing auth state, missing Stepik token env, runtime report paths, and
calibration packet inputs are explicit before network-touching commands run.
For browser-session platforms, read `browser_auth_handoffs` first: it groups
GetCourse/Skillspace sources by host, reports missing or mismatched
storage-state, and provides the exact auth capture, redacted inspect, and
recheck commands needed to turn blocked sources into sync-ready sources.
When a shell-side operator handoff is needed, run the CLI equivalent with
`--write-runbook "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connected-source-runbook.md"`; MCP
keeps the structured plan in `structuredContent`, while the CLI writes the
Markdown checklist as runtime-only artifact state.
The default `live_scope` is `bounded`; set `live_scope: "full-course"` and
`include_step_sources: true` only when the operator intentionally wants the
larger Stepik full-course/source-enrichment route.

`connected_run_status` is the read-only MCP handoff after a CLI
`calibration connected-run`. It returns
`aoa_course_connected_calibration_run_status_v1` with status, stages,
artifact paths, `source_selection`, packet quality, privacy flags, failures,
and next steps from `connected_calibration_receipt.json`. It never executes
network work; missing receipts return `status: "missing"` so agents can ask for
the fixture or live connected-run command instead of guessing from the
filesystem.
