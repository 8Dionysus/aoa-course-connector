# Suites

Fixture-safe suites for local course connector behavior:

- `starter_course_answer_packets.json`
- `stepik_clean_api_answer_packets.json`
- `browser_hard_adapter_answer_packets.json`
- `browser_progress_comments_answer_packets.json`
- `browser_discovery_sources.json`
- `browser_sync_checkpoints.json`
- `browser_crawl_answer_packets.json`
- `answer_quality_packets.json`
- `freshness_ranking.json`
- `authority_ranking.json`

`answer-quality.suite.md` records the local suite note for the answer-quality
contract. It is connector-local support evidence only; central proof doctrine,
verdicts, scoring, regression meaning, and adoption stay with `aoa-evals`.

`freshness-ranking.suite.md` records the local suite note for freshness-aware
ordering when base relevance is tied.

`authority-ranking.suite.md` records the local suite note for authority-aware
ordering when base relevance is tied.
