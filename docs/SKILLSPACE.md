# Skillspace adapter

Skillspace is a browser-session hard adapter that reuses the shared discovery,
crawl, normalization, evidence, retrieval, graph, and calibration pipeline.

## Discovery and crawl

The adapter extracts course entrypoints from accessible account pages and
follows bounded catalog pagination. Course indexes expose a visible lesson
population before crawl limits are applied. Missing pages are represented as
unfetched evidence rather than full lessons.

## Content

Accessible pages may yield lesson text, assets, assignments, visible progress,
comments, transcript/caption blocks, and caption sidecars. Native course and
lesson paths remain attached to every normalized and indexed object.

## Authorization and privacy

A registered Skillspace source is live-ready only when the selected local
browser state matches its host. Live work requires explicit network
authorization. Fixture and snapshot routes remain no-network.

Credentials, browser state, paid/private HTML, raw captures, normalized private
content, indexes, graphs, vectors, and runtime reports never belong in Git.
