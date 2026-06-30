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

Live materialization stores raw API responses and normalized bundles under
`AOA_COURSE_DATA_ROOT`; generated indexes and graphs go under
`AOA_COURSE_ARTIFACT_ROOT`.

Set `STEPIK_API_TOKEN` when accessing data that requires an authenticated Stepik
account. Public course reads can work without it.

## Mapped API Shape

The adapter follows the Stepik API shape:

`course -> sections -> units -> lessons -> steps`

Only bounded live slices should be used for smoke checks. Full-course ingestion
should be an explicit operator action.
