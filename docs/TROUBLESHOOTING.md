# Troubleshooting boundaries

Troubleshooting starts from the structured packet that owns the failing state,
not from a copied command recipe.

| Symptom | Inspect | Meaning |
| --- | --- | --- |
| Missing normalized bundle | ingest receipt and storage roots | materialization has not produced owner data |
| Empty or stale keyword/semantic result | index metadata, freshness, provider contract | rebuild or provider calibration may be needed |
| Missing graph context | graph metadata and canonical object inventory | graph projection is absent or incomplete |
| Browser source blocked | host-specific auth inspection and preflight | state is missing, expired, or mismatched |
| Bounded coverage | source coverage counts and gaps | inventory was intentionally not exhausted |
| Apparent removals after bounded refresh | identity continuity | removal is inconclusive, not source deletion |
| Partial connected run | stage failures and repair lanes | one bounded repair route remains |
| MCP call error | structuredContent and server stderr | inspect the tool-owned error without exposing secrets |
| Stats value unknown | fixture inventory and adapter coverage | the declared population is incomplete or malformed |

Exact recovery syntax belongs to the CLI parser and packet-provided next action,
while the root `AGENTS.md` names the bounded validation route. Do not paste
private payloads into issues, docs, evals, or stats artifacts.
