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
aoa-course eval install-route
aoa-course eval preauth-readiness
aoa-course preflight live
```

`bootstrap fixture` is the one-command local starter proof for a fresh install.
It creates storage roots, builds the starter normalized bundle, keyword index,
semantic index, graph, and a GetCourse/Skillspace/Stepik fixture connected-run
receipt without network or secrets.
`eval install-route` is the executable fresh-agent proof for that install path.
It checks route docs, storage roots, bootstrap, readiness, CLI hybrid answer,
MCP answer, CLI/MCP source-scoped `sources_answer`, connected-run status,
query-plan readiness, and source registry setup with `network_touched: false`.
`eval preauth-readiness` is the executable pre-authorization proof. It prepares
the starter run, writes and applies an `operator-preauth` connection profile,
creates redacted profile and connected-source runbooks, checks CLI/MCP profile
status, live preflight, connected-source plan, and fixture `connected_run_query`,
then returns `aoa_course_eval_preauth_readiness_v1` with
`ready_until_authorization: true` and
`pause_boundary: authorization_required`.

`readiness` is the broad read-only route audit for the connector. It reports
install files, storage roots, local run/index/graph readiness, source registry
counts, MCP tool coverage, connected-source plan status,
semantic provider readiness, `connected_run_plan`, and next commands. For
browser-session sources, `--link-pattern` keeps narrowed lesson/course globs
in that plan. Use
`--max-lessons`, `--max-pages`, `--max-sources`, `--live-scope`, and
`--include-step-sources`, `--max-step-sources`, and `--step-source-timeout`
when a readiness audit must preserve the exact operator-selected connected-run
breadth.

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
  --include-step-sources \
  --max-step-sources all \
  --step-source-timeout 0.5 \
  --semantic-provider http_json_v1 \
  --embedding-endpoint "https://embed.example/v1" \
  --embedding-model "course-embedding" \
  --embedding-token-env AOA_COURSE_EMBEDDING_TOKEN \
  --write-runbook "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.runbook.md"
aoa-course connect inspect "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json"
aoa-course connect status "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json"
aoa-course connect apply "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json" \
  --write-runbook "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live-applied.runbook.md"
aoa-course connect run "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connections/operator-live.connection-profile.json" \
  --platform getcourse
```

The profile is `aoa_course_connection_profile_v1`. It is a runtime artifact:
source refs may be operator-private, but token values are never written. Apply
only registers non-secret source refs in the local source registry; live sync
still requires the later explicit preflight/auth/network-gated commands.
`--write-runbook` writes the redacted operator checklist as Markdown beside the
profile JSON. For browser-session sources, that checklist includes a
no-network `auth import-firefox-state` shortcut when the source URL has a host,
then the fresh-login `auth capture-browser-state` fallback and redacted
inspection command. `connect status` returns
`aoa_course_connection_profile_status_v1`, the compact go/no-go packet for
registered sources, browser auth readiness, connected-plan readiness, blockers,
and ready live connected-run commands. MCP `connection_profile_run_plan`
returns the same selected `aoa_course_connection_profile_run_plan_v1` without
network access for agents operating through MCP.
`connect run` reads the same profile and selected platform/source. Without
`--allow-network` it is a no-network plan receipt; with `--allow-network` it
executes the ready live connected-run for that selected profile route.

When a Stepik source is registered as `public_api`, preflight can mark the
source sync route ready without a token. Token-gated Stepik sources and browser
sources still require matching local auth state before live sync is ready.
Stepik account discovery also accepts local browser state. If the operator is
already logged in through Firefox, import the matching Stepik cookies first;
otherwise capture a fresh Playwright browser state.

```bash
aoa-course auth import-firefox-state stepik account --state-file "$AOA_COURSE_AUTH_ROOT/stepik/account.storage-state.json" --expect-origin-contains stepik.org
aoa-course discover stepik-account --state-file "$AOA_COURSE_AUTH_ROOT/stepik/account.storage-state.json" --register --max-pages 5
aoa-course sync stepik-live --state-file "$AOA_COURSE_AUTH_ROOT/stepik/account.storage-state.json" --source-id "source:stepik:..." --build-artifacts
```

For this Abyss machine, use the external storage example when the corpus grows:

```bash
export AOA_COURSE_INSTANCE_ROOT=/srv/abyss-machine/storage/connectors/aoa-course-connector
```
