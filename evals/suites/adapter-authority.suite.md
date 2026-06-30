---
schema_version: local_eval_suite_note_v1
owner_repo: aoa-course-connector
status: reviewed
authority_boundary: >-
  Local repo has no verdict authority, no scoring authority, no regression
  authority, and no proof doctrine authority. This suite is connector-local
  support evidence only; aoa-evals owns central proof doctrine and adoption.
suite_ref: evals/suites/adapter_authority_metadata.json
---

# Adapter Authority Suite

This local suite checks that authority metadata produced by platform adapters
survives normalization, indexing, and source-backed query results.

It covers browser-session comment role metadata for GetCourse and Skillspace,
plus Stepik official API step and assignment metadata. It is fixture-safe and
does not touch live private accounts.
