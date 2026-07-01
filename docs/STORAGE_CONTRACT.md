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

Runtime ids such as `--run`, `--sync-run`, and discovery run names are portable
storage slugs, not filesystem paths. Use 1-160 letters, digits, dots,
underscores, or hyphens, starting with a letter or digit. The connector rejects
path-like ids before writing run, discovery, or sync artifacts.
