# AOA-COURSE-D-0002: KAG provider and workflow action are separate ABIs

## Status

Accepted.

## Context

The current Course source consumes the published `aoa-kag@v0.5.0` provider body
at `f46f146cc79a26fa81ad0f400b9c5774df293e57`. Its repo-local KAG workflow
action is pinned to the immutable helper snapshot
`6a79e62c7d20b6b11406dee78f409ada4a51bb3f`. The two commits contain different
action bytes and therefore cannot be described as one identity.

## Decision

Keep the provider and executable action as separate, explicit immutable
identities. `release/release-manifest.json` and `.github/workflows/validate.yml`
must retain both exact refs and role labels. The source compatibility test must
assert that the refs are present and intentionally unequal. The action gate is
executable CI machinery; the provider commit is the content/source identity.

This is a current-source compatibility repair. It does not publish a
successor, move or rewrite `v0.1.0`, or turn the action run into artifact,
runtime, proof, delivery, closure, owner-acceptance, or human-acceptance
evidence.

## Executable compatibility evidence

- `tests/contract/test_kag_action_provider_identity.py` reads the authored
  manifest and workflow and asserts exact role/ref closure and inequality.
- The `repo-local-kag-index` action at `6a79...` is executed by the workflow
  against the current Course source; the provider source is independently
  validated at `f46...` through its owner route.
- The two immutable action snapshots were compared from their owner checkout;
  differing action bytes are preserved as provenance, not coerced into an
  allow.

## Consequences

Changing either identity requires a new exact compatibility review and a
future source entry. A provider artifact record cannot inherit action identity,
and an action execution receipt cannot become provider content evidence.
