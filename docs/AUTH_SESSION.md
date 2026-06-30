# Auth And Session Guide

Browser-session adapters follow this route:

1. The operator logs in locally in a browser automation context.
2. The auth state is saved under `AOA_COURSE_AUTH_ROOT`.
3. The connector can use that state to discover visible course entrypoints and
   register them under `AOA_COURSE_DATA_ROOT`.
4. The connector uses that state to read visible course pages.
5. Each fetched object records source URL, fetched timestamp, platform, and
   evidence references.

The public repository must not contain browser state, cookies, tokens, phone
numbers, paid/private pages, or course exports.

## Browser State Onboarding

Plan the local state path first:

```bash
aoa-course auth plan-browser-state getcourse "https://school.example"
```

Then install the optional browser extra and capture a Playwright storage-state
file from the operator's own logged-in session:

```bash
python -m pip install -e ".[browser]"

aoa-course auth capture-browser-state getcourse "https://school.example" \
  --login-url "https://school.example/cms/system/login" \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --expect-origin-contains "school.example"
```

The command opens a local browser window. Log in normally, then press Enter in
the terminal so the connector can save storage state under `AOA_COURSE_AUTH_ROOT`.
For automation or already-authenticated browser contexts, use `--no-prompt`.
The capture receipt is redacted and includes `expected_origin_contains` plus
`expected_origin_matched`; if it reports `warning` or `false`, inspect the
state before using it for live source discovery or sync.

Inspect the state before using it for live discovery or sync:

```bash
aoa-course auth inspect-browser-state "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --expect-origin-contains "school.example"
```

Inspection reports only counts, timestamps, and match status. It does not print
cookie values, localStorage values, or tokens.

## Live Preflight

Before running live discovery or sync, ask the connector to inspect local
readiness without touching the network:

```bash
aoa-course preflight live \
  --platform getcourse \
  --state-file "$AOA_COURSE_AUTH_ROOT/getcourse/account.storage-state.json" \
  --expect-origin school.example
```

The report checks registered sources, browser storage-state usability, Stepik
token presence when requested, and next commands. It is read-only, returns
`network_touched: false`, and redacts cookie, localStorage, and token values.
Use `--require-ready` when an automation script should fail if a live source is
not ready yet.
