# aoa-course-connector local stats port

This directory exposes statistical questions whose domain meaning belongs to
the course connector. It uses the shared `aoa-stats` grammar without moving
course-source ownership, eval verdicts, private content, or runtime state into
the central stats organ.

## Current reference measurement

| Measurement | Question | Reference value |
| --- | --- | --- |
| `aoa-course-connector/public-fixture-structural-materialization-ratio` | What fraction of declared structural course-object references in the current public GetCourse, Skillspace, and Stepik starter fixtures are materialized by their adapters? | `9 / 9` at evidence revision `948315ca430d575e40ed49be788e7bfbab6a7602` |

The population is a census of unique platform-scoped structural references:
GetCourse and Skillspace lessons visible from their fixture course indexes,
plus Stepik sections, units, lessons, and steps referenced by its fixture API
tree. The numerator contains only corresponding objects reported as
materialized by the owner adapter coverage contract.

The ratio is composed as a ratio of sums while retaining platform and
structural-kind as bounded public dimensions. A valid complete population with
no materialized objects is an observed zero. A malformed or empty population,
duplicate or unsupported platform, bounded or indeterminate crawl, or source
inventory that was not exhausted is unknown.

## Evidence posture

The packet is a public, reference-only snapshot derived from the three
committed starter fixtures and their adapter-owned coverage logic. It does not
read configured storage, private course pages, live sources, raw captures, or
eval output. Terminal progress means only that this fixture census was fully
processed.

## Authority

The ratio reports fixture structural materialization only. It does not
establish content completeness or adequacy, live-source coverage, identity
continuity, normalized corpus integrity, index or graph coverage, retrieval or
answer quality, connector readiness, eval success, or runtime health.

## Surfaces

- `port.manifest.json` declares the owner-local question and measurement.
- `packets/public-fixture-structural-materialization-ratio.reference.json`
  records the evidence-linked reference observation.
- the three public starter fixtures own the declared reference population;
- the browser and Stepik coverage implementations own materialization counts;
- `aoa-stats` owns shared validation and cross-owner composition.
