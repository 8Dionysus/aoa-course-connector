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
aoa-course preflight live
```

`bootstrap fixture` is the one-command local starter proof for a fresh install.
It creates storage roots, builds the starter normalized bundle, keyword index,
semantic index, graph, and a GetCourse/Skillspace/Stepik fixture connected-run
receipt without network or secrets.

`readiness` is the broad read-only route audit for the connector. It reports
install files, storage roots, local run/index/graph readiness, source registry
counts, MCP tool coverage, connected-source plan status,
semantic provider readiness, `connected_run_plan`, and next commands. For
browser-session sources, `--link-pattern` keeps narrowed lesson/course globs
in that plan. Use
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

When the operator has real course URLs, state-file paths, Stepik course ids, or
semantic-provider settings, capture them as local runtime state:

```bash
aoa-course connect profile --name operator-live \
  --getcourse-url "https://school.example/teach/control/stream" \
  --skillspace-url "https://academy.example/course/demo" \
  --stepik-course-id 67 \
  --run connected-live-calibration \
  --semantic-provider http_json_v1 \
  --embedding-endpoint "https://embed.example/v1" \
  --embedding-model "course-embedding" \
  --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN \
  --write-runbook "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.runbook.md"
aoa-course connect inspect "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json"
aoa-course connect status "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json"
aoa-course connect apply "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json" \
  --write-runbook "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live-applied.runbook.md"
```

The profile is `aoa_course_connection_profile_v1`. It is a runtime artifact:
source refs may be operator-private, but token values are never written. Apply
only registers non-secret source refs in the local source registry; live sync
still requires the later explicit preflight/auth/network-gated commands.
`--write-runbook` writes the redacted operator checklist as Markdown beside the
profile JSON. `connect status` returns
`aoa_course_connection_profile_status_v1`, the compact go/no-go packet for
registered sources, browser auth readiness, connected-plan readiness, blockers,
and ready live connected-run commands.

When a Stepik source is registered as `public_api`, preflight can mark the
source sync route ready without a token. Token-gated Stepik sources and browser
sources still require matching local auth state before live sync is ready.

For this Abyss machine, use the external storage example when the corpus grows:

```bash
export AOA_COURSE_INSTANCE_ROOT=/srv/abyss-machine/storage/connectors/aoa-course-connector
```
