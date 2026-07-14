# Browser-session authorization

GetCourse and Skillspace adapters may use only pages available to the connected
user through legitimate account access. Browser state is local runtime evidence,
not repository content.

## State ownership

Playwright storage state belongs under `AOA_COURSE_AUTH_ROOT` or an external
secret store. Cookie values, local storage, browser profiles, tokens, and
captured private pages must never enter Git, logs, KAG, eval fixtures, stats
packets, or calibration summaries.

A source host is ready only when the selected state contains evidence for that
exact host. A state file for one school does not authorize another school.
Inspection reports origins, expiry posture, and expected-origin matching without
printing values.

## Import and capture

When an operator already has a usable Firefox session, the connector can plan a
host-matched import. Interactive Playwright capture is the fallback. Both routes
must be followed by redacted inspection before discovery or sync.

The executable CLI parser owns exact import, capture, and inspection syntax.
Readiness and connected plans expose host-specific state-file candidates rather
than requiring documentation to duplicate commands.

## Preflight

Preflight is read-only and no-network. It checks configured source refs, local
state-file presence, expected-origin matching, expiry signals, and selected
source scope. Missing or mismatched state remains an explicit blocker.

A ready preflight does not itself authorize a network call. Live discovery,
crawl, sync, smoke, or calibration still requires an explicit network gate.

## Stepik

Stepik public course API access and account-level discovery have different auth
postures. Public course material may be available without a token; account
catalogs and protected enrichment may require a token or browser-state cookie
route. Token presence may be reported, but token values may not.
