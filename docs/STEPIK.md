# Stepik Adapter

Stepik is the first clean API reference adapter.

## Fixture Route

```bash
aoa-course materialize stepik-fixture --run stepik-fixture
aoa-course build-index --run stepik-fixture
aoa-course build-graph --run stepik-fixture
aoa-course answer "Stepik public API evidence" --run stepik-fixture
```

## Live Public API Route

```bash
aoa-course materialize stepik-live 67 --run stepik-live-smoke --max-sections 1 --max-units-per-section 1 --max-steps-per-lesson 2
aoa-course build-index --run stepik-live-smoke
aoa-course build-graph --run stepik-live-smoke
aoa-course query "Python course" --run stepik-live-smoke
```

The bounded route is the default smoke path. It keeps CI and quick operator
checks small while still proving the API, normalization, index, graph, and query
chain.

## Full-Course API Route

```bash
export STEPIK_API_TOKEN=...
aoa-course materialize stepik-live 67 --run stepik-full-course --full-course --batch-size 20 --include-step-sources
aoa-course build-index --run stepik-full-course
aoa-course build-graph --run stepik-full-course
aoa-course answer "course-specific question" --run stepik-full-course
```

`--full-course` disables `--max-sections`, `--max-units-per-section`, and
`--max-steps-per-lesson` smoke limits. Use it only for an explicit
operator-selected course.

`--batch-size` controls Stepik multi-ID reads through `ids[]`. The adapter keeps
the course order stable while reducing one-request-per-object traversal.

`--include-step-sources` asks Stepik for step source payloads and prefers their
source block text during normalization. Some accounts or courses may not expose
step source data; those failures are stored as `step_source_error` on the raw
step object instead of failing the whole course sync.

Live materialization stores raw API responses and normalized bundles under
`AOA_COURSE_DATA_ROOT`; generated indexes and graphs go under
`AOA_COURSE_ARTIFACT_ROOT`.

Set `STEPIK_API_TOKEN` when accessing data that requires an authenticated Stepik
account. Public course reads can work without it.

## Mapped API Shape

The adapter follows the Stepik API shape:

`course -> sections -> units -> lessons -> steps`

Object fanout uses `ids[]` batching. Collection helpers support `meta.has_next`
pagination for future routes that need account- or catalog-level Stepik
discovery.

Only bounded live slices should be used for smoke checks. Full-course ingestion
should be an explicit operator action.
