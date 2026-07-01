# Install

```bash
git clone git@github.com:8Dionysus/aoa-course-connector.git
cd aoa-course-connector
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

For local state:

```bash
export AOA_COURSE_INSTANCE_ROOT="$PWD/.connector-state"
aoa-course init
aoa-course doctor
aoa-course bootstrap fixture --run starter-fixture --connected-run connected-calibration
aoa-course readiness --run starter-fixture
aoa-course goal audit --run starter-fixture --connected-run connected-calibration --require-ready-for-connection
aoa-course preflight live
```

`bootstrap fixture` is the one-command local starter proof for a fresh install.
It creates storage roots, builds the starter normalized bundle, keyword index,
semantic index, graph, and a GetCourse/Skillspace/Stepik fixture connected-run
receipt without network or secrets.

`readiness` is the broad read-only route audit for the connector. It reports
install files, storage roots, local run/index/graph readiness, source registry
counts, MCP tool coverage, connected-source handoff status,
semantic provider readiness, `connected_run_handoff`, and next commands. For
browser-session sources, `--link-pattern` keeps narrowed lesson/course globs
in that handoff. Use
`--max-lessons`, `--max-pages`, `--max-sources`, `--live-scope`, and
`--include-step-sources` when a readiness audit must preserve the exact
operator-selected connected-run breadth.

`preflight semantic-provider` is safe before an external embedding endpoint is
called. For `http_json_v1`, pass `--embedding-endpoint`, `--embedding-model`,
and `--embedding-token-env`; it reports endpoint/model/token-env readiness,
`token_env_present`, and `token_value_logged: false` without touching the
network.

`preflight live` is safe before credentials exist. It reports missing live auth
as a warning, does not touch the network, and gives the next commands for
Stepik tokens or browser storage-state capture.

`goal audit` is the read-only closeout handoff for a fresh agent. After
bootstrap it should report `ready_for_operator_connection: true` while keeping
`goal_complete: false` until live GetCourse, Skillspace, Stepik, and external
embedding calibration are performed with operator-owned access.
MCP `goal_audit` exposes the same DoD-oriented packet for agents that stay on
the MCP surface after install and readiness checks.

When a Stepik source is registered as `public_api`, preflight can mark the
source sync route ready without a token. Token-gated Stepik sources and browser
sources still require matching local auth state before live sync is ready.

For this Abyss machine, use the external storage example when the corpus grows:

```bash
export AOA_COURSE_INSTANCE_ROOT=/srv/abyss-machine/storage/connectors/aoa-course-connector
```
