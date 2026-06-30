# Troubleshooting

Run:

```bash
aoa-course doctor
aoa-course storage status --measure
python scripts/validate_connector.py
```

If query returns no results, rebuild:

```bash
aoa-course materialize fixture --run starter-fixture
aoa-course build-index --run starter-fixture
aoa-course build-graph --run starter-fixture
```

If a live browser route cannot read a connected account, inspect the local
storage state before rerunning discovery or sync:

```bash
aoa-course auth inspect-browser-state "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --expect-origin-contains "school.example"
```

If the status is `missing`, `empty`, or `mismatch`, rerun
`auth capture-browser-state` and log in with the same account that can view the
course pages.

For a combined source/auth readiness report that does not touch the network:

```bash
aoa-course preflight live --platform getcourse \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --expect-origin school.example
```

For Stepik authenticated routes:

```bash
aoa-course preflight live --platform stepik --stepik-token-env STEPIK_API_TOKEN
```
