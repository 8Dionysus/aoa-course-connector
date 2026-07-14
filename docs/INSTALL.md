# Installation boundary

The executable fresh-install proof lives in
`scripts/verify_agent_install_route.py`; the bounded operator route lives in
the root `AGENTS.md`. Exact package and CLI syntax belongs to those executable
owners and the parser.

## Requirements

The core package requires Python 3.11 or newer. Development installs add the
test runner. Browser-session capture is an optional extra because offline
fixtures, operator-provided snapshots, and Stepik public API routes do not
require Playwright.

## Storage

All mutable state resolves through either one instance root or the four explicit
`AOA_COURSE_DATA_ROOT`, `AOA_COURSE_CACHE_ROOT`,
`AOA_COURSE_AUTH_ROOT`, and `AOA_COURSE_ARTIFACT_ROOT` values. Defaults stay
under the ignored `.connector-state/` tree for local development.

Auth state, private raw pages, normalized private content, indexes, graphs,
vectors, media, and calibration packets are runtime state. They must never be
committed.

## Fresh-install proof

The verifier copies the repository into an isolated temporary workspace,
installs or uses the current package environment, runs the offline connector
route, checks CLI and MCP packets, and removes its state afterward. Its fixture
path must not touch the network.

A successful install proves method and local execution only. It does not prove
that operator credentials exist, that a live source is reachable, or that a
private course is complete.

## Live preparation

Live work begins only after storage roots, source refs, and host-matched auth
state are configured locally. Read-only preflight and connection-profile status
must expose blockers without printing secret values. Network access remains a
separate explicit authorization.

Runtime service installation and registration belong to `abyss-stack`, not
this repository.
