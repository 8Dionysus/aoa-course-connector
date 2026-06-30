# AOA-COURSE-D-0001: Course Knowledge Connector, Not Downloader

## Status

Accepted.

## Decision

`aoa-course-connector` optimizes for course knowledge retrieval: normalized
lesson content, evidence, index, graph, and MCP query. Media download remains an
optional asset-resolution layer and cannot be the core success path.

## Consequences

- The connector remains useful for protected or streaming-only lessons.
- GetCourse and Skillspace can start with browser-session discovery.
- Clean API adapters such as Stepik, Moodle, and Canvas can validate the core
  model without scraper-shaped assumptions.
