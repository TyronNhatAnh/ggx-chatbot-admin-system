# AI Admin Assistant — CLAUDE.md

## Project Overview

Read-only AI chatbot service for internal logistics/admin operations. Answers questions about orders, drivers, and organizations by combining live API tool-calling with offline indexed codebase knowledge.

**Stack:** FastAPI · Python 3.11 · Google Gemini (Vertex AI) · SQLite · ChromaDB · httpx

**Gemini Models Used:**
- `gemini-3-flash-preview` — default for most queries (fast, cost effective)
- `gemini-3.1-pro-preview` — for complex reports and knowledge-heavy queries (slower, more expensive)

---

## Common Commands

```bash
make install          # Create venv + install dependencies
make run              # Start server at http://localhost:8000
make debug            # Auto-reload dev mode
make index-all        # Index all configured services + run cross-linker
make index-order-service   # Index order-service (Go)
make index-user-service    # Index user-service (Go)
make index-driver-service  # Index driver-service (Go)
make index-common-service  # Index common-service (Go)
make index-web2            # Index consumer web frontend (React)
make index-admin-service   # Index admin-service (Java Spring Boot)
make link                  # Run cross-linker (React → Go handler matching) only
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
| `app/tools/` | 38 tool schemas (thin wrappers, no logic) |
| `app/services/` | External API clients (httpx, connection pooling) |
| `app/prompts/` | Modular prompt files assembled per feature key |
| `app/persistence/chat_store.py` | SQLite chat history (WAL mode) |
| `indexer/` | Offline codebase knowledge pipeline (Go/Java/React) |

### Tool-Calling Loop
- Max iterations: `MAX_TOOL_LOOPS=6`
- Duplicate suppression is active — same tool+args won't fire twice
- Falls back to synthesis if loop exhausted without final answer

### Memory Layers
1. **Short-term** — last 5 verbatim turns (`SHORT_TERM_MAX_TURNS=5`)
2. **Summary** — Gemini-compressed older turns (triggered every 5 new turns, `SUMMARIZE_THRESHOLD=5`)
3. **Long-term** — auto-extracted facts/entities/decisions via regex (max 50 items per session)

### Feature Detection
The orchestrator routes each query to a modular system prompt and selects model tier:
- Flash model (`MODEL_NAME`) — default for most queries; thinking_budget=1024, max_output_tokens=4096
- Pro model (`PRO_MODEL_NAME`) — reports and knowledge-heavy queries; thinking uncapped, max_output_tokens=8192
- Both models run with `include_thoughts=True`; thought parts are filtered before sending responses to users
- Detected `feature_key` persists in `SessionState` across follow-up turns

---

## Environment Variables

**Required:**
```
CHAT_API_KEY                    # Auth secret for /chat endpoint
VERTEX_AI_CREDENTIALS_FILE      # Path to JSON file containing Vertex AI SA key(s) (default: app/config/vertex-ai.json)
```

**Vertex AI (optional, have defaults):**
```
VERTEX_AI_SA_KEY=gemini-kr-sa-staging    # Key name inside credentials JSON file
VERTEX_AI_LOCATION=global                # Model location (global or us-central1)
```

**Models (optional, have defaults):**
```
MODEL_NAME=gemini-3-flash-preview        # Flash model for most queries
PRO_MODEL_NAME=gemini-3.1-pro-preview    # Pro model for reports/knowledge (leave empty to use Flash for all)
```

**Common optional:**
```
CHAT_HISTORY_DB=data/chat_history.db    # SQLite persistence (omit for in-memory only)
CONTEXT_CACHING_ENABLED=true            # Vertex AI context cache (requires versioned model name)

ORDER_SERVICE_BASE_URL
USER_SERVICE_BASE_URL
DRIVER_SERVICE_BASE_URL
COMMON_SERVICE_BASE_URL

# Indexer repo paths (not required at runtime)
ORDER_SERVICE_REPO_PATH
USER_SERVICE_REPO_PATH
DRIVER_SERVICE_REPO_PATH
COMMON_SERVICE_REPO_PATH
ADMIN_SERVICE_REPO_PATH
WEB2_REPO_PATH
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

Lives in `indexer/`. Parses Go (Gin routes + service flows), Java (Spring Boot enums/types), and React (API call graph) using tree-sitter AST + regex fallback. Services indexed: order-service, user-service, driver-service, common-service (Go); admin-service (Java); web2 (React).

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
