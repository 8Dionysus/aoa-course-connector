# Storage Contract

Generated connector state is rebuildable and private unless explicitly exported
by the operator.

The repo-local default `.connector-state` is only for small smoke runs. Real
course bases should use external roots:

```bash
AOA_COURSE_DATA_ROOT
AOA_COURSE_CACHE_ROOT
AOA_COURSE_AUTH_ROOT
AOA_COURSE_ARTIFACT_ROOT
```

Stable objects should be rebuildable from raw or normalized artifacts.
