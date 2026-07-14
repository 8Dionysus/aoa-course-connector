# Browser-session adapters

GetCourse and Skillspace share one browser-session pipeline for authorized pages.
Platform glue stays in adapters; normalized course objects, evidence, indexes,
graphs, and queries remain platform-neutral.

## Modes

- **fixture** uses committed synthetic snapshots and never touches the network.
- **snapshot** uses an operator-provided local capture and remains no-network.
- **live** uses host-matched Playwright state and requires an explicit network
  gate.

These modes are not interchangeable evidence postures. A fixture or example
source is marked `fixture_or_example_source` and
`operator_live_candidate: false`.

## Discovery

Account discovery extracts course entrypoints from visible catalog pages.
Receipts preserve page count, next-page posture, discovered sources, and
pagination bounds without committing account pages.

Live pagination follows only catalog pagination links before applying a custom
course filter, so broad lesson patterns cannot register a next-page link as a
course. A page bound and source bound keep discovery finite.

## Course-tree crawl

Crawl starts from a course index and discovers visible lesson links with module
and title hints. The adapter records the full visible inventory before applying
the lesson bound. Selected pages are matched by canonical URL; an absent page is
represented as `discovered_not_fetched`, not as full lesson content.

Coverage reports available, selected, included, missing, and truncated lesson
counts. Truncation is bounded; a fetch gap is partial; missing inventory
information is indeterminate. The local stats port accepts only exhausted
fixture inventories for its full-population reference ratio.

## Materialization and sync

Materialization converts a fixture, snapshot, or live crawl into canonical
course objects and an evidence-linked receipt. Sync applies the same route to
registered browser-session sources and writes a checkpoint per source and run.

Source selection is explicit through `source_ids`. Connected plans repeat the
resolved scope in `connected_run_plan.source_ids`, so an unrelated blocked
source cannot silently widen or freeze a ready source refresh.

Identity continuity compares course, lesson, step, asset, transcript,
assignment, discussion, topic, entity, and evidence ids with the previous
checkpoint. A bounded refresh marks apparent removals inconclusive.

## Extracted knowledge

Accessible HTML may yield:

- course/module/lesson hierarchy and visible progress;
- lesson text, assets, and assignments;
- visible comments with author-role authority;
- visible transcript/caption blocks;
- caption sidecar text resolved from matching `resources[]` entries;
- source URLs, timestamps, selectors, freshness, and authority evidence.

Caption sidecar parsing supports bounded WebVTT and SRT text. The materialized
receipt exposes `transcript_count` and caption-resource errors. Empty or
unparseable sidecars remain errors rather than silent success.

Access-denied or prerequisite pages become explicit blocked lesson evidence.
Their boilerplate is not promoted as lesson content.

## Authorization and preflight

Playwright state is local under `AOA_COURSE_AUTH_ROOT`. Read-only preflight
checks state for each source host and reports per-host `state_file_candidates`
and `expected_origin_matched`. One school's state never authorizes another
school.

A ready preflight proves only that the selected live route may be attempted. It
does not perform discovery, crawl, sync, or smoke and does not replace the
explicit network gate.

## Smoke and snapshot audit

Smoke combines discovery or source selection, materialization, derived
artifacts, and a bounded source-backed query into one privacy-safe report.
Snapshot audit inspects discovery, lesson coverage, progress, comments,
transcript/caption extraction, caption sidecars, pagination, and repair lanes
without writing the snapshot to Git.

## Privacy

Never commit browser state, paid/private HTML, raw captures, source registries,
normalized private content, indexes, graphs, vectors, media, or calibration
packets. Reports may carry counts, bounded local paths, source identities, and
failure reasons but not cookies, tokens, or raw course text.
