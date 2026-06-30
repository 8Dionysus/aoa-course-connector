# Adapter Guide

Each adapter should implement:

- `platform_id`
- supported auth modes;
- source discovery;
- course tree discovery;
- lesson page extraction;
- asset metadata extraction;
- transcript/caption extraction when available;
- conversion to canonical course objects;
- evidence records for every normalized object.

Adapters may return partial content. They should preserve platform-specific
notes in `metadata` without changing the core schema.
