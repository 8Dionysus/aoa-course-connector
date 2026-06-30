# MCP Usage

The server package name is `aoa-course-connector-mcp`.

Initial tools:

- `list_sources`
- `ingest_status`
- `sync_status`
- `search`
- `semantic_search`
- `hybrid_search`
- `lesson_context`
- `graph_neighbors`
- `freshness_report`

CLI smoke:

```bash
aoa-course mcp tools
aoa-course mcp call search '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call search '{"query":"rollback","run":"starter-fixture","mode":"hybrid"}'
aoa-course mcp call semantic_search '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call hybrid_search '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call lesson_context '{"query":"mentor anti-rollback vendor boot","run":"getcourse-browser-fixture"}'
aoa-course mcp call sync_status '{"sync_run":"browser-sync-fixture"}'
aoa-course mcp call sync_status '{"sync_run":"stepik-sync-fixture","platform":"stepik"}'
```

## JSON-RPC Stdio

The package entrypoint `aoa-course-connector-mcp` also speaks MCP-style
JSON-RPC over stdio. It supports:

- `initialize`
- `ping`
- `tools/list`
- `tools/call`
- `notifications/initialized`

Example smoke:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"local-agent","version":"0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search","arguments":{"query":"rollback","run":"starter-fixture"}}}' \
  | aoa-course-connector-mcp
```

Tool calls return both text content and `structuredContent` so agents can keep
source-backed result objects, evidence chains, freshness data, and graph packets
without reparsing prose.
