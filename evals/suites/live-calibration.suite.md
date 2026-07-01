---
schema_version: local_eval_suite_note_v1
owner_repo: aoa-course-connector
status: reviewed
authority_boundary: >-
  Local repo has no verdict authority, no scoring authority, no regression
  authority, and no proof doctrine authority. This suite is connector-local
  support evidence only; aoa-evals owns central proof doctrine and adoption.
suite_ref: evals/suites/live_calibration_packet.json
---

# Live Calibration Suite

This local suite checks the fixture-safe shape of live-calibration packets:
multiple platform smoke reports, source-backed answer evidence, timestamp
coverage, browser transcript/caption health, preflight input, and private-data
redaction boundaries. Browser smoke reports must also carry privacy-safe
snapshot audit summaries so selector/caption/comment/transcript/pagination
failures can be routed from the calibration packet.

It does not touch private accounts. Live operator runs can build the same
packet from saved smoke/preflight report JSON files.
