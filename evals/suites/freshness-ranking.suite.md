---
schema_version: local_eval_suite_note_v1
owner_repo: aoa-course-connector
status: reviewed
authority_boundary: >-
  Local repo has no verdict authority, no scoring authority, no regression
  authority, and no proof doctrine authority. This suite is connector-local
  support evidence only; aoa-evals owns central proof doctrine and adoption.
suite_ref: evals/suites/freshness_ranking.json
---

# Freshness Ranking Suite

This local suite checks that, when two source-backed course knowledge items have
the same base relevance, the current item ranks above the stale item and the
answer packet exposes both the base `score` and freshness-adjusted
`rank_score`.
