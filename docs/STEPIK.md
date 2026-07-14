# Stepik clean API adapter

Stepik is the first clean API reference adapter. Its structural path is:

`course -> sections -> units -> lessons -> steps`

The adapter keeps this platform shape at the edge and emits the same canonical
course objects and evidence contract used by browser-session sources.

## Fixture and live posture

The public fixture is synthetic and no-network. Live public course access may
use the `public_api` route without `STEPIK_API_TOKEN`; account discovery and
protected or user-specific data may require a token or browser-state cookie
route.

Preflight reports whether a source is sync-ready without exposing credentials.
Inactive or deleted enrollments are excluded from account discovery.

## Batching and scope

The client batches object retrieval through Stepik `ids[]` queries and follows
`meta.has_next` pagination where the API exposes it. A bounded route limits
sections, units, steps, pages, or sources. Full-course scope is an explicit
operator choice.

Optional step-source enrichment has its own attempt budget, timeout, fetched,
error, and skipped counts. It is reported separately from structural ingest
coverage so missing enrichment cannot rewrite the section/unit/lesson/step
population.

## Coverage and checkpoints

Coverage compares referenced and fetched section, unit, lesson, and step ids.
It records selected ids, limit truncation, fetch gaps, inventory exhaustion, and
complete, bounded, partial, or indeterminate state.

Sync writes per-source checkpoints and keeps prior normalized artifacts for
identity continuity. A bounded checkpoint cannot establish deletion.

## Retrieval and smoke

Materialized Stepik objects enter the same keyword and semantic indexes, graph,
answer, evidence, freshness, authority, and refresh surfaces as browser
sources. Smoke returns `aoa_course_stepik_smoke_report_v1` with registration,
sync, artifact, query, and privacy posture.

## Privacy

Tokens, cookies, raw live API payloads, private course content, normalized
corpora, indexes, graphs, vectors, and runtime reports remain outside Git.
Committed fixtures contain only public synthetic method evidence.
