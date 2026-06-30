# GetCourse Notes

GetCourse is a priority hard adapter.

Expected route:

- browser-session auth state under `AOA_COURSE_AUTH_ROOT`;
- discover visible trainings/courses;
- discover lesson groups and lessons;
- extract lesson title, text blocks, attachments metadata, available captions or
  transcripts, comments when visible, and source URLs;
- record media as asset metadata unless permitted resolution is explicitly
  enabled.

The connector should not depend on media download to deliver useful knowledge.

## Current Working Route

`aoa-course-connector` supports GetCourse through the shared browser-session
snapshot adapter:

```bash
aoa-course materialize browser-fixture --platform getcourse --run getcourse-browser-fixture
aoa-course build-index --run getcourse-browser-fixture
aoa-course build-graph --run getcourse-browser-fixture
aoa-course answer "GetCourse bootloader rollback evidence" --run getcourse-browser-fixture
```

For live operator-owned pages, use `materialize browser-live` with a local
Playwright storage-state file under `AOA_COURSE_AUTH_ROOT`.
