# aoa-course-connector

`aoa-course-connector` turns course platforms that the operator is legitimately
allowed to access into normalized, source-backed course knowledge for agents.
It owns connector method, adapters, schemas, local retrieval logic, evidence
packets, an independently runnable MCP server, local evals, and bounded
owner-local statistics. It is not a repository for course corpora.

## Owner boundary

The repository owns:

- source policy and adapter contracts;
- GetCourse and Skillspace browser-session adapters;
- the Stepik clean API adapter;
- platform-neutral course, module, lesson, step, asset, transcript,
  assignment, discussion, topic, entity, and evidence objects;
- authorized discovery, ingestion, normalization, refresh, and continuity;
- local keyword and semantic indexes, course graphs, queries, and answers;
- source-backed CLI and MCP read surfaces;
- fixture-safe local evals and calibration intake;
- the root `stats/` port over connector-authored evidence.

Runtime deployment belongs to `abyss-stack`. Shared eval doctrine and proof
authority belong to `aoa-evals`. Shared statistical grammar and cross-owner
composition belong to `aoa-stats`. Private course truth remains in the
operator's configured storage.

## Source posture

GetCourse and Skillspace use one platform-neutral browser-session pipeline with
hard-adapter parsing differences. Stepik demonstrates the clean API path from
course to sections, units, lessons, and steps. Moodle and Canvas are reference
targets; Coursera, Teachable, Thinkific, and Kajabi remain future adapter
routes.

Every route preserves source identity, access mode, capture or update time,
freshness, authority, and evidence. Fixture and example sources prove method
only. They are never presented as operator-connected live sources.

## Data flow

1. Discovery identifies course entrypoints and may register local sources.
2. Ingestion captures an authorized or public source into external local
   storage.
3. Normalization produces platform-neutral course objects and evidence.
4. Index and graph builders create rebuildable derived artifacts.
5. Query surfaces return ranked results, lesson context, answer packets, and
   evidence chains.
6. Refresh and continuity surfaces preserve previous artifacts and distinguish
   source change from bounded or incomplete ingest.

Raw captures, private normalized content, indexes, vectors, graphs, browser
state, credentials, and runtime calibration packets stay outside Git under the
configured `AOA_COURSE_*` roots.

## Retrieval and evidence

Keyword retrieval uses a versioned BM25 contract. Semantic retrieval supports a
deterministic local baseline and an operator-configured HTTP embedding adapter.
Hybrid ranking preserves lexical, semantic, freshness, authority, and native
course-path contributions instead of hiding them in one opaque score.

Answer packets retain source URL, source id, fetched time, freshness state,
authority tier, rank features, refresh hints, and an evidence chain. Cross-source
answers keep per-source evidence rather than promoting a blended response into
source truth.

## Coverage, integrity, and readiness

Ingest coverage distinguishes complete, bounded, partial, and indeterminate
source inventories. Browser coverage records the visible lesson population
before limits; Stepik coverage compares referenced and fetched structural ids.
Identity continuity keeps removal under incomplete ingest inconclusive.

Corpus integrity independently compares normalized canonical objects with
keyword and semantic indexes, graph nodes and edges, vectors, postings, and
evidence. It is an executable audit, not a replacement for the source.

Readiness is split between local operational readiness and connected-live
readiness. A blocked live source does not erase a query-ready local source.
Network-touching work requires an explicit gate, and secret values never enter
packets or logs.

## Connection profiles

`aoa_course_connection_profile_v1` is a runtime artifact that carries source
refs, local auth-state paths, selected scope, and semantic-provider settings
without token values. `connection_profile_inspect` and
`connection_profile_status` expose redacted inspection and the
`aoa_course_connection_profile_status_v1` readiness summary, including
`ready_for_connected_run` and `network_touched` posture. Applying a profile
changes only the local source registry.

## Local stats port

The root `stats/` port currently measures one public reference question: what
fraction of structural course-object references declared by the canonical
GetCourse, Skillspace, and Stepik starter fixtures are materialized by their
adapters. The reference census is `9 / 9` at its named source revision.

This ratio does not prove content adequacy, live-source coverage, corpus
integrity, retrieval or answer quality, connector readiness, eval success, or
runtime health. Bounded or non-exhausted source inventories are unknown rather
than partial success.

## MCP and eval boundaries

The `aoa-course-connector-mcp` package exposes read-oriented source, retrieval,
evidence, readiness, calibration, and planning tools over JSON-RPC stdio. It
does not own runtime deployment or source truth.

Local eval suites exercise adapter and retrieval behavior. Their results remain
local evidence; `aoa-evals` retains scoring, promotion, verdict, and proof
doctrine. Calibration intake creates bounded repair and eval-intake candidates
without moving private payloads into Git.

## Executable routes

Exact commands are owned by the CLI parser, `scripts/validate_connector.py`,
`scripts/verify_agent_install_route.py`, tests, and the CI workflow. The root
`AGENTS.md` contains the bounded operator route. Ordinary Markdown documents
architecture and contracts without duplicating command catalogs.

## Further reading

- `BOUNDARIES.md` — public, local, runtime, eval, and stats ownership.
- `docs/ARCHITECTURE.md` — component topology.
- `docs/STATUS.md` — current durable capability state.
- `docs/CLI_USAGE.md` — CLI group and packet semantics.
- `docs/MCP_USAGE.md` — MCP tools and authority.
- `docs/AGENT_INSTALL_ROUTE.md` — fresh-install states and proof boundary.
- `stats/README.md` — local measurement definition and reference posture.
