# Roadmap

## Now

- Prove offline course fixture ingestion, index, graph, query, and MCP tool
  shape.
- Prove Stepik as the first clean API reference adapter.
- Prove GetCourse and Skillspace through shared browser-session snapshot
  adapters.
- Prove GetCourse and Skillspace account-level source discovery into the local
  source registry from safe browser fixtures and optional live Playwright auth
  state.
- Prove source-registry driven sync checkpoints with optional per-source
  index/graph builds and MCP status.
- Prove bounded GetCourse and Skillspace course-tree crawling from safe browser
  fixtures and optional live Playwright auth state.
- Prove visible browser-session progress/status, comments, and paginated catalog
  receipt metadata from safe GetCourse and Skillspace fixtures.
- Prove bounded GetCourse and Skillspace live discovery pagination route and
  unannotated DOM heuristics for progress/status/comments.
- Prove fixture/snapshot/live browser smoke reports that combine discovery,
  ingestion, index/graph build, and optional answer evidence checks.
- Prove Stepik batched full-course API materialization with optional
  authenticated step-source enrichment.
- Document GetCourse and Skillspace hard-adapter strategy.
- Keep storage portable and safe for public clones.

## Next

- Run the gated live smoke route on connected GetCourse and Skillspace accounts to
  calibrate pagination and DOM heuristics against real themes.
- Broaden GetCourse and Skillspace live DOM selectors for unusual progress,
  status, comments, and discussion markup found by live smoke.
- Run gated live full-course Stepik sync on an operator-selected authenticated
  course and calibrate permission/source-enrichment behavior.
- Expand Stepik from course-id sync into source-registry driven discovery where
  official account scopes expose enough course catalog data.
- Add semantic/vector index behind the stable keyword index contract.

## Later

- Add Moodle, Canvas, Teachable, Thinkific, Kajabi, and Coursera adapters.
- Add transcript/caption extraction where available.
- Add richer eval suites for answer quality, freshness, and evidence coverage.
