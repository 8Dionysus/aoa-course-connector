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
```

For this Abyss machine, use the external storage example when the corpus grows:

```bash
export AOA_COURSE_INSTANCE_ROOT=/srv/abyss-machine/storage/connectors/aoa-course-connector
```
