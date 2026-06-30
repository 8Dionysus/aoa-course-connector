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
aoa-course bootstrap fixture --run starter-fixture --connected-run connected-calibration --platform stepik
aoa-course readiness --run starter-fixture
aoa-course preflight live
```

`bootstrap fixture` is the one-command local starter proof for a fresh install.
It creates storage roots, builds the starter normalized bundle, keyword index,
semantic index, graph, and a fixture connected-run receipt without network or
secrets.

`readiness` is the broad read-only route audit for the connector. It reports
install files, storage roots, local run/index/graph readiness, source registry
counts, MCP tool coverage, connected-source handoff status, and next commands.

`preflight live` is safe before credentials exist. It reports missing live auth
as a warning, does not touch the network, and gives the next commands for
Stepik tokens or browser storage-state capture.

When a Stepik source is registered as `public_api`, preflight can mark the
source sync route ready without a token. Token-gated Stepik sources and browser
sources still require matching local auth state before live sync is ready.

For this Abyss machine, use the external storage example when the corpus grows:

```bash
export AOA_COURSE_INSTANCE_ROOT=/srv/abyss-machine/storage/connectors/aoa-course-connector
```
