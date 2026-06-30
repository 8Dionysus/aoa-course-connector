# Auth And Session Guide

Browser-session adapters follow this route:

1. The operator logs in locally in a browser automation context.
2. The auth state is saved under `AOA_COURSE_AUTH_ROOT`.
3. The connector uses that state to read visible course pages.
4. Each fetched object records source URL, fetched timestamp, platform, and
   evidence references.

The public repository must not contain browser state, cookies, tokens, phone
numbers, paid/private pages, or course exports.
