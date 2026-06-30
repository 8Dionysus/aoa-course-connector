# Privacy And Security

- Keep auth-state and private course artifacts outside Git.
- Treat course content as private unless the operator explicitly marks it public.
- Do not log secrets or cookies.
- Use `auth inspect-browser-state` for redacted auth-state health checks; do not
  print or commit Playwright storage-state JSON.
- Do not perform write actions against course platforms.
- Keep live tests gated and fixture tests safe for CI.
