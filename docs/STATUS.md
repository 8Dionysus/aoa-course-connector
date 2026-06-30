# Status

## Current Proof

The repository has a working offline connector slice:

```bash
python scripts/validate_connector.py
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m aoa_course_connector.cli materialize fixture --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "bootloader unlock rollback" --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli mcp tools
```

This proves:

- canonical course fixture normalization;
- source-backed keyword search;
- graph construction for course/module/lesson/step/asset/topic/entity;
- answer packets with evidence chains and freshness timestamps;
- initial MCP tool surface;
- fresh-copy agent install route.
- Stepik clean API adapter through fixture, bounded live public API smoke,
  source-registry sync checkpoints, batched full-course materialization route,
  optional authenticated step-source enrichment, and client pagination helpers.
- GetCourse and Skillspace browser-session snapshot adapters through fixtures
  and optional Playwright live capture route.
- GetCourse and Skillspace account-level browser discovery into the local source
  registry through fixtures, snapshot input, optional Playwright live discovery,
  bounded live next-page following, and source-registry evals.
- GetCourse and Skillspace source-registry driven browser sync with
  `SyncCheckpoint` records, optional per-source index/graph builds, CLI status,
  MCP status, and evals.
- GetCourse and Skillspace bounded course-tree crawlers through fixtures,
  snapshot input, optional Playwright live traversal, and answer evals.
- GetCourse and Skillspace visible progress/status and comments through browser
  fixtures, answer packets, index docs, graph edges, MCP context, and evals.
- GetCourse and Skillspace paginated catalog fixture receipts with page-count
  and next-link evidence in discovery output.
- Browser-session parser heuristics for unannotated progress/status and compact
  visible comment/reply/discussion blocks.
- Browser-session smoke route for fixture, operator snapshot, and gated live
  calibration reports without printing private raw HTML.
- Stepik source-registry sync route with fixture checkpoint proof, optional
  index/graph builds, CLI status, MCP status, and eval coverage.
- Stepik fixture/live smoke report routes that combine source registration,
  source-registry sync, index/graph build, answer evidence, and privacy-safe
  local raw API path reporting.

## Remaining Goal Work

The next layer is live connected-source work:

- run gated live smoke with connected GetCourse and Skillspace accounts to
  calibrate real theme selectors and pagination behavior;
- broader live selector coverage for real GetCourse and Skillspace themes where
  progress and comment blocks use unusual markup;
- gated live full-course Stepik runs against operator-selected authenticated
  courses to calibrate real course size, permissions, and source enrichment;
- broader Stepik live smoke calibration against operator-selected authenticated
  courses and full-course source-registry runs;
- richer live smoke routes gated away from CI secrets.
