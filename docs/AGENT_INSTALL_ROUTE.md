# Agent Install Route

1. Clone the repository.
2. Create a Python 3.11+ environment.
3. Install `.[dev]` for tests and CLI smoke checks.
4. Configure `AOA_COURSE_*` roots or `AOA_COURSE_INSTANCE_ROOT`.
5. Run `aoa-course doctor`.
6. Run `aoa-course readiness --run starter-fixture` to get the read-only
   install/source/run/MCP audit and its next commands.
7. Run the offline starter proof.
8. Build the semantic index with `build-semantic-index` and run at least one
   `--mode hybrid` answer to prove the vector contract.
9. Register a Stepik course with `discover stepik 67 --register`, then run
   `sync stepik-fixture --source-id "<registered-source-id>" --build-artifacts`
   to prove source-scoped clean API checkpoints without network access.
10. Run `discover stepik-account --from-fixture --register --source-limit 1` to
   prove connected-account course discovery can write Stepik sources without
   live credentials.
11. Run `preflight live --platform stepik` to prove the live readiness report
    is safe and read-only even before an operator provides `STEPIK_API_TOKEN`.
    Registered `public_api` Stepik sources can be sync-ready without a token;
    account discovery and token-gated sources still require the token.
12. Run `smoke stepik-fixture 67` to prove the combined clean API registration,
   sync, index/graph, answer, and privacy-safe report route.
13. Run browser fixture discovery with `--register` to prove the local source
   registry route.
14. After starter, Stepik fixture, and GetCourse browser fixture artifacts are
    built, run `eval answer-quality` to prove top-result path, source id,
    freshness, snippet, and evidence-field quality.
15. Run MCP calls for `connector_readiness`, `graph_neighbors`,
    `freshness_report`, `evidence_report`, and `refresh_plan` against
    `starter-fixture` to prove agents can audit connector readiness, traverse
    graph neighborhoods, inspect source evidence/freshness, and plan a refresh
    cycle without shelling into lower-level CLI internals.
16. After a registry-backed Stepik fixture sync, run `refresh query
    "Stepik public API evidence" --run "<checkpoint-run-id>" --mode hybrid
    --strategy fixture --execute` to prove the agent refresh loop can sync,
    select the new checkpoint run, rebuild indexes/graphs, and re-answer from
    refreshed evidence without live credentials.
17. Run the freshness conflict fixture and `eval freshness-ranking` to prove
    current material ranks above stale material when base relevance is tied.
18. Run the authority conflict fixture and `eval authority-ranking` to prove
    official lessons and mentor comments rank above learner comments when base
    relevance is tied.
19. After Stepik, GetCourse, and Skillspace fixture indexes are built, run
    `eval adapter-authority` to prove adapter-derived authority metadata reaches
    normalized objects and query packets.
20. Run `eval browser-transcripts` to prove visible GetCourse/Skillspace
    transcript and caption text becomes canonical transcript objects and
    source-backed answer evidence.
21. Run `eval live-calibration` to prove the fixture-safe calibration packet for
    GetCourse, Skillspace, and Stepik smoke reports before collecting connected
    account reports.
22. Run `calibration connected-run --mode fixture --run connected-fixture-proof`
    to prove source-registry sync, smoke reports, connected plan/runbook,
    calibration packet, intake, and one connected run receipt without touching
    live sources.
23. Before live browser sources, run `auth plan-browser-state`, capture the
    local Playwright state with `auth capture-browser-state`, and verify it with
    `auth inspect-browser-state`.
24. Run `preflight live --platform getcourse` or
    `preflight live --platform skillspace` to inspect source registry and
    redacted browser-state readiness before live discovery or sync.
25. Confirm browser preflight marks only sources whose host matches the saved
    storage state as sync-ready.
26. Run `preflight connected-plan --write-runbook
    "${AOA_COURSE_ARTIFACT_ROOT:-.connector-state/artifacts}/connected-source-runbook.md"`
    to produce the redacted setup/sync/smoke/calibration handoff with portable
    runtime artifact paths.
27. Run `calibration connected-run --mode live --allow-network` only after the
    connected plan shows the selected sources are ready.
28. Add live sources only after auth-state and storage roots are local and
    ignored by Git.
