# Release 0.1.2 Reconciliation Ledger

This ledger covers the exact-provider corrective source-release boundary after
immutable `v0.1.1`. The human release narrative is in `CHANGELOG.md`; this
document accounts for the provider transition, release surfaces, and claim
limits without rewriting either prior release.

## 1. Boundary and identity

| Field | Value |
| --- | --- |
| Previous stable release | `v0.1.1` -> `73288a6de89782e4ec5c38d7e050a2ace2c1175c` |
| Provider correction commit | `91c919da227cf725ccf99d0195712c2c5fd8cf93` |
| Corrective target | `0.1.2` / `v0.1.2` |
| Release kind | GitHub source Release; no package artifact or assets |
| Release law | Manifest-driven sequential release with a lightweight tag, following the owner tradition |
| Reconciliation rule | Every provider, workflow, version, release, and non-claim surface is classified below |

The provider correction starts from the exact current `origin/main` and keeps
the immediately preceding stable release as the manifest baseline. The final
landed commit, merged PR, tag, and GitHub Release identity are recorded by the
execution report and postpublish handoff; this ledger does not invent those
future immutable identities before landing.

## 2. First-parent and merged-change reconciliation

| Source identity | Classification | Human meaning |
| --- | --- | --- |
| `91c919da227cf725ccf99d0195712c2c5fd8cf93` | changelog-worthy corrective source change | Aligns the Course release manifest, owner law, and validation workflow with the exact published `aoa-stats v0.2.1` provider commit. |
| Release-preparation carrier in the release PR | release-boundary material | Synchronizes `0.1.2` markers, canonical notes, the previous-release identity, and this ledger for the owner publication route. |

The release PR's final landed commit is the first-parent carrier for the
published release. The execution report records its exact post-merge SHA and
the complete `v0.1.1..v0.1.2` range. No unrelated active branch or sibling
repository is included.

## 3. File-level reconciliation

| Path | Classification | Reason and consumer-visible effect |
| --- | --- | --- |
| `release/release-manifest.json` | authored release identity | Moves the target to `0.1.2`, preserves `v0.1.1` as the previous stable release, and binds `aoa-stats v0.2.1` to `339ecb2d...`. |
| `.github/workflows/validate.yml` | authored validation contract | Checks out the exact published stats provider commit; the KAG action pin remains a separate helper identity. |
| `RELEASING.md` | authored owner law | Makes the current exact stable provider prerequisite explicit for future Course releases. |
| `pyproject.toml` | version-bearing source | Synchronizes package metadata to `0.1.2`. |
| `src/aoa_course_connector/__init__.py` | version-bearing source | Synchronizes the package initializer to `0.1.2`. |
| `src/aoa_course_connector/mcp/server.py` | version-bearing source | Synchronizes the MCP server version to `0.1.2`; protocol version is unchanged. |
| `CHANGELOG.md` | authored release narrative | Records the compatibility correction, migration posture, validation route, and bounded non-claims. |
| `docs/RELEASE_RECONCILIATION_0.1.2.md` | authored evidence ledger | Accounts for the provider transition and release-boundary surfaces. |
| `kag/indexes/index_family.manifest.json` and `kag/indexes/shards/` | generated owner-local projection | Refreshes the portable KAG family with the pinned owner generator after release-surface changes; it carries no new authored KAG meaning. |

No connector adapter, schema, local measurement contract, fixture, or
runtime/private storage surface is changed by this correction. The generated
KAG family is refreshed only as a deterministic projection of the changed
public source tree. The old `docs/RELEASE_RECONCILIATION_0.1.1.md` remains
historical and is not rewritten.

## 4. Exact provider-before-consumer evidence

| Provider | Tag | Commit | Role |
| --- | --- | --- | --- |
| `8Dionysus/aoa-kag` | `v0.5.0` | `813a7f69dc96ec031dad9b897a6991792cc48b7a` | Existing stable KAG provider, unchanged |
| `8Dionysus/aoa-stats` | `v0.2.1` | `339ecb2db22ac4552fa88756b650896ebbff5b56` | Current stable stats provider and exact workflow checkout |

The published stats tag resolves through its annotated tag object to the
commit above, and the provider Release is stable/non-draft/non-prerelease.
The local Course stats-port validator is run against a clean checkout of that
exact commit. A green validator establishes the declared stats-port contract;
it does not establish runtime health, eval verdicts, or consumer acceptance.

## 5. Release-worthiness and version judgment

The correction is patch-level under the Course owner law: it changes a public
provider compatibility/release-boundary declaration and its CI checkout from
an historical provider to the current exact stable provider, without changing
the connector method, schema, MCP protocol, storage contract, or runtime
behavior. It is not a new feature or a breaking migration. Publishing `v0.1.2`
is therefore justified only after the landed source, exact provider checks,
owner gate, and postpublish identity all pass.

## 6. Artifact, source, and non-claim boundary

The manifest declares `github_source_release`, `assets=[]`, and no package
registry publication. The connector artifact-class manifest keeps private
course pages, auth state, media, indexes, graphs, vectors, and full reports
external-only. No concrete public artifact candidate is part of this release
slice; artifact admission is consequently `unknown`/not claimed, not an
implicit `allow`, `warn`, `deny`, or `manual_review_required` verdict.

The source Release and its tag prove source publication identity only. They do
not prove artifact trust/admission, deployment, activation, runtime health,
live-source coverage, corpus completeness, central eval proof, shared stats
authority, terminal closure, master acceptance, or human acceptance.

## 7. Validation record

The final execution report binds the exact results for:

- owner connector validation;
- full unit and contract tests;
- CLI doctor and install-route verifier;
- local stats-port validation against `aoa-stats@339ecb2d...`;
- fixture-safe release scenarios and compile checks;
- pinned repo-local KAG sentinel, full parity, family contract, and
  compatibility assembly;
- exact provider/release manifest and workflow preflight;
- GitHub PR checks, merge, exact landed main synchronization, dry-run;
- immutable lightweight tag and GitHub Release publication; and
- postpublish tag/commit, latest marker, exact body, assets, and clean-main checks.

Skipped or non-applicable artifact/runtime/proof checks remain explicit in the
handoff and final report rather than being represented as green source checks.
