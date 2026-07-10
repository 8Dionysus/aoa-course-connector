# Evals

This is a repo-local eval port. It can hold local suites, reports, and intake
pressure for `aoa-course-connector`, but it is not the central proof owner.
`aoa-evals` owns central verdicts, scoring, regression meaning, proof doctrine,
promotion, and central bundle adoption.

Local evals prove the starter retrieval loop:

`fixture -> normalize -> index -> graph -> answer packet with evidence`

Additional suites prove Stepik clean API fixtures, browser-session hard adapter
snapshots, browser account discovery into the source registry, and bounded
browser course-tree crawls. The browser progress/comments suite proves visible
course status and discussion notes become source-backed answer packets. The
browser-transcripts suite proves visible transcript/caption text becomes
canonical transcript objects and answer evidence. Sync suites prove that
registered browser sources produce checkpoints and rebuildable per-source
artifacts.

The answer-quality suite raises the bar above term presence: it checks top
result shape, source id, platform, path, snippets, freshness, and evidence
fields for fixture-safe runs.

The retrieval-loop suite prepares starter, GetCourse, Skillspace, and Stepik
fixture runs, builds keyword/semantic indexes and graphs, then checks CLI
answer, CLI lesson-context, MCP search, MCP lesson_context, and MCP
evidence_report in one fixture-safe route.

The connected-portfolio suite checks the layer that source-registry breadth
alone cannot prove: expected Top-1 source and native path across independent
connected runs, cross-source collision ordering, comparable portfolio rank
features, and low-confidence handling for unrelated questions. Operator
benchmarks stay in gitignored runtime artifact storage and use the same CLI
runner with `--suite ... --skip-prepare`.

The ingest-coverage suite checks structural source exhaustion and refresh
continuity rather than retrieval relevance. It requires explicit inventory,
limit and fetch-gap counts, preserved previous snapshots, stable canonical IDs,
and a bounded probe that must classify omitted lessons as truncation.

The corpus-integrity suite checks that the complete normalized searchable
inventory survives into keyword/semantic indexes, evidence, and graph records.
Its deterministic source-derived probes separate exact-document recall from
place-grounded course/lesson recall so duplicate technical metadata does not
hide either artifact loss or useful retrieval behavior.

The freshness-ranking suite checks the ordering-specific conflict case: when
current and stale course items have equal base relevance, the current item must
rank higher while the packet still exposes the base `score`, adjusted
`rank_score`, rank features, and evidence chain.

The place-ranking suite checks the native hierarchy case: when the same evidence
text appears across thread/comment/attachment surfaces, the requested course
location must win and the answer must carry the source path.

The authority-ranking suite checks another ordering-specific conflict case:
official lesson text and mentor comments must rank above learner comments when
base relevance is tied, while authority tier, rank score, rank features, and
evidence chain remain visible.

The adapter-authority suite checks that authority metadata produced by
browser-session and Stepik adapters survives normalization, indexing, and
source-backed query packets.

The live-calibration suite builds a fixture-safe
`aoa_course_live_calibration_packet_v1` from GetCourse, Skillspace, and Stepik
smoke/preflight reports. It proves the connected-source plan contract,
including browser transcript/caption health and caption-resource error counts,
without requiring credentials or storing private course payloads.
