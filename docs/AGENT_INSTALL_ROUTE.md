# Agent install route

This document describes the states and boundaries of a fresh agent install. It
does not duplicate the executable command sequence. The authoritative route is
implemented by `scripts/verify_agent_install_route.py`; the bounded operator
entrypoint is in the root `AGENTS.md`, and exact CLI syntax is owned by the
`aoa-course` parser.

## Offline baseline

A fresh install starts in isolated storage and must be able to create the
starter normalized bundle, keyword and semantic indexes, graph, and the default
GetCourse, Skillspace, and Stepik fixture connected-run receipt without network
access. The resulting readiness packet must distinguish local operational
readiness from connected-live readiness.

The executable verifier copies the repository to a temporary install-like
workspace and checks repository validation, compilation, doctor output,
fixture bootstrap, readiness, install-route eval, CLI retrieval, MCP stdio,
source-scoped retrieval, connected-run status and query packets, and the source
registry. Every fixture path must report `network_touched: false`.

## Connection profiles

Operator source refs, auth-state paths, live-scope choices, semantic-provider
settings, and selected course ids belong in a runtime
`aoa_course_connection_profile_v1` under `AOA_COURSE_ARTIFACT_ROOT`. Profiles
must never contain token values. Inspection and status surfaces expose a
redacted `aoa_course_connection_profile_status_v1` before a live run can be
considered.

Applying a profile mutates only the local source registry. A profile run plan
remains no-network until the operator explicitly authorizes the selected live
route. Browser sections prefer a host-matched imported Firefox state when one
is already available and otherwise expose capture and inspection routes.

## Source readiness

The connector preserves the distinction between:

- fixture or example sources, which prove installation and adapter shape;
- registered public sources, which may be usable without account credentials;
- authenticated sources, which require local token or browser-state evidence;
- selected ready subsets, which may proceed while unrelated blocked sources
  remain visible;
- live execution, which requires an explicit network gate.

Browser storage state is usable only for the matching source host. Stepik
public API course access and account-level discovery have different credential
requirements. Optional Stepik step-source enrichment keeps its own bounds and
does not silently widen a course sync.

## Retrieval and calibration

The fixture baseline proves that normalized content can be built into local
indexes and graphs and returned as source-backed answers, lesson context,
evidence, freshness, authority, and refresh information. Source-scoped and
cross-source queries retain separate evidence chains instead of collapsing
their authority.

Connected-source plans preserve selected source ids, platform scope, crawl and
pagination bounds, Stepik enrichment limits, query plan, portable artifact
paths, and both CLI and MCP representations. Fixture connected runs exercise
the same receipt and query shapes without network access. Live connected runs
are permitted only after the selected sources are ready and the network gate is
explicit.

Calibration intake converts a partial packet into local repair lanes and eval
intake candidates without taking proof authority from `aoa-evals`. Prior run
artifacts remain available so bounded refreshes are not mistaken for source
deletion.

## Completion evidence

The install route is complete only when the executable verifier succeeds from
its fresh temporary copy, all returned fixture packets remain no-network and
secret-free, direct CLI and MCP retrieval agree on source identity, and the
temporary workspace is removed. Narrative documentation is not evidence that
the route ran.
