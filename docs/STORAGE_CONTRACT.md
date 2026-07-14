# Storage contract

Mutable connector state is external to the authored repository.

- `AOA_COURSE_DATA_ROOT` owns raw and normalized run data.
- `AOA_COURSE_CACHE_ROOT` owns rebuildable caches and indexes.
- `AOA_COURSE_AUTH_ROOT` owns credentials and browser-session state.
- `AOA_COURSE_ARTIFACT_ROOT` owns receipts, reports, connection profiles, and
  calibration artifacts.
- `AOA_COURSE_INSTANCE_ROOT` may provide one parent for all four roots.

Repository fixtures are small public method examples. They are not a fallback
location for live data. Portable packets may reference external paths but must
not copy private content or secret values into Git.

The executable storage status and fresh-install verifier own path resolution
checks. Runtime deployment and host storage lifecycle belong to
`abyss-stack` and `abyss-machine`.
