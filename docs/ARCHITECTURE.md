# Architecture

`aoa-course-connector` is organized around ports and adapters:

- `core`: canonical course-domain objects.
- `adapters`: platform-specific collection contracts.
- `auth`: browser-session, API token, OAuth, and offline-export auth routes.
- `ingest`: discovery/materialization orchestration.
- `normalize`: conversion into canonical course bundles.
- `evidence`: source URLs, timestamps, selectors, and provenance.
- `storage`: portable local roots.
- `index`: local search artifacts.
- `graph`: course/entity relation graph.
- `query`: search and answer packets.
- `mcp`: agent-facing tool surface.
- `stats`: reference-only owner measurements over public source and
  materialization evidence.

Platform glue must not leak into the core schema. GetCourse and Skillspace are
browser-session hard adapters. Stepik, Moodle, and Canvas are clean API/LMS
reference targets. Coursera, Teachable, Thinkific, and Kajabi are future
platform adapters and should enter through the same source registry, auth,
normalization, evidence, index, graph, query, and MCP ports rather than adding
platform-shaped shortcuts to the core model. Treat them as future platform
routes until working adapter implementations land.

The root `stats/` port asks a narrower question than ingest coverage or corpus
integrity: what fraction of structural references declared by the three public
starter fixtures are materialized by the corresponding adapters at one source
revision. It reuses adapter-owned coverage evidence and the central
`aoa-stats` grammar. It does not own source completeness, normalized artifacts,
eval verdicts, readiness, private runtime state, or MCP deployment.
