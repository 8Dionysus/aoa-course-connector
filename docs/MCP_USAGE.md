# MCP surface

The independently runnable `aoa-course-connector-mcp` package exposes
connector-owned read, plan, and fixture-safe execution capabilities over
JSON-RPC stdio. Runtime deployment, registration, and lifecycle belong to
`abyss-stack`.

## Protocol

The server implements initialization, `tools/list`, and `tools/call`.
Successful calls return MCP `structuredContent`; errors remain structured and
do not print secret values. The supported protocol version is `2025-11-25`.
An unsupported protocol version returns a protocol error rather than silently
negotiating a different contract.

## Retrieval tools

Retrieval tools cover search, answer, lesson context, graph and evidence:

- `graph_neighbors` returns bounded course-graph context;
- `freshness_report` and `evidence_report` expose source-backed freshness,
  authority report, source URL, and evidence posture;
- `refresh_plan` returns a no-network refresh report and `refresh_hint`;
- `source_answer` uses one configured source;
- `sources_answer` preserves one evidence chain per selected source;
- matrix retrieval repeats the same source selection over several questions.

The tool layer does not change source authority or blend private evidence into a
new owner truth.

## Source and ingest tools

`list_sources` exposes a bounded local source registry view. It can omit source
refs while retaining ids and counts. `ingest_status` exposes normalized
counts, artifact metadata, source coverage, and `agent_query_ready` without
opening raw content.

Source selection uses `source_ids` and reports
`selected_source_ids`. Fixture/example sources remain marked
`fixture_or_example_source` with `operator_live_candidate: false`.

## Readiness and preflight

`live_preflight` and `connected_source_plan` are read-only and keep
`network_touched: false`. Plans preserve the full priority set unless the
caller selects a narrower scope. They retain `link_pattern`, `live_scope`,
`include_step_sources`, full-course posture, source bounds, auth candidates,
and a `connected_run_plan`.

`connector_readiness` returns
`aoa_course_connector_readiness_v1`, separating `operational_ready`,
`connected_live_ready`, semantic provider readiness, and local query
readiness. `semantic_provider_preflight` returns
`aoa_course_semantic_provider_preflight_v1` without calling the provider.

## Connection profiles

Profiles use `aoa_course_connection_profile_v1`.
`connection_profile_inspect` returns
`aoa_course_connection_profile_inspection_v1`.
`connection_profile_status` returns
`aoa_course_connection_profile_status_v1` and embedded
`aoa_course_connection_profile_readiness_v1`. Profile tools report token
presence and paths but never token values.

## Connected calibration

`connected_run` executes the fixture route by default; live work requires the
explicit network gate. `connected_run_status` reads the receipt.
`connected_run_query` returns
`aoa_course_connected_run_query_packet_v1` with source-backed answer, context,
and evidence.

The connected plan preserves `source_selection`, `query_plan`,
`repair_lanes`, `mcp_tool_call`, `mcp_command`, and `mcp_commands`.
The returned source packet contracts include
`aoa_course_source_answer_packet_v1` and
`aoa_course_sources_answer_packet_v1`.

## Authority and privacy

MCP is an access surface over connector logic. It does not own course sources,
eval verdicts, local stats, runtime registration, or deployment. Private raw
content stays in configured storage. Tool results may expose bounded evidence
and local artifact refs, but not cookies, browser state, token values, or other
secret values.

Exact invocation syntax belongs to the server tool schema and CLI parser. The
root `AGENTS.md`, tests, verifier, and CI own executable proof routes.
