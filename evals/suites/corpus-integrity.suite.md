---
schema_version: local_eval_suite_note_v1
owner_repo: aoa-course-connector
status: reviewed
authority_boundary: >-
  Local repo has no verdict authority, no scoring authority, no regression
  authority, and no proof doctrine authority. This suite is connector-local
  support evidence only; aoa-evals owns central proof doctrine and adoption.
suite_ref: evals/suites/corpus_integrity.json
---

# Corpus Integrity Suite

Fixture-safe proof that every canonical searchable object survives into the
keyword and semantic indexes, evidence attribution, and graph. It also rejects
dangling or duplicate graph records, broken postings and vectors, stale
artifact metadata, and retrieval misses from deterministic probes derived
independently from normalized source objects.
Exact-document recall remains visible, while the required relevance contract
accepts evidence from the same canonical course or lesson when technical
records are textually indistinguishable.
