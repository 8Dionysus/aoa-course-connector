# aoa-course-connector

`aoa-course-connector` is a GitHub-publishable AoA connector for turning
authorized course-platform access into local searchable course knowledge,
evidence packets, and course graphs.

The connector is not a downloader first. Its job is to let an agent answer
questions from course sources with lesson paths, snippets, freshness, and source
evidence.

## Offline Starter Proof

```bash
python scripts/validate_connector.py
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m aoa_course_connector.cli doctor
PYTHONPATH=src python -m aoa_course_connector.cli materialize fixture --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run starter-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "bootloader unlock rollback"
```

The starter path creates:

- normalized course objects from a safe fixture;
- a local keyword index;
- a course graph;
- an answer packet with source-backed evidence.

## Priority Platforms

| Platform | Route |
| --- | --- |
| GetCourse | Hard browser-session adapter for authorized course pages |
| Skillspace | Hard browser-session adapter for authorized course pages |
| Stepik | Clean API reference adapter target |
| Moodle / Canvas | Future clean LMS adapters |
| Teachable / Thinkific / Kajabi | Future platform adapters with API/browser-session split |

## Storage

Portable env roots:

```bash
export AOA_COURSE_DATA_ROOT=.connector-state/data
export AOA_COURSE_CACHE_ROOT=.connector-state/cache
export AOA_COURSE_AUTH_ROOT=.connector-state/auth
export AOA_COURSE_ARTIFACT_ROOT=.connector-state/artifacts
```

On this Abyss machine, the recommended external storage example is:

```bash
export AOA_COURSE_INSTANCE_ROOT=/srv/abyss-machine/storage/connectors/aoa-course-connector
```

That path is an example only, not a public default.

## MCP

The MCP server package is named `aoa-course-connector-mcp` and exposes the same
local artifacts used by the CLI:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli mcp tools
PYTHONPATH=src python -m aoa_course_connector.cli mcp call search '{"query":"rollback","run":"starter-fixture"}'
```

Runtime deployment in the full Abyss stack belongs in `abyss-stack`; this repo
keeps the source server independently installable.
