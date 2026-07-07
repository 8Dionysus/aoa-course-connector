---
schema_version: local_eval_suite_note_v1
owner_repo: aoa-course-connector
status: reviewed
authority_boundary: >-
  Local repo has no verdict authority, no scoring authority, no regression
  authority, and no proof doctrine authority. This suite is connector-local
  support evidence only; aoa-evals owns central proof doctrine and adoption.
suite_ref: evals/suites/retrieval_loop.json
---

# Retrieval Loop Suite

This local suite prepares safe fixture runs for starter, GetCourse,
Skillspace, and Stepik sources, then checks the complete agent retrieval loop:
CLI answer packet, CLI lesson context with graph neighborhoods, MCP search, MCP
lesson context, and MCP evidence report. It proves that an agent can retrieve
source-backed knowledge, graph context, freshness/authority evidence, and rerun
commands without live credentials.
