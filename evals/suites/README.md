# Suites

Fixture-safe suites for local course connector behavior:

- `starter_course_answer_packets.json`
- `stepik_clean_api_answer_packets.json`
- `browser_hard_adapter_answer_packets.json`
- `browser_progress_comments_answer_packets.json`
- `browser_transcripts_answer_packets.json`
- `browser_discovery_sources.json`
- `browser_sync_checkpoints.json`
- `browser_crawl_answer_packets.json`
- `retrieval_loop.json`
- `answer_quality_packets.json`
- `freshness_ranking.json`
- `place_ranking.json`
- `authority_ranking.json`
- `adapter_authority_metadata.json`
- `live_calibration_packet.json`
- `connected_portfolio.json`

`answer-quality.suite.md` records the local suite note for the answer-quality
contract. It is connector-local support evidence only; central proof doctrine,
verdicts, scoring, regression meaning, and adoption stay with `aoa-evals`.

`retrieval-loop.suite.md` records the local suite note for the complete
fixture-safe CLI/MCP retrieval loop across starter, GetCourse, Skillspace, and
Stepik runs.

`freshness-ranking.suite.md` records the local suite note for freshness-aware
ordering when base relevance is tied.

`place-ranking.suite.md` records the local suite note for native
hierarchy-aware ordering when text is shared across multiple course locations.

`authority-ranking.suite.md` records the local suite note for authority-aware
ordering when base relevance is tied.

`adapter-authority.suite.md` records the local suite note for adapter-derived
authority metadata preservation across normalized bundles and query packets.

`browser-transcripts.suite.md` records the local suite note for visible
browser-session transcript/caption extraction and retrieval.

`live-calibration.suite.md` records the local suite note for fixture-safe live
calibration packet construction from smoke and preflight reports.

`connected-portfolio.suite.md` records the local suite note for expected
cross-source Top-1 platform/path ranking and negative-query confidence.
