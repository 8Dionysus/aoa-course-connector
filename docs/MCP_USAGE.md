# MCP Usage

The server package name is `aoa-course-connector-mcp`.

Initial tools:

- `list_sources`
- `ingest_status`
- `sync_status`
- `search`
- `lesson_context`
- `graph_neighbors`
- `freshness_report`

CLI smoke:

```bash
aoa-course mcp tools
aoa-course mcp call search '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call lesson_context '{"query":"mentor anti-rollback vendor boot","run":"getcourse-browser-fixture"}'
aoa-course mcp call sync_status '{"sync_run":"browser-sync-fixture"}'
aoa-course mcp call sync_status '{"sync_run":"stepik-sync-fixture","platform":"stepik"}'
```
