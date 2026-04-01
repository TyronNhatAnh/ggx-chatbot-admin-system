# AI Admin Assistant

Read-only logistics admin assistant (Python 3.11). Never add create/update/delete actions.

## Common Commands

```bash
make install        # Create .venv + install requirements.txt
make deps           # Re-install deps into existing .venv
make run            # Start server at http://localhost:8000
make debug          # Auto-reload dev mode (uvicorn --reload)
make docker-run     # Run via Docker Compose
make index-all      # Index all services + cross-linker (reads *_REPO_PATH from .env)
make link           # Run cross-linker only (React API → Go handlers)
make seed-personas  # One-time: seed enum persona tags after re-indexing
make clean          # Delete .venv
```

**Indexing flags:** `FORCE=1 make index-all` bypasses incremental hash check and re-indexes all files.

**No test suite.** No `tests/` directory and no pytest configuration exist — do not look for or run tests.

## Architecture

| Layer | Path | Responsibility |
|---|---|---|
| HTTP | `app/main.py` | Transport, auth guard, rate limit |
| Orchestrator | `app/orchestrator/` | Prompt routing, tool loop, memory, summarization |
| LLM | `app/llm/` | Gemini API calls, Vertex AI context cache, credentials |
| Tools | `app/tools/` | Thin schema wrappers only |
| Services | `app/services/` | External API calls, auth, payload normalization |
| Prompts | `app/prompts/` | Prompt assembly (`builder.py`) |
| Persistence | `app/persistence/` | Optional SQLite session store (`CHAT_HISTORY_DB`) |
| Schemas | `app/schemas/` | Pydantic request/response models |
| Observability | `app/observability/` | Request ID context variable |
| Indexer | `indexer/` | Offline codebase indexer — do not modify for runtime bugs |

**Rules:** Never bypass orchestrator from routes. No business logic in tools/routes.

## API Contract (stable)

- `GET /health` — liveness probe
- `POST /chat` — request: `message` (required), `service_token` (required — admin bearer token forwarded to downstream services), `conversation_id` (optional); response: `reply`, `tools_called`, `conversation_id`
- `GET /history` — paginated conversation list; query params: `page` (default 1), `page_size` (default 20, max 100)
- `GET /history/{conversation_id}` — full turn history, summary, and long-term memory for a session
- Auth: `X-API-Key` or `Authorization: Bearer <token>` header (when `CHAT_AUTH_ENABLED=true`)
- Errors: `401` unauthorized · `422` validation · `429` rate-limit/quota · `500` internal

## Orchestrator

- `MAX_TOOL_LOOPS = 6` — do not change
- Suppress duplicate tool calls per turn; provide fallback reply on unproductive loops
- Conversation context: in-memory TTL 30 min (`SESSION_TTL_SECONDS = 1800`), process-local (`memory_service.py`)
- Optionally persisted to SQLite when `CHAT_HISTORY_DB` is set (`persistence/chat_store.py`)
- Token-budgeted context assembly with CJK-aware estimation (`context_builder.py`)
- 3-layer memory: `memory_service.py` (FACT / ENTITY / DECISION); short-term 5 turns (`SHORT_TERM_MAX_TURNS`), summarize every 5 new turns (`SUMMARIZE_THRESHOLD`)
- LLM thinking enabled on both models (`include_thoughts=True`); Flash capped at 8 000 thinking tokens, 4 096 output; Pro uncapped thinking, 8 192 output
- Pro model auto-selected for feature keys `report-summary` and `knowledge-code`; Flash used for all others
- `_sanitize_user_message()` strips prompt injection markers (`[Instruction:`, `[Today's date:`) before the LLM sees the input
- Conversation summarization: `summarizer.py`

## Prompts

- Entry point: `app/prompts/builder.py`
- Always loaded: `base/persona.md`, `base/safety.md`, `base/output-format.md`
- Feature prompts in `app/prompts/features/`: `order-lookup` · `report-summary` · `driver-tracking` · `user-admin` · `common-data` · `knowledge-code`
- Few-shot examples in `app/prompts/few-shots/`: `order-lookup`
- `app/orchestrator/prompt_builder.py` is a thin re-export only
- Prompt file inventory: see [docs/prompt-consolidation-map.md](../docs/prompt-consolidation-map.md)

## Tools

- 6 tool files: `order_tools.py` · `user_tools.py` · `driver_tools.py` · `common_tools.py` · `docs_tools.py` · `knowledge_tools.py` — 50 functions total
- Keep `ALL_TOOL_FUNCTIONS` and `TOOL_REGISTRY` in sync (`app/tools/__init__.py`); `_validate_unique_tool_names()` asserts uniqueness at startup
- `get_delayed_orders` stays unregistered (overlaps `get_orders_admin_panel(status_cd=[4])`)
- Summary tools → aggregate; Detail tools → per-order. Don't call both in one turn unless requested
- Knowledge/docs tools query `data/vectordb/` (ChromaDB) and `data/knowledge/` — read-only

## Auth & Security

- Service token cache: re-login only on missing/expired/401; one retry on `401`
- Reuse `httpx.Client` across requests in service clients
- Order service errors: `ORDER_NOT_FOUND` · `ORDER_SERVICE_ERROR` · `NETWORK_ERROR` · `UNEXPECTED_ERROR`
- User service errors: `USER_NOT_FOUND` · `USER_SERVICE_ERROR` · `NETWORK_ERROR` · `UNEXPECTED_ERROR`
- Never expose raw exceptions to tool/LLM layer; never hardcode secrets
- All service clients return `{"error": "ERROR_TYPE", ...}` dicts — never raise exceptions to the caller

## Code Style

- Type hints everywhere; small single-purpose functions
- Preserve existing logging style and tool signatures
- Config via `app/config.py` (pydantic-settings, loads `.env`); copy `.env.example` to `.env` to start
- `CONTEXT_CACHING_ENABLED=true` requires a **versioned** model name (e.g., `gemini-2.0-flash-001`), not aliases
- No heavy dependencies; minimal comments (non-obvious logic only)

## Persona

The assistant is always used by **admins**. "Persona" refers to the **data context** — which actor type an enum value or status belongs to, so the LLM can explain it in the right context.
- Data from Admin system → INTERNAL OPERATIONS perspective

## Change Discipline

Before finishing any update or fix:
1. **Check related files** — if you change a tool signature, param name, or add/remove a tool, update ALL of the following that reference it:
   - `app/prompts/features/*.md` (tool names, params, usage rules)
   - `app/tools/__init__.py` (`ALL_TOOL_FUNCTIONS` + `TOOL_REGISTRY`)
   - `app/services/` (matching service client method)
   - `.github/copilot-instructions.md` (architecture notes if affected)
2. **Cross-check prompt ↔ tool ↔ service** — every tool name in prompt files must exist in `ALL_TOOL_FUNCTIONS`; every param name in prompt files must match the actual function signature.
3. **Review, then finish** — do not mark a task done until the above cross-check passes.
