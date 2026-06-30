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

Platform glue must not leak into the core schema. GetCourse and Skillspace are
browser-session hard adapters. Stepik, Moodle, and Canvas are clean API reference
targets.
