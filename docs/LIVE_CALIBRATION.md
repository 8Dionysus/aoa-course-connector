# Live calibration boundary

Live calibration connects operator-authorized source evidence to bounded local
repair and eval-intake decisions. It does not make private source data public,
and it does not own central proof.

## Packet topology

The read-only planner emits `aoa_course_connected_source_plan_v1`. It contains
source readiness, `source_selection`, `execution_options`, auth candidates,
portable artifact routes, `query_plan`, and a `connected_run_plan`. The same
plan has CLI and MCP representations, including `mcp_commands` and the
structured `connected_source_plan` result.

A connected execution emits
`aoa_course_connected_calibration_run_receipt_v1`. Status inspection emits
`aoa_course_connected_calibration_run_status_v1` through
`connected_run_status`. Source-backed follow-up
retrieval emits `aoa_course_connected_run_query_packet_v1` through
`connected_run_query`, retaining answer, `lesson_context`,
`evidence_report`, freshness, authority, and graph context.

Calibration summary emits `aoa_course_live_calibration_packet_v1`. Intake
emits `aoa_course_live_calibration_intake_v1` and bounded `repair_lanes`.
These packets remain evidence, not verdicts.

## Fixture before live

Fixture calibration exercises GetCourse, Skillspace, and Stepik source
selection, sync, smoke, packet build, intake, status, and query shapes with
`network_touched: false`. It is the first proof because it can be repeated
without credentials or private content.

Live execution is a separate state. It requires selected-source readiness and
an explicit network gate. Full-course Stepik scope and optional step-source
enrichment are deliberate expansions, not defaults.

## Browser authorization

Browser sources require local host-matched state such as
`account.storage-state.json`. The plan reports per-host import, capture, and
inspection candidates without embedding cookie values. A ready subset may
proceed while unrelated blocked sources remain visible.

## Runtime artifacts

Connected receipts live below
`${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/<run>/connected/`.
Calibration packets live below
`${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/<run>/calibration/live_calibration_packet.json`.
These are local runtime paths, not repository artifacts.

Packets carry `raw_paths_are_local_runtime_state` and
`contains_secret_values` privacy assertions. They may summarize platform,
source mode, stage status, counts, and bounded paths, but they do not contain
cookies, tokens, raw API payloads, or course pages. Do not commit them.

## Transcript and caption health

Browser summaries preserve `transcript_count_total`,
`caption_sidecar_count_total`, `caption_resource_error_count_total`, and
`browser_reports_with_transcripts`. A missing or unparseable sidecar remains a
repair signal. Counts do not replace source evidence or answer quality.

## Repair lanes

A partial connected run keeps its successful and failed stages separate.
`repair_lanes` classify network gate, source authorization, selected-source
scope, sync, smoke/selector, artifact, answer, or intake pressure. They carry
minimal local follow-up and safe evidence requirements.

Calibration intake may propose a fixture or local eval candidate. Scoring,
promotion, verdict, and proof doctrine remain owned by `aoa-evals`.
