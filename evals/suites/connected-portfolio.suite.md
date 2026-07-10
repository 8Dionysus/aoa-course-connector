---
schema_version: local_eval_suite_note_v1
owner_repo: aoa-course-connector
status: reviewed
authority_boundary: >-
  Local repo has no verdict authority, no scoring authority, no regression
  authority, and no proof doctrine authority. This suite is connector-local
  support evidence only; aoa-evals owns central proof doctrine and adoption.
suite_ref: evals/suites/connected_portfolio.json
---

# Connected Portfolio Suite

Fixture-safe local suite for cross-source retrieval quality. It checks that a
portfolio query selects the expected platform and native course path, ranks a
collision by query-to-path relevance instead of incomparable run-local scores,
preserves source, freshness, and evidence fields, and marks an unrelated query
as having no confident portfolio match.
