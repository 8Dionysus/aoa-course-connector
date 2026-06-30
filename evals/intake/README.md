# Eval Intake

Local intake packets may record connector-specific eval pressure that is not
yet covered by a fixture-safe suite. Intake here is candidate/support evidence
only.

Live calibration packets can be converted into runtime intake plans with:

```bash
aoa-course calibration intake \
  --run connected-live-calibration-intake \
  --packet "$AOA_COURSE_ARTIFACT_ROOT/runs/connected-live-calibration/calibration/live_calibration_packet.json"
```

The generated `aoa_course_live_calibration_intake_v1` artifact stays under
`AOA_COURSE_ARTIFACT_ROOT`. It may suggest `evals/intake/*.md` candidate paths,
but adding a repo-local intake note still requires a human/agent review of the
redacted evidence and fixture plan.

`aoa-evals` owns central proof doctrine, verdicts, scoring, regression meaning,
promotion, and central bundle adoption. Do not treat an intake packet in this
repo as a central proof object.
