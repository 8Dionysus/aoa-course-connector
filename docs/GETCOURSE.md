# GetCourse adapter

GetCourse is a browser-session hard adapter over the shared course connector
pipeline. It uses only pages available to the connected operator account and
does not bypass platform authorization.

## Discovery and crawl

Account catalogs may expose course entrypoints through standard links or
GetCourse-specific embedded routes. Discovery follows bounded catalog
pagination and retains the native course URL as evidence.

Course crawl recognizes GetCourse lesson routes, records the complete visible
lesson inventory before limits, and preserves module/title hints. Missing lesson
pages become explicit `discovered_not_fetched` evidence.

## Content

Accessible lesson pages may provide text, assets, assignments, visible progress,
mentor or learner comments, transcript blocks, and caption sidecars. Author role
and browser-source authority survive normalization and ranking.

Access-denied, prerequisite, or locked pages remain blocked evidence and do not
supply normal lesson body text.

## Authorization

Each registered school host requires matching local browser state.
Host-mismatched or expired state remains blocked in preflight. Live discovery,
crawl, sync, and smoke require an explicit network gate.

Fixtures and example hosts prove adapter method only. Private pages, state,
normalized content, indexes, graphs, and reports remain outside Git.
