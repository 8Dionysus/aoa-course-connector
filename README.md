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

## Stepik Clean API Proof

The first clean API adapter is Stepik. CI uses a safe Stepik-shaped fixture:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli materialize stepik-fixture --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run stepik-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "Stepik public API evidence" --run stepik-fixture
```

For a bounded live public API smoke:

```bash
PYTHONPATH=src python -m aoa_course_connector.cli materialize stepik-live 67 --run stepik-live-smoke --max-sections 1 --max-units-per-section 1 --max-steps-per-lesson 2
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run stepik-live-smoke
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run stepik-live-smoke
PYTHONPATH=src python -m aoa_course_connector.cli query "Python course" --run stepik-live-smoke
```

## Browser-Session Hard Adapter Proof

GetCourse and Skillspace now have a shared browser-session snapshot route. CI
uses safe synthetic snapshots; live operator-owned pages can be captured with
the optional Playwright browser extra.

```bash
PYTHONPATH=src python -m aoa_course_connector.cli materialize browser-fixture --platform getcourse --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run getcourse-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "GetCourse bootloader rollback evidence" --run getcourse-browser-fixture

PYTHONPATH=src python -m aoa_course_connector.cli materialize browser-fixture --platform skillspace --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-index --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli build-graph --run skillspace-browser-fixture
PYTHONPATH=src python -m aoa_course_connector.cli answer "Skillspace logcat bugreport evidence" --run skillspace-browser-fixture
```

## Priority Platforms

| Platform | Route |
| --- | --- |
| GetCourse | Working browser-session snapshot adapter; live Playwright capture gated by local auth state |
| Skillspace | Working browser-session snapshot adapter; live Playwright capture gated by local auth state |
| Stepik | Working clean API reference adapter |
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
