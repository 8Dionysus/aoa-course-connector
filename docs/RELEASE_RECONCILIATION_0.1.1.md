# Release 0.1.1 Reconciliation Ledger

This ledger covers the corrective source-release boundary after immutable
`v0.1.0`. The human release narrative is in `CHANGELOG.md`; this document is
the source-linked accounting for the accumulated post-release change and the
release-preparation surfaces that carry it forward.

## 1. Boundary and identity

| Field | Value |
| --- | --- |
| Previous stable release | `v0.1.0` -> `181abe0e11a96f45c4b465ef10282ff35480c3da` |
| Fresh current-main slice at repair intake | `4e6703fd9dd63a75670cade7342c7f5ceba126c2` |
| Current-main ancestry | `4e6703f` is a direct descendant of `181abe0` |
| Corrective target | `0.1.1` / `v0.1.1` |
| Release kind | GitHub source Release; no package artifact or assets |
| Reconciliation rule | Every commit, PR, generated change, or release surface is classified below |

The intake slice was recomputed from the exact immutable tag to the live
`origin/main`, not from the earlier release-prep branch. It contained one
first-parent commit and one merged PR. The release-preparation changes in this
branch are listed separately as owner release-boundary material; the final
landed commit, required checks, tag, and Release identity are recorded by the
execution report and handoff.

## 2. First-parent reconciliation of the post-v0.1.0 intake slice

| Ordinal | Commit | Date | Classification | Human meaning |
| ---: | --- | --- | --- | --- |
| 1 | `4e6703fd9dd63a75670cade7342c7f5ceba126c2` | 2026-08-22 | changelog-worthy corrective source change | Fixes the owner postpublish route's GitHub CLI field compatibility and refreshes its generated KAG consumers |

Count: 1 first-parent commit in `v0.1.0..4e6703f`.

## 3. Merged-PR reconciliation

| PR | Head | Merge commit | Classification | Scope |
| ---: | --- | --- | --- | --- |
| [#188](https://github.com/8Dionysus/aoa-course-connector/pull/188) | `c29f88d6e61ded113061387ecf2ec7adc4ddbffa` | `4e6703fd9dd63a75670cade7342c7f5ceba126c2` | changelog-worthy corrective patch | Replace unsupported `url` in `gh release list` output selection; refresh generated KAG family against the exact `v0.1.0` landed base |

Count: 1 merged PR in the intake slice. The PR head and merge identity were
checked against GitHub; the merge commit is the exact current `origin/main`
at repair intake.

## 4. Non-first-parent and side-commit reconciliation

There are no distinct non-first-parent commits in the final
`v0.1.0..4e6703f` range. The PR head above is the merged head, not an omitted
side history. No active or unrelated branch was folded into this release
boundary.

## 5. File-level reconciliation

The intake range changed five tracked files: 25 insertions and 24 deletions.

| Path | Classification | Reason and consumer-visible effect |
| --- | --- | --- |
| `scripts/release.py` | changelog-worthy authored source | The postpublish audit now asks GitHub CLI only for supported release-list fields, allowing the official owner route to inspect latest status on the installed CLI. |
| `kag/indexes/index_family.manifest.json` | generated consumer refresh | Portable KAG family manifest re-emits the source snapshot and digest after the release-tooling repair. |
| `kag/indexes/shards/event/7.jsonl` | generated consumer refresh | Adds the derived event edge for the repaired source snapshot. |
| `kag/indexes/shards/event/f.jsonl` | generated consumer refresh | Updates the derived repository snapshot change-set record. |
| `kag/indexes/shards/source/0.jsonl` | generated consumer refresh | Updates the derived source record and digest for `scripts/release.py`. |

Generated KAG files are not authored authority. They are included because
they are public, content-addressed consumers of the changed source and must
be synchronized and validated with it.

## 6. Corrective release-boundary material

The following owner surfaces carry the new reviewed `0.1.1` boundary and are
not silently folded into the old `0.1.0` ledger:

| Surface | Classification | Purpose |
| --- | --- | --- |
| `CHANGELOG.md` | authored release narrative | Human-first notes for the PR #188 correction and the sequential release route. |
| `docs/RELEASE_RECONCILIATION_0.1.1.md` | authored evidence ledger | This complete post-v0.1.0 and release-boundary accounting. |
| `release/release-manifest.json` | authored machine identity | Declares `0.1.1`, `v0.1.1`, the canonical ledger, provider pins, source-only publication, and immutable previous release. |
| `RELEASING.md` | authored owner law | Generalizes the one-shot first-release wording into sequential manifest-driven release law. |
| `scripts/release.py` | authored executable owner route | Uses manifest target identity and previous-release continuity checks for every subsequent release. |
| `pyproject.toml`, package initializer, MCP server | version-bearing source | Synchronize all public version markers to `0.1.1`; MCP protocol remains unchanged. |
| `tests/unit/test_release_route.py` | authored regression coverage | Keeps target identity, changelog extraction, and sequential manifest behavior tested without publication side effects. |
| `kag/**` generated family | derived consumer refresh | Rebuilt after authored release surfaces change and checked for deterministic parity. |

The release-preparation pull request is an owner release-boundary operation,
not an unaccounted product commit. Its exact final landed commit and CI
receipts are deliberately bound in the final execution report and handoff,
where the post-merge commit is known.

## 7. Provider-before-consumer and compatibility

The corrective release retains the exact stable provider prerequisites already
accepted by `v0.1.0`:

| Provider | Tag | Commit | Role |
| --- | --- | --- | --- |
| `8Dionysus/aoa-kag` | `v0.5.0` | `813a7f69dc96ec031dad9b897a6991792cc48b7a` | Published KAG provider release |
| `8Dionysus/aoa-stats` | `v0.2.0` | `dc608fd5de3fcaf0301f356c9efd52e2bdd350ce` | Published stats provider release |

The repo-local KAG workflow action remains the separately declared accepted
helper pin `6a79e62c7d20b6b11406dee78f409ada4a51bb3f`. The direct stats checkout
remains pinned to `dc608fd5de3fcaf0301f356c9efd52e2bdd350ce`. No provider
release or sibling repository is changed by this repair.

## 8. Trust, source, and non-claims

- The release is a public source Release with no package-registry publication,
  no release assets, and no signed package or bundle admission claim.
- The generated KAG family is a source-linked read model, not source authority,
  runtime state, or central proof.
- `abyss-stack` retains deployment, activation, health, observability, and
  rollback authority; `aoa-evals` retains central proof and verdict authority;
  `aoa-stats` retains shared measurement grammar and federation authority.
- The tag and GitHub Release prove source publication identity only. They do
  not prove runtime health, live-source coverage, eval success, artifact
  admission, or human acceptance.
- `v0.1.0` is historical stable evidence and remains immutable.
