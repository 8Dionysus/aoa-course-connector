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
  --platform getcourse \
  --platform stepik \
  --live-scope bounded \
  --query "course-specific question" \
  --write-runbook "$AOA_COURSE_ARTIFACT_ROOT/connected-source-runbook.md"
```

The `aoa_course_connected_source_plan_v1` packet embeds the live preflight
result and lists exact commands for preflight report capture, auth/source
unblocking, live sync, per-source smoke reports, and `calibration build`. It is
the safest first handoff when connected-source state is unknown. Its default
`bounded` scope keeps Stepik live sync/smoke under smoke limits; switch to
`--live-scope full-course --include-step-sources` only for an explicit
operator-selected full-course calibration.

For GetCourse and Skillspace, inspect `browser_auth_handoffs` before running
any live browser command. The handoff packet groups source readiness by host,
shows the storage-state file, and gives the auth capture, redacted inspect, and
recheck commands required before the plan will emit browser live sync/smoke
commands. The optional runbook is a Markdown rendering of the same redacted
packet plus execution stages; store it in `AOA_COURSE_ARTIFACT_ROOT` and keep it
out of Git.

```bash
aoa-course preflight live --platform getcourse --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" > "$AOA_COURSE_ARTIFACT_ROOT/getcourse-preflight.json"
aoa-course preflight live --platform stepik --stepik-token-env STEPIK_API_TOKEN > "$AOA_COURSE_ARTIFACT_ROOT/stepik-preflight.json"
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
  > "$AOA_COURSE_ARTIFACT_ROOT/getcourse-live-smoke.json"

aoa-course smoke stepik-live 67 \
  --run stepik-live-smoke \
  --query "course-specific question" \
  > "$AOA_COURSE_ARTIFACT_ROOT/stepik-live-smoke.json"
```

Build the packet from the reports:

```bash
aoa-course calibration build \
  --run connected-live-calibration \
  --report "$AOA_COURSE_ARTIFACT_ROOT/getcourse-live-smoke.json" \
  --report "$AOA_COURSE_ARTIFACT_ROOT/stepik-live-smoke.json" \
  --preflight-report "$AOA_COURSE_ARTIFACT_ROOT/getcourse-preflight.json" \
  --preflight-report "$AOA_COURSE_ARTIFACT_ROOT/stepik-preflight.json"
```

`calibration build` writes
`$AOA_COURSE_ARTIFACT_ROOT/<run>/calibration/live_calibration_packet.json`.
Do not commit live packets, raw smoke reports, browser state, private snapshots,
tokens, cookies, raw API payloads, or course pages.

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
