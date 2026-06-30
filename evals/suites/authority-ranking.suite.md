---
schema_version: local_eval_suite_note_v1
owner_repo: aoa-course-connector
status: reviewed
authority_boundary: >-
  Local repo has no verdict authority, no scoring authority, no regression
  authority, and no proof doctrine authority. This suite is connector-local
  support evidence only; aoa-evals owns central proof doctrine and adoption.
suite_ref: evals/suites/authority_ranking.json
---

# Authority Ranking Suite

This local suite checks that, when base relevance is tied, higher-authority
course knowledge items rank above lower-authority items. It covers official
lesson text over learner comments and mentor comments over learner comments
while keeping base `score`, adjusted `rank_score`, rank features, and evidence
fields visible.
