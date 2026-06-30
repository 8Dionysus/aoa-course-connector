# Storage Policy

The public repository stores method and small fixtures. Heavy or private data
must be routed through environment-configured local storage.

Required portable roots:

| Variable | Role |
| --- | --- |
| `AOA_COURSE_DATA_ROOT` | source registry, normalized runs, checkpoints |
| `AOA_COURSE_CACHE_ROOT` | regenerable HTTP/browser/cache artifacts |
| `AOA_COURSE_AUTH_ROOT` | local auth-state manifests and browser state |
| `AOA_COURSE_ARTIFACT_ROOT` | indexes, graphs, answer packets, reports |

Optional shortcuts:

| Variable | Role |
| --- | --- |
| `AOA_COURSE_INSTANCE_ROOT` | expands to `data/cache/auth/artifacts` |
| `AOA_COURSE_FAMILY_ROOT` | expands to `<family>/aoa-course-connector/...` |

This Abyss machine can use:

`/srv/abyss-machine/storage/connectors/aoa-course-connector`

That path is documentation for this host, not a public default.
