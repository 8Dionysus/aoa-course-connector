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
11. Run `smoke stepik-fixture 67` to prove the combined clean API registration,
   sync, index/graph, answer, and privacy-safe report route.
12. Run browser fixture discovery with `--register` to prove the local source
   registry route.
13. After starter, Stepik fixture, and GetCourse browser fixture artifacts are
    built, run `eval answer-quality` to prove top-result path, source id,
    freshness, snippet, and evidence-field quality.
14. Before live browser sources, run `auth plan-browser-state`, capture the
    local Playwright state with `auth capture-browser-state`, and verify it with
    `auth inspect-browser-state`.
15. Run `preflight live --platform getcourse` or
    `preflight live --platform skillspace` to inspect source registry and
    redacted browser-state readiness before live discovery or sync.
16. Add live sources only after auth-state and storage roots are local and
    ignored by Git.
