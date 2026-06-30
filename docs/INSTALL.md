# Install

```bash
git clone git@github.com:8Dionysus/aoa-course-connector.git
cd aoa-course-connector
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

For local state:

```bash
export AOA_COURSE_INSTANCE_ROOT="$PWD/.connector-state"
aoa-course init
aoa-course doctor
aoa-course preflight live
```

`preflight live` is safe before credentials exist. It reports missing live auth
as a warning, does not touch the network, and gives the next commands for
Stepik tokens or browser storage-state capture.

When a Stepik source is registered as `public_api`, preflight can mark the
source sync route ready without a token. Token-gated Stepik sources and browser
sources still require matching local auth state before live sync is ready.

For this Abyss machine, use the external storage example when the corpus grows:

```bash
export AOA_COURSE_INSTANCE_ROOT=/srv/abyss-machine/storage/connectors/aoa-course-connector
```
