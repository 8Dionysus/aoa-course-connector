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
