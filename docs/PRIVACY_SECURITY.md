# Privacy And Security

- Keep auth-state and private course artifacts outside Git.
- Treat course content as private unless the operator explicitly marks it public.
- Do not log secrets or cookies.
- Use `auth inspect-browser-state` for redacted auth-state health checks; do not
  print or commit Playwright storage-state JSON.
- Do not perform write actions against course platforms.
- Keep live tests gated and fixture tests safe for CI.
- Use `preflight live` before live discovery/sync when possible; it checks local
  token presence and browser-state usability without touching the network or
  printing secret values.
- Browser preflight checks storage state against each registered source host so
  an auth state from one host is not treated as proof of access to another host.
