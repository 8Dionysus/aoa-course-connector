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
the same base relevance, stable/current queries rank current evidence first,
fresh/latest queries expose fresh intent, and historical/old queries can rank
stale evidence first instead of being overwritten by recency. The answer packet
must expose base `score`, adjusted `rank_score`, temporal intent features, path
evidence, and freshness provenance.
