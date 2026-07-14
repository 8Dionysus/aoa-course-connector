# Boundaries

- Public Git stores method, schemas, code, docs, fixtures, and small tests.
- Local storage stores raw captures, normalized private data, indexes, graphs,
  auth-state, and media metadata.
- Secrets and browser state belong under `AOA_COURSE_AUTH_ROOT` or an external
  vault, never in Git.
- Paid/private course access is allowed only through the connected user's own
  authorized account.
- Media download is optional and subordinate to knowledge retrieval.
- DRM bypass is out of scope.
- Root `stats/` may derive public reference measurements from committed
  fixtures and adapter-owned coverage packets. It does not read private or live
  storage and cannot claim eval success, connector readiness, corpus quality,
  or runtime health.
- Shared measurement grammar and cross-owner composition belong to
  `aoa-stats`; course objects, sources, coverage, and privacy remain owned here.
