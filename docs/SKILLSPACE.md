# Skillspace Notes

Skillspace is a priority hard adapter.

Expected route:

- browser-session auth state under `AOA_COURSE_AUTH_ROOT`;
- discover available courses from the connected account;
- extract module/lesson hierarchy and lesson page content;
- preserve assignment, progress, comment, and asset metadata when visible;
- store evidence for every normalized object.

Skillspace public API coverage appears limited for full course-content export, so
the first live route should be browser-session discovery.
