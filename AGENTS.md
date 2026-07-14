# AGENTS.md

Root route card for `aoa-course-connector`.

## Purpose

This repository owns the course-platform member of the AoA connector family:
source policy, course schemas, adapter contracts, authorized-session ingestion,
normalization, local indexes, graph packets, answer packets, MCP surface, and
local evals. Its root `stats/` port owns bounded measurements over
connector-authored source and materialization evidence.

It is public method and code, not a course data dump.

## Boundaries

- Do not commit credentials, cookies, Playwright storage-state files, browser
  profiles, paid/private course pages, raw captures, indexes, graph databases,
  vectors, media downloads, or caches.
- GetCourse and Skillspace are priority hard adapters, but core logic must stay
  platform-neutral.
- Browser-session adapters may use only the connected user's legitimate access.
- Protected media should be represented with metadata, source links, available
  captions/transcripts, and evidence; do not make DRM bypass connector behavior.
- Runtime/MCP deployment belongs in `abyss-stack`; this repo owns connector
  logic and an independently runnable MCP server package.
- Shared statistical grammar and cross-owner composition belong to
  `aoa-stats`; local stats cannot claim eval, readiness, runtime, or source
  authority.

## Read Before Editing

1. `CHARTER.md`, `BOUNDARIES.md`, and the relevant design document under
   `docs/`.
2. `connector/SOURCE_POLICY.md` and `connector/STORAGE_POLICY.md` for source or
   storage changes.
3. The nearest nested `AGENTS.md` for `.connector-state/`, `evals/`, `kag/`, or
   `stats/`.
4. The executable owner: CLI parser and implementation, validator, test, or CI
   workflow relevant to the change.

## Validation

Exact command syntax belongs to the executable CLI, scripts, tests, and CI
workflow. Ordinary Markdown explains behavior and links to those owners; it
does not duplicate command catalogs.

Use this bounded operator route from the repository root:

```bash
python scripts/validate_connector.py
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m aoa_course_connector.cli doctor
python scripts/verify_agent_install_route.py --skip-pytest
AOA_STATS_ROOT=/path/to/aoa-stats python scripts/validate_local_stats_port.py
```

The CI workflow owns the exhaustive fixture/eval command matrix. The CLI
parser owns subcommand syntax; inspect it with `aoa-course --help` and the
relevant nested `--help` route rather than copying commands into docs.
