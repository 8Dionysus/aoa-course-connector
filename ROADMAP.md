# Roadmap

## Now

- Prove offline course fixture ingestion, index, graph, query, and MCP tool
  shape.
- Prove Stepik as the first clean API reference adapter.
- Prove GetCourse and Skillspace through shared browser-session snapshot
  adapters.
- Prove bounded GetCourse and Skillspace course-tree crawling from safe browser
  fixtures and optional live Playwright auth state.
- Document GetCourse and Skillspace hard-adapter strategy.
- Keep storage portable and safe for public clones.

## Next

- Expand GetCourse browser-session crawl from bounded course-index traversal to
  account-level training discovery, pagination, progress, and visible comments.
- Expand Skillspace browser-session crawl from bounded course-index traversal to
  account-level course discovery, pagination, progress, and visible comments.
- Expand Stepik adapter from bounded smoke slices to robust pagination and
  authenticated account scopes.
- Add semantic/vector index behind the stable keyword index contract.

## Later

- Add Moodle, Canvas, Teachable, Thinkific, Kajabi, and Coursera adapters.
- Add transcript/caption extraction where available.
- Add richer eval suites for answer quality, freshness, and evidence coverage.
