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
