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
- Stepik clean API adapter through fixture and bounded live public API smoke.

## Remaining Goal Work

The next layer is live connected-source work:

- GetCourse browser-session discovery;
- Skillspace browser-session discovery;
- broader Stepik sync coverage beyond bounded smoke slices;
- richer live smoke routes gated away from CI secrets.
