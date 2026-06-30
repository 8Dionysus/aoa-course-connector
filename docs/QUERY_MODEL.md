# Query Model

A useful result must include:

- matched snippet;
- course/module/lesson/step path;
- source URL;
- fetched timestamp;
- platform;
- evidence IDs;
- freshness state;
- score.

Answers should be built from query results rather than free-floating summaries.

## Index Modes

- `keyword`: deterministic inverted-index search over normalized course
  knowledge items.
- `semantic`: deterministic local sparse vector search using the
  `local_hashing_v1` provider. It hashes text tokens, title/path tokens,
  adjacent bigrams, kind, and platform features into normalized vectors.
- `hybrid`: combines normalized keyword score and semantic vector score while
  preserving the same evidence-bearing result shape.

The local semantic index is a portable baseline, not a claim that the repo has
external model embeddings configured. Future embedding providers must keep this
contract stable: source-backed snippets, path, URL, fetched timestamp, evidence
IDs, freshness, and score components remain visible.

Commands:

```bash
aoa-course build-semantic-index --run starter-fixture
aoa-course query "bootloader rollback" --run starter-fixture --mode semantic
aoa-course answer "bootloader rollback" --run starter-fixture --mode hybrid
aoa-course mcp call semantic_search '{"query":"rollback","run":"starter-fixture"}'
aoa-course mcp call hybrid_search '{"query":"rollback","run":"starter-fixture"}'
```
