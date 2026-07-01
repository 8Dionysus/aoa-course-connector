# Agent Install Route

1. Clone the repository.
2. Create a Python 3.11+ environment.
3. Install `.[dev]` for tests and CLI smoke checks.
4. Configure `AOA_COURSE_*` roots or `AOA_COURSE_INSTANCE_ROOT`.
5. Run `aoa-course doctor`.
6. Run `aoa-course bootstrap fixture --run starter-fixture --connected-run connected-calibration`
   to create the local starter bundle, keyword/semantic indexes, graph, and
   default GetCourse/Skillspace/Stepik fixture connected-run receipt without
   network access.
7. Run `aoa-course readiness --run starter-fixture` to get the read-only
   install/source/run/MCP audit and its next commands.
8. Run `aoa-course goal audit --run starter-fixture --connected-run
   connected-calibration --require-ready-for-connection` to get a DoD-oriented
   JSON handoff. It should report `ready_for_operator_connection: true` and
   `goal_complete: false`, with live account calibration listed under
   `remaining_live_requirements`.
9. Run `aoa-course goal audit --run starter-fixture --connected-run
   connected-calibration --write-connection-handoff
   "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/goal-connection-handoff.md"`
   to write the redacted `aoa_course_connection_handoff_v1` checklist for the
   operator/source-connection phase.
10. When operator source refs are available, run `aoa-course connect profile`
    with real GetCourse/Skillspace URLs, Stepik course ids, state-file paths,
    and semantic-provider settings, then run `connect inspect` and `connect
    apply`. The profile is `aoa_course_connection_profile_v1`; it is runtime
    artifact state under `AOA_COURSE_ARTIFACT_ROOT`, does not store token
    values, and `apply` mutates only the local source registry. MCP agents can
    inspect it through `connection_profile_inspect`. Use `--write-runbook` to
    write the same redacted source/auth/connected-plan/semantic checklist as
    Markdown beside the profile JSON.
11. Run the offline starter proof.
12. Run `preflight semantic-provider --run starter-fixture --require-ready`,
   then build the semantic index with `build-semantic-index` and run at least
   one `--mode hybrid` answer to prove the vector contract. For
   `http_json_v1`, run the same preflight with `--embedding-endpoint`,
   `--embedding-model`, and `--embedding-token-env`; it must report
   `token_env_present` without printing the token value before the first
   network-touching semantic build.
13. Register a Stepik course with `discover stepik 67 --register`, then run
   `sync stepik-fixture --source-id "<registered-source-id>" --build-artifacts`
   to prove source-scoped clean API checkpoints without network access.
14. Run `discover stepik-account --from-fixture --register --source-limit 1` to
   prove connected-account course discovery can write Stepik sources without
   live credentials.
15. Run `preflight live --platform stepik` to prove the live readiness report
    is safe and read-only even before an operator provides `STEPIK_API_TOKEN`.
    Registered `public_api` Stepik sources can be sync-ready without a token;
    account discovery and token-gated sources still require the token.
16. Run `smoke stepik-fixture 67` to prove the combined clean API registration,
   sync, index/graph, answer, and privacy-safe report route.
17. Run browser fixture discovery with `--register` to prove the local source
   registry route.
18. After starter, Stepik fixture, and GetCourse browser fixture artifacts are
    built, run `eval answer-quality` to prove top-result path, source id,
    freshness, snippet, and evidence-field quality.
19. Run MCP calls for `connector_readiness`, `goal_audit`,
    `connection_profile_inspect`, `semantic_provider_preflight`,
    `graph_neighbors`, `freshness_report`, `evidence_report`, and
    `refresh_plan` against
    `starter-fixture` to prove agents can audit connector readiness, inspect
    the DoD-oriented remaining live prerequisites, traverse graph
    neighborhoods, inspect source evidence/freshness, and plan a refresh cycle
    without shelling into lower-level CLI internals.
20. After a registry-backed Stepik fixture sync, run `refresh query
    "Stepik public API evidence" --run "<checkpoint-run-id>" --mode hybrid
    --strategy fixture --execute` to prove the agent refresh loop can sync,
    select the new checkpoint run, rebuild indexes/graphs, and re-answer from
    refreshed evidence without live credentials.
21. Run the freshness conflict fixture and `eval freshness-ranking` to prove
    current material ranks above stale material when base relevance is tied.
22. Run the authority conflict fixture and `eval authority-ranking` to prove
    official lessons and mentor comments rank above learner comments when base
    relevance is tied.
23. After Stepik, GetCourse, and Skillspace fixture indexes are built, run
    `eval adapter-authority` to prove adapter-derived authority metadata reaches
    normalized objects and query packets.
24. Run `eval browser-transcripts` to prove visible GetCourse/Skillspace
    transcript and caption text becomes canonical transcript objects and
    source-backed answer evidence.
25. Run `eval live-calibration` to prove the fixture-safe calibration packet for
    GetCourse, Skillspace, and Stepik smoke reports before collecting connected
    account reports.
26. Run `calibration connected-run --mode fixture --run connected-fixture-proof`
    to prove source-registry sync, smoke reports, connected plan/runbook,
    calibration packet, intake, and one connected run receipt without touching
    live sources.
27. Before live browser sources, run `auth plan-browser-state`, capture the
    local Playwright state with `auth capture-browser-state`, and verify it with
    `auth inspect-browser-state`. The plan/capture commands should carry
    `--expect-origin-contains`; the capture receipt must show
    `expected_origin_matched: true` before discovery or sync.
28. Run `preflight live --platform getcourse` or
    `preflight live --platform skillspace` to inspect source registry and
    redacted browser-state readiness before live discovery or sync.
29. Confirm browser preflight marks only sources whose host matches the saved
    storage state as sync-ready.
30. Run `preflight connected-plan --write-runbook
    "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connected-source-runbook.md"`
    to produce the redacted setup/sync/smoke/calibration handoff with portable
    runtime artifact paths and a `connected_run_handoff`.
31. In a large registry, add `--source-id "<registered-source-id>"` to
    `preflight live`, `preflight connected-plan`, or `readiness` when preparing
    one selected source. MCP uses `source_ids`; the scoped plan should show the
    same ids in `source_registry.selected_source_ids` and
    `connected_run_handoff.source_ids`.
32. Run the plan's exact
    `calibration connected-run --mode live --allow-network` handoff only after
    the connected plan shows the selected sources are ready.
33. Add live sources only after auth-state and storage roots are local and
    ignored by Git.
