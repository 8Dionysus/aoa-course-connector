# Runtime Contract

Runtime deployment belongs in `abyss-stack`, but this repository ships an
independently runnable package and MCP server entrypoint:

`aoa-course-connector-mcp`

The server reads local connector artifacts and does not require platform access
for query-only operation.

It supports JSON-RPC over stdio for `initialize`, `ping`, `tools/list`, and
`tools/call`. CLI compatibility helpers remain available through
`aoa-course mcp tools` and `aoa-course mcp call`.
