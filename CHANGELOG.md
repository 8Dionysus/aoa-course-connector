# Changelog

## 0.1.0 - Unreleased

- Initial public-ready repository skeleton.
- Added offline course fixture ingestion.
- Added keyword index, graph builder, answer packet, CLI, MCP skeleton, and
  validation route.
- Added Stepik clean API adapter with fixture and bounded live materialization.
- Added shared GetCourse/Skillspace browser-session snapshot adapters with
  fixture materialization and optional Playwright live capture.
- Added GetCourse/Skillspace browser-session account discovery into the local
  source registry with fixture, snapshot, live Playwright CLI routes, and evals.
- Added bounded GetCourse/Skillspace course-tree crawl routes with fixture,
  snapshot, live Playwright CLI commands, CI smoke checks, and answer evals.
- Hardened browser asset metadata extraction for unannotated file links and
  Stepik live step block resolution for richer source-backed text.
