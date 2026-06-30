# Agent Install Route

1. Clone the repository.
2. Create a Python 3.11+ environment.
3. Install `.[dev]` for tests and CLI smoke checks.
4. Configure `AOA_COURSE_*` roots or `AOA_COURSE_INSTANCE_ROOT`.
5. Run `aoa-course doctor`.
6. Run the offline starter proof.
7. Register a Stepik course with `discover stepik 67 --register`, then run
   `sync stepik-fixture --build-artifacts` to prove clean API source-registry
   checkpoints without network access.
8. Run browser fixture discovery with `--register` to prove the local source
   registry route.
9. Add live sources only after auth-state and storage roots are local and
   ignored by Git.
