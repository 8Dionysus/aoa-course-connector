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
