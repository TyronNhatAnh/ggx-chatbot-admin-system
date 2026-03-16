# Discovery Output

This directory contains generated artifacts from `scripts/run_discovery.py`
and from the indexer pipeline (`--docs` flag).

## Artifacts

| File | Produced by | Contents |
|------|-------------|----------|
| `web2/fe_api_inventory.json` | `scan-fe` | Outgoing HTTP calls found in the Web2 frontend repo |
| `order-services/be_endpoints.json` | `scan-be` / indexer `--docs` | Backend endpoint definitions (method, path, handler, service_calls) |
| `order-services/code_context/*.context.md` | `scan-be` / indexer `--docs` | Handler-level Go source code snippets |
| `flow_mappings.json` | `map-flows` | FE call → BE endpoint mappings |

> **Note:** These are generated artifacts — do not edit manually.
> They can become stale when upstream repos change. Regenerate when needed.

## Explorer vs Indexer

| Concern | Explorer (this dir) | Indexer (data/knowledge/) |
|---|---|---|
| Endpoint index | ✅ `be_endpoints.json` | Embedded in flow records |
| Handler source code | ✅ `*.context.md` (actual Go code) | ❌ (names only) |
| FE API inventory | ✅ `fe_api_inventory.json` | ❌ |
| Enum/struct definitions | ❌ | ✅ SQLite |
| Graph edges + traversal | ❌ | ✅ SQLite |
| Semantic search | ❌ | ✅ ChromaDB vectors |
| Cross-service links | ❌ | ✅ linker x_calls edges |

Both systems are complementary. Explorer produces human-readable docs;
indexer produces the queryable knowledge base for AI tools.

## Regenerate

```bash
# Option 1: Standalone discovery scan
make scan-all

# Option 2: Via indexer (auto-runs explorer for BE services)
make index-service SERVICE_REPO=/path/to/repo SERVICE_NAME=order-service LANG=go
```

## When To Run Discovery

1. First-time onboarding to new FE/BE repos
2. Major API changes made previous mappings stale
3. Preparing candidate feature scopes

For deep analysis of one known feature, use `make explore` instead.
