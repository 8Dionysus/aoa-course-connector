# MCP Usage

The server package name is `aoa-course-connector-mcp`.

Initial tools:

- `list_sources`
- `ingest_status`
- `sync_status`
- `live_preflight`
- `connected_source_plan`
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
aoa-course mcp call lesson_context '{"query":"mentor anti-rollback vendor boot","run":"getcourse-browser-fixture"}'
aoa-course mcp call graph_neighbors '{"node_id":"lesson:starter:unlock-risk","run":"starter-fixture"}'
aoa-course mcp call freshness_report '{"run":"starter-fixture"}'
aoa-course mcp call evidence_report '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call sync_status '{"sync_run":"browser-sync-fixture"}'
aoa-course mcp call sync_status '{"sync_run":"stepik-sync-fixture","platform":"stepik"}'
aoa-course mcp call live_preflight '{"platforms":["getcourse","stepik"]}'
aoa-course mcp call connected_source_plan '{"platforms":["getcourse","stepik"],"query":"course-specific question"}'
```

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
  '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"live_preflight","arguments":{"platforms":["stepik"]}}}' \
  '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"connected_source_plan","arguments":{"platforms":["stepik"]}}}' \
  | aoa-course-connector-mcp
```

Tool calls return both text content and `structuredContent` so agents can keep
source-backed result objects, `score`/`rank_score`, `authority_tier`,
rank features, evidence chains, freshness/authority reports, and graph packets
without reparsing prose.

`evidence_report` is the compact agent handoff for a query. It returns the
evidence chain, freshness report, authority report, and result references with
source URL, course path, fetched timestamp, freshness state, authority tier, and
rank score.

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
