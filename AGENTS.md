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
PYTHONPATH=src python -m aoa_course_connector.cli materialize fixture --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "bootloader unlock rollback"
PYTHONPATH=src python -m aoa_course_connector.cli materialize stepik-fixture --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval clean-api
PYTHONPATH=src python -m aoa_course_connector.cli materialize browser-fixture --platform getcourse --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli materialize browser-fixture --platform skillspace --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli eval browser-hard-adapters
PYTHONPATH=src python -m aoa_course_connector.cli mcp tools
```
