# Agent Install Route

1. Clone the repository.
1. Create a Python 3.11+ environment.
1. Install `.[dev]` for tests and CLI smoke checks.
1. Configure `AOA_COURSE_*` roots or `AOA_COURSE_INSTANCE_ROOT`.
1. Run `aoa-course doctor`.
1. Run `aoa-course bootstrap fixture --run starter-fixture --connected-run connected-calibration`
   to create the local starter bundle, keyword/semantic indexes, graph, and
   default GetCourse/Skillspace/Stepik fixture connected-run receipt without
   network access.
1. Run `aoa-course readiness --run starter-fixture` to get the read-only
   install/source/run/MCP audit and its next commands.
1. Run `aoa-course eval install-route` to prove the fresh-agent route end to
   end: docs, storage, bootstrap, readiness, CLI answer, MCP answer,
   connected-run status, query-plan entries, `connected_run_query` retrieval,
   and source registry without touching the network.
1. Run `aoa-course eval preauth-readiness` to prove the repository is ready up
   to the operator authorization boundary. The packet is
   `aoa_course_eval_preauth_readiness_v1`; it must return
   `ready_until_authorization: true`, `pause_boundary:
   authorization_required`, `network_touched: false`, concrete
   `authorization_handoff.next_commands`, redacted profile/runbook artifacts,
   and CLI/MCP checks for profile status, live preflight, connected-source
   plan, and fixture `connected_run_query`.
1. For the full public-repo verifier, run
   `python scripts/verify_agent_install_route.py --skip-pytest`. It copies the
   repository to a temporary install-like workspace, executes the offline route,
   checks MCP stdio, and requires direct MCP `answer` plus fixture-safe MCP
   `connected_run` and `connected_run_query` packets.
1. When operator source refs are available, run `aoa-course connect profile`
    with real GetCourse/Skillspace URLs, Stepik course ids, state-file paths,
    and semantic-provider settings, then run `connect inspect` and `connect
    apply`. The profile is `aoa_course_connection_profile_v1`; it is runtime
    artifact state under `AOA_COURSE_ARTIFACT_ROOT`, does not store token
    values, and `apply` mutates only the local source registry. MCP agents can
    inspect it through `connection_profile_inspect`. Use `--write-runbook` to
    write the same redacted source/auth/connected-plan/semantic checklist as
    Markdown beside the profile JSON. Run `connect status` or MCP
    `connection_profile_status` to get the compact
    `aoa_course_connection_profile_status_v1` go/no-go packet before any
    `calibration connected-run --mode live --allow-network` command. Use
    `connect run <profile> --platform <platform>` for the no-network executable
    profile plan, then add `--allow-network` only after the selected
    platform/source is ready.
1. Run the offline starter proof.
1. Run `preflight semantic-provider --run starter-fixture --require-ready`,
   then build the semantic index with `build-semantic-index` and run at least
   one `--mode hybrid` answer to prove the vector contract. For
   `http_json_v1`, run the same preflight with `--embedding-endpoint`,
   `--embedding-model`, and `--embedding-token-env`; it must report
   `token_env_present` without printing the token value before the first
   network-touching semantic build.
1. Register a Stepik course with `discover stepik 67 --register`, then run
   `sync stepik-fixture --source-id "<registered-source-id>" --build-artifacts`
   to prove source-scoped clean API checkpoints without network access.
1. Run `discover stepik-account --from-fixture --register --source-limit 1` to
   prove connected-account course discovery can write Stepik sources without
   live credentials.
1. Run `preflight live --platform stepik` to prove the live readiness report
    is safe and read-only even before an operator provides `STEPIK_API_TOKEN`.
    Registered `public_api` Stepik sources can be sync-ready without a token;
    account discovery and token-gated sources still require the token.
1. Run `smoke stepik-fixture 67` to prove the combined clean API registration,
   sync, keyword/semantic/graph, answer, and privacy-safe report route.
1. Run browser fixture discovery with `--register` to prove the local source
   registry route.
1. After starter, Stepik fixture, and GetCourse browser fixture artifacts are
    built, run `eval answer-quality` to prove top-result path, source id,
    freshness, snippet, and evidence-field quality.
1. Run MCP calls for `connector_readiness`, `connection_profile_inspect`,
    `connection_profile_status`, `connection_profile_run_plan`,
    `semantic_provider_preflight`, `connected_run`, `graph_neighbors`, `freshness_report`,
    `answer`, `evidence_report`, and `refresh_plan` against `starter-fixture` to prove
    agents can inspect connector readiness, profile readiness, selected
    profile run plans, execute the fixture connected route, graph neighborhoods, full answer packets, source
    evidence/freshness, and plan a refresh cycle
    without shelling into lower-level CLI internals.
1. After a registry-backed Stepik fixture sync, run `refresh query
    "Stepik public API evidence" --run "<checkpoint-run-id>" --mode hybrid
    --strategy fixture --execute` to prove the agent refresh loop can sync,
    select the new checkpoint run, rebuild indexes/graphs, and re-answer from
    refreshed evidence without live credentials.
1. Run the freshness conflict fixture and `eval freshness-ranking` to prove
    current material ranks above stale material when base relevance is tied.
1. Run the authority conflict fixture and `eval authority-ranking` to prove
    official lessons and mentor comments rank above learner comments when base
    relevance is tied.
1. After Stepik, GetCourse, and Skillspace fixture indexes are built, run
    `eval adapter-authority` to prove adapter-derived authority metadata reaches
    normalized objects and query packets.
1. Run `eval browser-transcripts` to prove visible GetCourse/Skillspace
    transcript and caption text becomes canonical transcript objects and
    source-backed answer evidence.
1. Run `eval live-calibration` to prove the fixture-safe calibration packet for
    GetCourse, Skillspace, and Stepik smoke reports before collecting connected
    account reports.
1. Run `calibration connected-run --mode fixture --run connected-fixture-proof`
    to prove source-registry sync, smoke reports, connected plan/runbook,
    calibration packet, intake, and one connected run receipt without touching
    live sources.
1. Run `calibration query --run connected-fixture-proof --kind smoke` or MCP
    `connected_run_query` to prove the connected receipt produces source-backed
    answer, lesson context, evidence report, freshness, authority, and graph
    context packets with `network_touched: false`.
1. Run `calibration query-matrix --run connected-fixture-proof --kind smoke
    --query ... --query ...` or MCP `connected_run_query_matrix` to prove the
    same connected receipt can answer several course-specific questions from
    local indexes and graphs without repeating live source access.
1. Before live browser sources, run `auth plan-browser-state`, capture the
    local Playwright state with `auth capture-browser-state`, and verify it with
    `auth inspect-browser-state`. The plan/capture commands should carry
    `--expect-origin-contains`; the capture receipt must show
    `expected_origin_matched: true` before discovery or sync.
1. Run `preflight live --platform getcourse` or
    `preflight live --platform skillspace` to inspect source registry and
    redacted browser-state readiness before live discovery or sync.
1. Confirm browser preflight marks only sources whose host matches the saved
    storage state as sync-ready.
1. Run `preflight connected-plan --write-runbook
    "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connected-source-runbook.md"`
    to produce the redacted setup/sync/smoke/calibration plan with portable
    runtime artifact paths and a `connected_run_plan`.
    If top-level status is `partial`, still inspect `connected_run_plan`: a
    `ready` plan with `scope: ready_subset` is an executable route for the
    already-authorized platform/source ids, while the same packet keeps the
    unready platform blockers visible.
1. In a large registry, add `--source-id "<registered-source-id>"` to
    `preflight live`, `preflight connected-plan`, or `readiness` when preparing
    one selected source. MCP uses `source_ids`; the scoped plan should show the
    same ids in `source_registry.selected_source_ids` and
    `connected_run_plan.source_ids`.
    Use MCP `list_sources` first when the agent needs the configured-source
    catalog before choosing those ids; pass `include_source_refs:false` when
    counts and ids are enough. If the selected source already has
    `latest_connected_runs[]`, prefer MCP `source_answer` with that `source_id`
    for a direct answer/context/evidence packet before planning another live
    run. Use the attached MCP `answer`, `lesson_context`, or `evidence_report`
    commands only when the agent intentionally wants the lower-level run id.
    When the question should be checked across several ready sources, use MCP
    `sources_answer` with `source_ids` or `platforms` so each source keeps its
    own evidence chain and quality state.
1. Run the plan's exact
    `calibration connected-run --mode live --allow-network` plan only after
    the connected plan shows the selected sources are ready.
1. Add live sources only after auth-state and storage roots are local and
    ignored by Git.
