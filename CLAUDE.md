# AI Admin Assistant — CLAUDE.md

## Project Overview

Read-only AI chatbot service for internal logistics/admin operations. Answers questions about orders, drivers, and organizations by combining live API tool-calling with offline indexed codebase knowledge.

**Stack:** FastAPI · Python 3.11 · Google Gemini (Vertex AI) · SQLite · ChromaDB · httpx

**Gemini Models Used:**
- `gemini-3-flash-preview` — default for most queries (fast, cost effective)
- `gemini-3-pro-preview` — for complex reports and knowledge-heavy queries (slower, more expensive)

---

## Common Commands

```bash
make install          # Create venv + install dependencies
make run              # Start server at http://localhost:8000
make debug            # Auto-reload dev mode
make index-all        # Run full codebase indexer + cross-linker
make index-order-service  # Index order-service Go repo only
```

Swagger docs available at `http://localhost:8000/docs` when running.

---

## Architecture

### Layering Rule
```
HTTP layer (no logic) → Orchestrator (all LLM logic) → Services (API calls only)
```
Never put business logic in `app/services/` — that belongs in the orchestrator.

### Key Components

| Path | Responsibility |
|------|---------------|
| `app/main.py` | FastAPI entry point, routes, auth, rate limiting |
| `app/config.py` | Pydantic Settings — all env vars defined here |
| `app/orchestrator/ai_orchestrator.py` | Tool-calling loop, feature detection, context injection |
| `app/orchestrator/memory_service.py` | 3-layer memory: short-term (5 turns) + summary + long-term facts |
| `app/orchestrator/context_builder.py` | Token-budgeted context assembly |
| `app/tools/` | 50+ tool schemas (thin wrappers, no logic) |
| `app/services/` | External API clients (httpx, connection pooling) |
| `app/prompts/` | Modular prompt files assembled per feature key |
| `app/persistence/chat_store.py` | SQLite chat history (WAL mode) |
| `indexer/` | Offline codebase knowledge pipeline (Go/Java/React) |

### Tool-Calling Loop
- Max iterations: `MAX_TOOL_LOOPS=3`
- Duplicate suppression is active — same tool+args won't fire twice
- Falls back to synthesis if loop exhausted without final answer

### Memory Layers
1. **Short-term** — last 5 verbatim turns
2. **Summary** — Gemini-compressed older turns
3. **Long-term** — auto-extracted facts/entities/decisions via regex

### Feature Detection
The orchestrator routes each query to a modular system prompt and selects model tier:
- Flash model (`MODEL_NAME`) — default for most queries
- Pro model (`PRO_MODEL_NAME`) — reports and knowledge-heavy queries

---

## Environment Variables

**Required:**
```
GEMINI_API_KEY        # Google AI Studio API key
CHAT_API_KEY          # Auth secret for /chat endpoint
```

**Common optional:**
```
MODEL_NAME=gemini-3-flash-preview
PRO_MODEL_NAME=gemini-3-pro-preview
CHAT_HISTORY_DB=data/chat_history.db
CONTEXT_CACHING_ENABLED=true

ORDER_SERVICE_BASE_URL
USER_SERVICE_BASE_URL
DRIVER_SERVICE_BASE_URL
COMMON_SERVICE_BASE_URL

ORDER_SERVICE_REPO_PATH    # For indexer
USER_SERVICE_REPO_PATH
```

Copy `.env.example` to `.env` to get started.

---

## Data & Persistence

- `data/chat_history.db` — SQLite WAL, sessions + turns + memory items
- `data/knowledge/knowledge.db` — Indexer output (enums, structs, flows, edges, FTS5)
- `data/vectordb/` — ChromaDB collections for semantic search

The `data/` directory is gitignored. Persistence is optional — omit `CHAT_HISTORY_DB` for in-memory-only mode.

---

## Codebase Indexer

Lives in `indexer/`. Parses Go (Gin routes + service flows), Java (Spring Boot enums/types), and React (API call graph) using tree-sitter AST + regex fallback.

- Incremental: uses SHA-256 hashing, only re-indexes changed files
- Cross-linker (`indexer/linker.py`) matches React API calls to Go handlers
- Run `make index-all` after pulling new service code

---

## Tools

All tools in `app/tools/` are thin schema wrappers registered automatically from function signatures via `app/tools/__init__.py`. No business logic belongs here — tools delegate to `app/services/`.

Tool files by domain:
- `order_tools.py` — orders, pricing, reports
- `user_tools.py` — users, orgs, branches
- `driver_tools.py` — drivers, location, fares
- `common_tools.py` — vehicles, addresses, goods
- `docs_tools.py` — endpoint search + handler source
- `knowledge_tools.py` — enums, structs, flows, graph

---

## Prompts

Prompts live in `app/prompts/` and are assembled modularly per feature key. Base formatting rules are in `app/prompts/base/output-format.md`. Feature-specific instructions are in `app/prompts/features/`.

Do not hardcode prompt strings in Python files — keep them in `.md` files under `app/prompts/`.

---

## Context Caching

When `CONTEXT_CACHING_ENABLED=true` (Vertex AI only), system instructions + tool schemas are cached, reducing token cost ~75%. This requires a Vertex AI project setup — does not work with AI Studio API keys alone.
