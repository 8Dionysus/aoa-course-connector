# Releasing aoa-course-connector

This document is the owner-local release law for the independently
publishable Course connector. `abyss-stack` owns deployment and runtime
health; `aoa-evals` owns central proof and verdicts; `aoa-stats` owns shared
measurement grammar. This repository owns the source changelog, release
manifest, reconciliation ledger, and GitHub source Release.

## Release identity

The first release was version `0.1.0` with tag `v0.1.0`. For every release,
the target version, tag, canonical changelog, reconciliation ledger, provider
pins, and previous-release identity are declared by
`release/release-manifest.json`. The canonical release body is the dated
section named by that manifest, and the reconciliation ledger is the matching
`docs/RELEASE_RECONCILIATION_<version>.md` source surface.

The manifest-driven route is intentionally sequential: a stable target must
use the exact `v<version>` tag, identify the immediately preceding stable
release, prove that the previous tag still resolves to its declared commit,
and prove that the current source contains that commit. The target tag and
Release must be absent before publication. Existing releases are never moved,
deleted, or rewritten; a correction is a new reviewed release.

The version must agree in `pyproject.toml`, the package initializer, the MCP
server, and the changelog. A release is source-only: there is no PyPI or
other package-registry publication and no release asset unless a later owner
decision explicitly changes the manifest and release law.

## Provider-before-consumer gate

Before a Course release, resolve and verify the exact stable published tags
`aoa-kag@v0.5.0` and `aoa-stats@v0.2.1` against the commits in the release
manifest. The direct `aoa-stats` workflow checkout must use the exact
`v0.2.1` target commit. The repo-local KAG workflow action is a distinct
accepted helper pin from #186 and is checked independently.

## Required sequence

The release executor must run the owner validator, local stats-port
validator, install-route verifier, unit and contract tests, fixture-safe
release scenarios, compile check, provider checks, artifact/trust policy
review, and the owner-local strict preflight. The release-prep branch is
opened as a pull request from a clean worktree based on current `origin/main`.

After required GitHub checks pass, merge through GitHub and fast-forward a
clean local `main`. Re-run all owner gates and the route's dry-run on the
exact landed `main` commit. Only then create the manifest-declared
`v<version>` on that exact commit and create the GitHub Release from the
canonical changelog section. The postpublish route must verify tag-to-commit
identity, stable/latest marker, exact Release body, asset state, and clean
local main.

A failed gate is repaired on the release-prep branch and re-verified. A
published source release is not undone by deleting a tag; a correction uses a
new reviewed release. CI, a tag, a Release, or a delivery receipt does not
by itself prove runtime health, central proof, or human acceptance.

## Owner-local route

The executable route is `scripts/release.py`. Its `preflight`, `dry-run`,
`publish --confirm`, and `postpublish` actions are the authoritative syntax;
the route reads the target identity from the manifest and accepts an explicit
`--manifest` path for isolated checks. This document intentionally does not
duplicate shell command blocks. The publish action uses the GitHub API/CLI so
a local SSH configuration problem cannot silently cause a non-exact tag,
while GitHub remains the publication authority.
