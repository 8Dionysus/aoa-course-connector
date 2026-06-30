# Agent Install Route

1. Clone the repository.
2. Create a Python 3.11+ environment.
3. Install `.[dev]` for tests and CLI smoke checks.
4. Configure `AOA_COURSE_*` roots or `AOA_COURSE_INSTANCE_ROOT`.
5. Run `aoa-course doctor`.
6. Run the offline starter proof.
7. Build the semantic index with `build-semantic-index` and run at least one
   `--mode hybrid` answer to prove the vector contract.
8. Register a Stepik course with `discover stepik 67 --register`, then run
   `sync stepik-fixture --build-artifacts` to prove clean API source-registry
   checkpoints without network access.
9. Run `discover stepik-account --from-fixture --register --source-limit 1` to
   prove connected-account course discovery can write Stepik sources without
   live credentials.
10. Run `preflight live --platform stepik` to prove the live readiness report
    is safe and read-only even before an operator provides `STEPIK_API_TOKEN`.
    Registered `public_api` Stepik sources can be sync-ready without a token;
    account discovery and token-gated sources still require the token.
11. Run `smoke stepik-fixture 67` to prove the combined clean API registration,
   sync, index/graph, answer, and privacy-safe report route.
12. Run browser fixture discovery with `--register` to prove the local source
   registry route.
13. After starter, Stepik fixture, and GetCourse browser fixture artifacts are
    built, run `eval answer-quality` to prove top-result path, source id,
    freshness, snippet, and evidence-field quality.
14. Run the freshness conflict fixture and `eval freshness-ranking` to prove
    current material ranks above stale material when base relevance is tied.
15. Run the authority conflict fixture and `eval authority-ranking` to prove
    official lessons and mentor comments rank above learner comments when base
    relevance is tied.
16. After Stepik, GetCourse, and Skillspace fixture indexes are built, run
    `eval adapter-authority` to prove adapter-derived authority metadata reaches
    normalized objects and query packets.
17. Run `eval live-calibration` to prove the fixture-safe calibration packet for
    GetCourse, Skillspace, and Stepik smoke reports before collecting connected
    account reports.
18. Before live browser sources, run `auth plan-browser-state`, capture the
    local Playwright state with `auth capture-browser-state`, and verify it with
    `auth inspect-browser-state`.
19. Run `preflight live --platform getcourse` or
    `preflight live --platform skillspace` to inspect source registry and
    redacted browser-state readiness before live discovery or sync.
20. Confirm browser preflight marks only sources whose host matches the saved
    storage state as sync-ready.
21. Add live sources only after auth-state and storage roots are local and
    ignored by Git.
