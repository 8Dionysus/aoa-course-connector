# AGENTS.md

Route card for owner-local statistical questions in `aoa-course-connector`.
Read the root `AGENTS.md` first.

## Applies To

Everything under `stats/`.

## Role

This directory owns bounded statistics over course-connector source and
materialization objects. Shared measurement grammar and cross-owner
composition remain owned by `aoa-stats`; eval verdicts remain owned by
`aoa-evals`, and private or live source truth remains in configured storage.

## Read Before Editing

1. Root `AGENTS.md`, `CHARTER.md`, and `BOUNDARIES.md`.
2. `connector/SOURCE_POLICY.md` and `connector/STORAGE_POLICY.md`.
3. The relevant adapter, fixture, schema, and owner evidence implementation.
4. `evals/AGENTS.md` when evidence is also consumed by an eval.
5. `stats/README.md`, `stats/port.manifest.json`, and the central contracts
   under `aoa-stats/stats/`.

## Boundaries

- The reference population contains only structural references declared by
  the three public starter fixtures: browser lessons plus Stepik sections,
  units, lessons, and steps.
- An object enters the numerator only when the corresponding adapter coverage
  packet reports it materialized from the same fixture inventory.
- A valid non-empty population with no materialized objects is an observed
  zero.
- Missing, malformed, empty, duplicate-platform, bounded, indeterminate, or
  non-exhausted source inventories are unknown, not zero or failure.
- The reference packet is weaker than fixtures, adapters, source coverage,
  normalized artifacts, executable audits, eval results, and live evidence.
- Structural materialization does not prove content adequacy, retrieval or
  answer quality, connector readiness, eval success, or live-source coverage.

## Validation

Inspect the fixtures, adapter coverage output, and packet first. The port
validator requires a compatible `aoa-stats` checkout through `AOA_STATS_ROOT`,
`.deps/aoa-stats`, or the workspace sibling route. Then run:

```bash
python scripts/validate_local_stats_port.py
python -m pytest -q tests/unit/test_local_stats_port.py
```

Use the root route for repository-wide validation.

## Closeout

Report the exact declared population, materialized numerator, manual positive
and negative cases, unknown handling, packet posture, central validation, and
repository validation.
