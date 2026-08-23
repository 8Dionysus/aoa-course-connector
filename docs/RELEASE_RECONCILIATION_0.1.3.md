# Release 0.1.3 Reconciliation Ledger

This ledger covers the exact-provider corrective source-release boundary after
immutable `v0.1.2`. The human release narrative is in `CHANGELOG.md`; this
document accounts for the provider transition, generated-family refresh, and
claim limits without rewriting either prior release.

## 1. Boundary and identity

| Field | Value |
| --- | --- |
| Previous stable release | `v0.1.2` -> `b22d83bfd000d28ee621b576d9a8caf1684a787b` |
| Corrective target | `0.1.3` / `v0.1.3` |
| Release kind | GitHub source Release; no package artifact or assets |
| Release law | Manifest-driven sequential release with a lightweight tag and immutable predecessor |
| Provider gate | Exact published KAG and stats tags/commits below; provider releases precede this consumer |
| Reconciliation rule | Authored source, generated projections, provider identity, artifact, runtime, proof, delivery, and acceptance remain separate claims |

The target is a patch successor because the public provider compatibility
contour and generated owner-local consumer family changed. The old
`docs/RELEASE_RECONCILIATION_0.1.2.md` remains historical and is not rewritten.

## 2. Exact provider-before-consumer evidence

| Provider | Tag | Exact commit | Role |
| --- | --- | --- | --- |
| `8Dionysus/aoa-kag` | `v0.5.2` | `8136d3eb629da28cea1206d13a8f1df52ee14739` | Final published KAG provider successor |
| `8Dionysus/aoa-stats` | `v0.2.2` | `f119805cda69b3edeb2a4c5e407368d70e68650d` | Final published stats provider successor and exact workflow checkout |

The KAG tag is annotated object
`251846823f49d18b06c32374b3434e6e11002e96` and the stats tag is annotated
object `119f434918e8218e43e977b2edec3e4feab6b493`; both peel to the exact
commits above and both provider main branches matched those commits during
revalidation.

The workflow action identity remains the separately accepted helper pin
`8Dionysus/aoa-kag/.github/actions/repo-local-kag-index@6a79e62c7d20b6b11406dee78f409ada4a51bb3f`. It is not substituted for the
KAG release tag or provider commit.

## 3. File-level reconciliation

| Path | Classification | Reason and consumer-visible effect |
| --- | --- | --- |
| `release/release-manifest.json` | authored release/provider identity | Moves the target to `0.1.3`, preserves `v0.1.2`, and binds exact KAG v0.5.2 and stats v0.2.2 commits. |
| `.github/workflows/validate.yml` | authored validation contract | Checks out exact stats v0.2.2; keeps the KAG workflow helper ref as a distinct identity. |
| `RELEASING.md` | authored owner law | Makes the exact current provider chain and action/provider distinction explicit for future releases. |
| `pyproject.toml` | version-bearing source | Synchronizes package metadata to `0.1.3`. |
| `src/aoa_course_connector/__init__.py` | version-bearing source | Synchronizes the package initializer to `0.1.3`. |
| `src/aoa_course_connector/mcp/server.py` | version-bearing source | Synchronizes the MCP server marker to `0.1.3`; protocol version is unchanged. |
| `CHANGELOG.md` | authored release narrative | Records the exact provider transition, migration posture, validation boundary, and non-claims. |
| `tests/unit/test_release_route.py` | owner contract test | Asserts current provider pins and preserves the separate KAG action identity. |
| `docs/RELEASE_RECONCILIATION_0.1.3.md` | authored evidence ledger | Accounts for the full release-boundary change and claim limits. |
| `kag/indexes/**` and budget receipts | generated owner-local projection | Rebuilt through the exact published KAG owner generator after authored source changes; no new authored KAG meaning. |

No connector adapter, schema, MCP protocol, private storage, credential,
course payload, media, or runtime/deployment surface is changed by this
correction.

## 4. Generated-family and canary boundary

The portable KAG family is a deterministic read model of the Course source
tree. It is regenerated through the `aoa-kag v0.5.2` builder and checked for
sentinel, full-family, budget, contract, and compatibility parity. Its output
does not replace authored Course source authority.

The exact stats checkout is immutable in the Course validation workflow. Any
compatibility canary that observes moving sibling inputs remains moving-lane
evidence and is not immutable release proof.

## 5. Release-worthiness and version judgment

The provider rebind changes public compatibility and validation contracts and
forces a generated consumer refresh. Under Course owner law this is a
patch-level release-bearing delta, not a no-release revalidation. The target
must be published only from the exact landed main commit after all required
owner gates pass.

## 6. Artifact, source, and non-claim boundary

The manifest declares `github_source_release`, `assets=[]`, and no package
registry publication. The Course artifact-class manifest does not admit a
concrete public Course artifact; its artifact result remains `none`/unknown
and not claimed. The separately recorded KAG owner-family artifact is
host-managed, signed, verified, and agent-admissible; release-consumer and
public-release intents remain `manual_review_required` until their production
trust-root requirements are supplied. No verdict is manually promoted.

The source Release and tag prove source publication identity only. They do not
prove artifact production admission for Course, deployment, activation,
runtime health, live-source coverage, corpus completeness, central eval proof,
shared stats authority, terminal closure, master acceptance, or human
acceptance.

## 7. Validation record

The final execution report binds exact results for:

- Course owner validator, full tests, CLI doctor, install-route verifier, and
  local stats-port validation against stats v0.2.2;
- fixture-safe release scenarios and compile checks;
- exact KAG provider checkout, generated-family sentinel/full parity, owner
  family contract, and compatibility route;
- exact manifest/workflow/provider/release preflight;
- GitHub PR checks, merge, exact landed-main synchronization, and dry-run;
- immutable lightweight tag and GitHub source Release publication; and
- postpublish tag/commit, latest marker, exact body, assets, and clean main.

Skipped or non-applicable artifact/runtime/proof checks remain explicit in the
execution report and handoff rather than being represented as green source
checks.
