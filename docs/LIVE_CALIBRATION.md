# Live Calibration

Live calibration is the bridge between fixture-safe connector proof and
operator-connected course sources. It turns smoke and preflight reports into one
small calibration packet that an agent can inspect before choosing deeper live
sync, selector repair, ranking calibration, or eval-intake work.

The packet schema is `aoa_course_live_calibration_packet_v1`.

## Fixture-Safe Check

Run the local suite first. It uses safe GetCourse, Skillspace, and Stepik
fixtures and writes a calibration packet under `AOA_COURSE_ARTIFACT_ROOT`:

```bash
aoa-course eval live-calibration
```

This is repo-local support evidence only. `aoa-evals` keeps central verdict,
scoring, regression, and proof-doctrine authority.

## Connected-Source Route

Run `preflight live` before any connected smoke. Preflight is read-only and does
not touch the network.

For agents, start with the combined read-only plan:

```bash
aoa-course preflight connected-plan \
  --live-scope bounded \
  --query "course-specific question" \
  --write-runbook "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connected-source-runbook.md"
```

The `aoa_course_connected_source_plan_v1` packet embeds the live preflight
result and lists exact commands for preflight report capture, auth/source
unblocking, live sync, per-source smoke reports, and `calibration build`. It is
the safest first handoff when connected-source state is unknown. Its default
platform set covers GetCourse, Skillspace, and Stepik together, and its default
`bounded` scope keeps Stepik live sync/smoke under smoke limits. Pass
`--platform` only to narrow a diagnostic run; switch to `--live-scope
full-course --include-step-sources` only for an explicit operator-selected
full-course calibration.

For GetCourse and Skillspace, inspect `browser_auth_handoffs` before running
any live browser command. The handoff packet groups source readiness by host,
shows the storage-state file, and gives the auth capture, redacted inspect, and
recheck commands required before the plan will emit browser live sync/smoke
commands. The optional runbook is a Markdown rendering of the same redacted
packet plus execution stages; store it in `AOA_COURSE_ARTIFACT_ROOT` and keep it
out of Git.

For a one-command executable proof of the same contract, run the fixture-safe
connected calibration route:

```bash
aoa-course calibration connected-run --mode fixture --run connected-fixture-proof
aoa-course calibration status --run connected-fixture-proof
```

It writes an `aoa_course_connected_calibration_run_receipt_v1` under
`${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/<run>/connected/`,
plus smoke reports, a connected-source plan, a runbook, a calibration packet,
and a calibration intake report. Fixture mode does not touch the network.

After reviewing `preflight connected-plan` and confirming local auth/source
readiness, the same route can execute selected live sources only with an
explicit network gate:

```bash
aoa-course calibration connected-run \
  --mode live \
  --platform stepik \
  --allow-network \
  --live-scope bounded \
  --source-limit 1 \
  --run connected-stepik-live-calibration
```

Live connected-run receipts are runtime evidence and must stay out of Git.
For GetCourse and Skillspace live runs, `calibration connected-run` uses the
same default browser storage-state path checked by preflight,
`${AOA_COURSE_AUTH_ROOT:-.connector-state/auth}/<platform>/account.storage-state.json`,
unless `--state-file` is supplied.
The bounded public Stepik route has been field-smoked with this command shape:
the resulting local receipt and calibration packet were `ok`, contained answer
evidence and timestamps, and kept raw payloads and secret values out of the
packet. Treat that as route proof, not a guarantee that every authenticated or
full-course Stepik source behaves the same.

After any connected run, use `calibration status --run <run>` or MCP
`connected_run_status` to read the receipt summary without executing network
work. The `aoa_course_connected_calibration_run_status_v1` status packet
includes `source_selection`, stage summaries, packet quality, privacy flags,
failures, next steps, runtime artifact paths, and `query_handoff` entries for
the sync/smoke runs that already have local indexes, graphs, answer packets, and
CLI `query`/`answer` commands.

```bash
aoa-course preflight live --platform getcourse --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" > "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/getcourse-preflight.json"
aoa-course preflight live --platform stepik --stepik-token-env STEPIK_API_TOKEN > "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/stepik-preflight.json"
```

Then run bounded smoke commands against sources the connected account is allowed
to view. Redirect reports into runtime artifact storage, not into Git:

```bash
aoa-course smoke browser-live \
  --platform getcourse \
  --run getcourse-live-smoke \
  --catalog-url "https://school.example/teach/control/stream" \
  --course-url "https://school.example/teach/control/stream/view/id/201" \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --query "course-specific question" \
  > "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/getcourse-live-smoke.json"

aoa-course smoke stepik-live 67 \
  --run stepik-live-smoke \
  --query "course-specific question" \
  > "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/stepik-live-smoke.json"
```

Build the packet from the reports:

```bash
aoa-course calibration build \
  --run connected-live-calibration \
  --report "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/getcourse-live-smoke.json" \
  --report "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/stepik-live-smoke.json" \
  --preflight-report "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/getcourse-preflight.json" \
  --preflight-report "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/stepik-preflight.json"
```

`calibration build` writes
`${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/<run>/calibration/live_calibration_packet.json`.
Do not commit live packets, raw smoke reports, browser state, private snapshots,
tokens, cookies, raw API payloads, or course pages.

Turn a packet into a local repair/eval-intake plan:

```bash
aoa-course calibration intake \
  --run connected-live-calibration-intake \
  --packet "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/connected-live-calibration/calibration/live_calibration_packet.json"
```

`calibration intake` writes an `aoa_course_live_calibration_intake_v1` artifact at
`${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/<run>/calibration/live_calibration_intake.json`.
It classifies packet failures into repair lanes such as privacy guard,
caption/transcript collection, course/evidence extraction, retrieval quality,
or readiness preflight. It also suggests repo-local `evals/intake/*.md`
candidates, but those are pressure notes only; `aoa-evals` owns promotion,
scoring, regression meaning, and central verdicts.

## Packet Meaning

The packet summarizes report health without embedding raw private payloads:

- `platforms`, `source_modes`, `report_count`, and `preflight_count` show the
  covered adapter routes.
- `quality.transcript_count_total`, `quality.caption_sidecar_count_total`, and
  `quality.transcript_source_authority_counts` show whether browser smoke found
  visible transcript/caption text and caption sidecars.
- `quality.browser_reports_with_transcripts` shows how many browser smoke
  reports produced at least one canonical transcript object.
- `quality.caption_resource_error_count_total` must stay `0`; any non-zero
  value means a visible caption sidecar was present but could not be collected
  or parsed cleanly.
- `quality.answer_result_count_total` and
  `quality.answer_evidence_count_total` show whether answer checks found
  source-backed evidence.
- `quality.all_answered_reports_have_evidence` and
  `quality.all_answered_reports_have_timestamps` must stay true for useful
  connected-source handoff.
- `privacy.raw_paths_are_local_runtime_state` must stay true.
- `privacy.contains_raw_payloads` and `privacy.contains_secret_values` must
  stay false.

If a smoke report has no lessons, no evidence, no answer chain, caption-resource
errors, a missing privacy guard, or a secret-like marker, packet `status`
becomes `partial` and the `failures` list tells the next agent what to repair.
Run `calibration intake` against such packets before selector or query repairs
so the failure is routed to a concrete lane and fixture/eval follow-up.

## Next Work From A Packet

Use a successful packet to decide the next bounded field task:

- expand a live sync from smoke limits to an operator-selected full course;
- repair GetCourse or Skillspace selectors for real themes found in smoke;
- repair protected or unusual caption sidecar collection when
  `caption_resource_error_count_total` is non-zero;
- calibrate Stepik source enrichment and account discovery on authenticated
  courses;
- capture new local eval pressure when a recurring failure appears, without
  promoting local reports into central proof.
