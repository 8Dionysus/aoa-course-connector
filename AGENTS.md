# AGENTS.md

Root route card for `aoa-course-connector`.

## Purpose

This repository owns the course-platform member of the AoA connector family:
source policy, course schemas, adapter contracts, authorized-session ingestion,
normalization, local indexes, graph packets, answer packets, MCP surface, and
local evals.

It is public method and code, not a course data dump.

## Boundaries

- Do not commit credentials, cookies, Playwright storage-state files, browser
  profiles, paid/private course pages, raw captures, indexes, graph databases,
  vectors, media downloads, or caches.
- GetCourse and Skillspace are priority hard adapters, but core logic must stay
  platform-neutral.
- Browser-session adapters may use only the connected user's legitimate access.
- Protected media should be represented with metadata, source links, available
  captions/transcripts, and evidence; do not make DRM bypass a connector goal.
- Runtime/MCP deployment belongs in `abyss-stack`; this repo owns connector
  logic and an independently runnable MCP server package.

## Validation

Run from the repository root:

```bash
python scripts/validate_connector.py
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m aoa_course_connector.cli doctor
PYTHONPATH=src python -m aoa_course_connector.cli bootstrap fixture --run starter-fixture --connected-run connected-calibration
PYTHONPATH=src python -m aoa_course_connector.cli readiness --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli materialize fixture --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --help
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "bootloader unlock rollback"
PYTHONPATH=src python -m aoa_course_connector.cli answer "bootloader rollback" --mode hybrid
PYTHONPATH=src python -m aoa_course_connector.cli refresh query "bootloader rollback" --run starter-fixture --mode hybrid
PYTHONPATH=src python -m aoa_course_connector.cli materialize stepik-fixture --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli materialize stepik-live --help
PYTHONPATH=src python -m aoa_course_connector.cli discover stepik-account --from-fixture --run stepik-account-discovery-fixture --register --source-limit 1
PYTHONPATH=src python -m aoa_course_connector.cli preflight live --platform stepik
PYTHONPATH=src python -m aoa_course_connector.cli discover stepik 67 --register --title "Stepik course 67"
PYTHONPATH=src python -m aoa_course_connector.cli sync stepik-fixture --run stepik-sync-fixture --build-artifacts
PYTHONPATH=src python -m aoa_course_connector.cli sync status --run stepik-sync-fixture --platform stepik
PYTHONPATH=src python -m aoa_course_connector.cli eval stepik-sync
PYTHONPATH=src python -m aoa_course_connector.cli smoke stepik-fixture 67 --run stepik-smoke-fixture --query "Stepik public API evidence"
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval clean-api
PYTHONPATH=src python -m aoa_course_connector.cli discover browser-fixture --platform getcourse --run getcourse-browser-discovery-fixture --register
PYTHONPATH=src python -m aoa_course_connector.cli discover browser-fixture --platform skillspace --run skillspace-browser-discovery-fixture --register
PYTHONPATH=src python -m aoa_course_connector.cli sources list
PYTHONPATH=src python -m aoa_course_connector.cli eval browser-discovery
PYTHONPATH=src python -m aoa_course_connector.cli sync browser-fixture --run browser-sync-fixture --build-artifacts
PYTHONPATH=src python -m aoa_course_connector.cli sync status --run browser-sync-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval browser-sync
PYTHONPATH=src python -m aoa_course_connector.cli mcp call sync_status '{"sync_run":"browser-sync-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli materialize browser-fixture --platform getcourse --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval answer-quality
PYTHONPATH=src python -m aoa_course_connector.cli answer "sidecar caption safe mode recovery logs" --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli materialize fixture --run freshness-ranking-fixture --fixture connector/fixtures/course/freshness_conflict_course.json
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run freshness-ranking-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run freshness-ranking-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval freshness-ranking
PYTHONPATH=src python -m aoa_course_connector.cli materialize fixture --run authority-ranking-fixture --fixture connector/fixtures/course/authority_conflict_course.json
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run authority-ranking-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-semantic-index --run authority-ranking-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval authority-ranking
PYTHONPATH=src python -m aoa_course_connector.cli materialize browser-fixture --platform skillspace --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "sidecar subtitle ANR tombstone evidence" --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval browser-hard-adapters
PYTHONPATH=src python -m aoa_course_connector.cli eval adapter-authority
PYTHONPATH=src python -m aoa_course_connector.cli eval browser-progress-comments
PYTHONPATH=src python -m aoa_course_connector.cli eval browser-transcripts
PYTHONPATH=src python -m aoa_course_connector.cli eval semantic-index
PYTHONPATH=src python -m aoa_course_connector.cli eval live-calibration
PYTHONPATH=src python -m aoa_course_connector.cli calibration status --run connected-calibration
PYTHONPATH=src python -m aoa_course_connector.cli calibration connected-run --mode fixture --run connected-fixture-proof
PYTHONPATH=src python -m aoa_course_connector.cli calibration status --run connected-fixture-proof
PYTHONPATH=src python -m aoa_course_connector.cli calibration build --help
PYTHONPATH=src python -m aoa_course_connector.cli calibration intake --packet "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/runs/live-calibration-fixture/calibration/live_calibration_packet.json" --run live-calibration-intake
PYTHONPATH=src python -m aoa_course_connector.cli auth plan-browser-state getcourse https://school.example
PYTHONPATH=src python -m aoa_course_connector.cli preflight live --platform getcourse
PYTHONPATH=src python -m aoa_course_connector.cli preflight connected-plan --live-scope bounded
PYTHONPATH=src python -m aoa_course_connector.cli preflight connected-plan --live-scope bounded --write-runbook "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connected-source-runbook.md"
PYTHONPATH=src python -m aoa_course_connector.cli mcp call live_preflight '{}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call connected_source_plan '{"live_scope":"bounded"}'
PYTHONPATH=src python -m aoa_course_connector.cli smoke browser-fixture --platform getcourse --run getcourse-browser-smoke-fixture
PYTHONPATH=src python -m aoa_course_connector.cli crawl browser-fixture --platform getcourse --run getcourse-browser-crawl-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run getcourse-browser-crawl-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run getcourse-browser-crawl-fixture
PYTHONPATH=src python -m aoa_course_connector.cli crawl browser-fixture --platform skillspace --run skillspace-browser-crawl-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run skillspace-browser-crawl-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run skillspace-browser-crawl-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval browser-crawl
PYTHONPATH=src python -m aoa_course_connector.cli mcp call graph_neighbors '{"node_id":"lesson:starter:unlock-risk","run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call freshness_report '{"run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call evidence_report '{"query":"rollback","run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call refresh_plan '{"query":"rollback","run":"starter-fixture","mode":"hybrid"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call connected_run_status '{"run":"connected-fixture-proof"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call connector_readiness '{"runs":["starter-fixture"]}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp call ingest_status '{"run":"starter-fixture"}'
PYTHONPATH=src python -m aoa_course_connector.cli mcp tools
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"local-agent","version":"0"}}}' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | PYTHONPATH=src python -m aoa_course_connector.mcp.server
```
