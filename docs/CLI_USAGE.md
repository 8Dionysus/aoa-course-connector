# CLI Usage

```bash
aoa-course doctor
aoa-course init
aoa-course adapters list
aoa-course sources add demo-course --platform offline_export --title "Demo Course"
aoa-course materialize fixture --run starter-fixture
aoa-course materialize stepik-fixture --run stepik-fixture
aoa-course materialize stepik-live 67 --run stepik-live-smoke --max-sections 1 --max-units-per-section 1 --max-steps-per-lesson 2
aoa-course build-index --run starter-fixture
aoa-course build-graph --run starter-fixture
aoa-course query "rollback" --run starter-fixture
aoa-course answer "bootloader unlock rollback" --run starter-fixture
aoa-course mcp tools
```
