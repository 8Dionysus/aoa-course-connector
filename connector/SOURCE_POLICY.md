# Source Policy

`aoa-course-connector` may ingest course-platform information only from sources
the connected user is authorized to access.

Allowed source modes:

- `browser_session`: operator logs in locally, exports or reuses browser auth
  state under `AOA_COURSE_AUTH_ROOT`, and the connector reads visible course
  pages.
- `api_token`: platform token or OAuth route for official APIs.
- `offline_export`: operator-provided course export or safe fixture.
- `public_api`: public catalog or LMS API content that does not require private
  account access.

Priority hard adapters:

- GetCourse via `browser_session`.
- Skillspace via `browser_session`.

Reference clean adapters:

- Stepik via official API.
- Moodle or Canvas via official LMS APIs.

Denied by default:

- unauthorized access;
- credential sharing in Git;
- cookie or token commits;
- raw paid/private course page commits;
- DRM bypass;
- bulk media download as a default behavior;
- write actions against course platforms.

When protected media is present, preserve metadata, source URL, page evidence,
available transcripts/captions, and lesson context. Do not make media cracking a
connector behavior.
