# AI Admin Assistant

Read-only AI chatbot service for internal logistics/admin operations, built with FastAPI and Google Gemini.

The assistant answers questions about orders, drivers, organizations, and indexed code knowledge by combining:
1. Live API tools (order-service, user-service)
2. Offline indexed code intelligence (docs + graph + semantic search)

## Current API Surface

- `GET /health`
- `POST /chat`
- `GET /history` — paginated conversation list (`page`, `page_size`)
- `GET /history/{conversation_id}` — full turn history, summary, and long-term memory

`/chat` response contract:

```json
{
  "reply": "...",
  "tools_called": ["get_order_detail"],
  "conversation_id": "..."
}
```

`/chat` request fields currently accepted by runtime:

```json
{
  "message": "required",
  "conversation_id": "optional",
  "service_token": "required (Bearer token for downstream services)"
}
```

## Runtime Guardrails

- API key authentication for `/chat`:
  - `X-API-Key: <key>`
  - or `Authorization: Bearer <chat-api-key>`
- In-memory fixed-window rate limiting (configurable)
- Explicit HTTP status mapping:
  - `422` validation errors
  - `429` Gemini quota / rate-limit errors
  - `500` internal server errors
- Tool loop protections in orchestrator:
  - `MAX_TOOL_LOOPS = 6`
  - duplicate tool-call suppression
  - fallback answer when loop becomes unproductive

## Architecture Overview

### System Layers

```
┌─────────────────────────────────────────────────────┐
│  Client (FDE / curl)                                │
└──────────────────┬──────────────────────────────────┘
                   │  POST /chat  (message, conversation_id, service_token)
┌──────────────────▼──────────────────────────────────┐
│  app/main.py  — FastAPI                             │
│  · Auth guard (X-API-Key / Bearer)                  │
│  · Fixed-window rate limiter (per IP)               │
│  · Request-ID injection + structured logging        │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  app/orchestrator/ai_orchestrator.py  (singleton)   │
│  · Feature detection → per-request system prompt    │
│  · Injects today's date + conversation context      │
│  · Gemini tool-calling loop (MAX_TOOL_LOOPS = 6)    │
│  · Parallel tool execution (ThreadPoolExecutor)     │
│  · Duplicate tool-call suppression                  │
│  · Synthesis fallback when loop exhausted           │
└──────┬──────────────────┬───────────────────────────┘
       │                  │
┌──────▼──────┐  ┌────────▼──────────────────────────┐
│ app/prompts │  │  app/llm/gemini_client.py          │
│ /builder.py │  │  · GeminiChatFactory               │
│             │  │  · Vertex AI (asia-northeast3)     │
│ base/       │  │  · Service account credentials     │
│  persona    │  │  · Optional context caching        │
│  safety     │  │    (system_instruction + tools     │
│  output-fmt │  │     cached per feature_key, 1h     │
│             │  │     TTL, ~75% token cost reduction)│
│ features/   │  └───────────────────────────────────┘
│  per-domain │
│ few-shots/  │
└─────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│  app/orchestrator/memory_service.py  (3-layer)      │
│                                                     │
│  Layer 1 — Short-term  (last 5 turns verbatim)      │
│  Layer 2 — Summary     (compressed by Gemini, ≤200w)│
│  Layer 3 — Long-term   (FACT / ENTITY / DECISION)   │
│            auto-extracted via regex (orderId, etc.) │
│                                                     │
│  Token budget: 8k total / 4.4k input; CJK-aware     │
│  Session TTL: 30 min inactivity                     │
│  Persistence: Redis (REDIS_URL); SQLite fallback (local dev) │
└──────┬──────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│  app/tools/  (38 registered tools)                  │
│                                                     │
│  order_tools.py   — orders, pricing, reports        │
│  user_tools.py    — users, orgs, branches, roles    │
│  driver_tools.py  — drivers, location, fares        │
│  common_tools.py  — vehicles, addresses, goods      │
│  docs_tools.py    — endpoint search + handler src   │
│  knowledge_tools.py — enums, structs, flows, graph  │
│                                                     │
│  JSON schemas auto-generated from Python signatures │
└──────┬──────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│  app/services/  (external API clients)              │
│                                                     │
│  OrderServiceClient  → stag-api.gogox.co.kr/order   │
│  UserServiceClient   → stag-api.gogox.co.kr/user    │
│  DriverServiceClient → stag-api.gogox.co.kr/driver  │
│  CommonServiceClient → stag-api.gogox.co.kr/common  │
│                                                     │
│  · Persistent httpx.Client (connection reuse)       │
│  · Request-scoped Bearer token (contextvars)        │
│  · One retry on 401                                 │
│  · Structured error returns (never raises to LLM)   │
└─────────────────────────────────────────────────────┘
```

### POST /chat — Full Request Flow

```
1. Auth + rate-limit guard
2. AIOrchestrator.chat(message, conversation_id?)
   a. Load/create SessionState from MemoryService
   b. Auto-extract entity IDs from message → long-term memory
   c. build_context() → summary + top-3 memory + last-5 turns (token-budgeted)
   d. Detect feature key → load modular system prompt
   e. Inject [Today's date] + report tool hints into message
   f. Gemini round 1: send_message(effective_message)
   ┌─ TOOL LOOP (repeat up to MAX_TOOL_LOOPS=6) ────────┐
   │  g. Extract function_calls from response            │
   │  h. Execute tools in parallel via ThreadPoolExecutor│
   │  i. Collect results + steering notes                │
   │  j. Gemini round N: send_message(results + notes)  │
   └─ Until: no function_calls in response ─────────────┘
   k. If loop exhausted: synthesis prompt or partial text
   l. Record user + assistant turns → summarize if needed
3. Return (reply, tools_called[], conversation_id)
```

### Persistence

```
app/persistence/redis_store.py  (enabled by REDIS_URL — preferred, multi-pod safe)
app/persistence/chat_store.py   (fallback when CHAT_HISTORY_DB is set — local dev only)
  SQLite — WAL mode, FK constraints
  ├── sessions    (session_id, summary, turns_since_summary, updated_at)
  ├── turns       (id, session_id, role, content, tools_called, tool_results, created_at)
  └── memory_items (id, session_id, type, content, created_at)
```

### Codebase Indexer Pipeline
### Refer from https://github.com/vitali87/code-graph-rag

```
Source repos (Go / Java / React)
       │
       ▼
indexer/parsers/{go,java,react}/
  ├── enum_extractor  → EnumGroup[]  (const blocks, iota, Java enums)
  ├── type_extractor  → StructDefinition[]  (struct fields, JSON tags)
  ├── flow_extractor  → ServiceFlow[]  (endpoint → handler → service → repo)
  └── route_extractor → Edge[]  (api_endpoint -handles→ handler)
       │
       ▼
indexer/store.py  →  data/knowledge/knowledge.db  (SQLite)
  ├── enums + enum_values  (with persona tag: customer/driver/admin)
  ├── struct_definitions + struct_fields
  ├── service_flows  (call chains)
  ├── code_chunks  (indexed fragments)
  ├── code_chunks_fts  (FTS5 full-text search)
  └── edges  (defines / calls / handles / calls_api / x_calls)
       │
       └──▶ indexer/linker.py  (cross-service pass)
              React calls_api edges  ╮
              Go handles edges       ╯  → match → x_calls edges
              (React component → Go handler, cross-service)
```

**Supported services & languages:**

| Service | Language | Extracts |
|---|---|---|
| order-service | Go | Enums, structs, Gin routes, service flows |
| user-service | Go | Enums, structs, Gin routes, service flows |
| driver-service | Go | Enums, structs, Gin routes, service flows |
| common-service | Go | Enums, structs, Gin routes, service flows |
| web-library | Java | Enums, types |
| admin-service | Java | Enums, types, Spring flows |
| web-api | Java | Enums, types, Spring flows |
| web2 | React/TS | API call graph (calls_api edges) |

**Knowledge tools query path:**

```
lookup_enum / explain_status  →  SQLite enums table  (exact + value match)
get_struct_definition         →  SQLite struct_definitions table
trace_service_flow            →  SQLite service_flows table
search_codebase               →  FTS5 full-text search (knowledge.db)
traverse_graph / find_api_consumers / trace_full_stack  →  SQLite edges table
search_endpoints / get_handler_context  →  SQLite code_chunks (handler source)
```

### Layering Rules

| Layer | Path | Rule |
|---|---|---|
| HTTP | `app/main.py` | Transport, auth, rate limit only — no business logic |
| Orchestrator | `app/orchestrator/` | All LLM logic, memory, routing — never bypass from routes |
| LLM | `app/llm/` | Gemini API calls only |
| Tools | `app/tools/` | Thin schema wrappers — no logic, no external calls |
| Services | `app/services/` | External API calls, auth, payload normalization |
| Prompts | `app/prompts/` | Prompt assembly only (`builder.py` entry point) |
| Indexer | `indexer/` | Offline pipeline — do not modify for runtime bugs |

## Setup

1. Clone and enter project

```bash
git clone <repo-url>
cd ai-admin-assistant
```

2. Configure environment

```bash
cp .env.example .env
```

Required keys (minimum):

```env
CHAT_API_KEY=replace-with-strong-random-secret
VERTEX_AI_CREDENTIALS_FILE=app/config/vertex-ai.json
```

Optional but commonly used:

```env
MODEL_NAME=gemini-3-flash-preview
PRO_MODEL_NAME=gemini-3.1-pro-preview
VERTEX_AI_SA_KEY=gemini-kr-sa-staging
VERTEX_AI_LOCATION=global
REDIS_URL=redis://localhost:6379/0
CHAT_AUTH_ENABLED=true
CHAT_RATE_LIMIT_ENABLED=true
CHAT_RATE_LIMIT_REQUESTS=30
CHAT_RATE_LIMIT_WINDOW_SECONDS=60
CONTEXT_CACHING_ENABLED=false
```

Indexer repo paths:

```env
ORDER_SERVICE_REPO_PATH=/path/to/ggx-kr-order-service
USER_SERVICE_REPO_PATH=/path/to/ggx-kr-user-service
DRIVER_SERVICE_REPO_PATH=/path/to/ggx-kr-driver-service
COMMON_SERVICE_REPO_PATH=/path/to/ggx-kr-common-service
WEB2_REPO_PATH=/path/to/ggx-kr-consumer-web
ADMIN_SERVICE_REPO_PATH=/path/to/ggx-kr-admin-service
```

3. Install dependencies

```bash
make install
```

## Run

```bash
make run
make debug
make docker-run
```

Server: `http://localhost:8000`
Swagger: `http://localhost:8000/docs`

## Tool Inventory (Current)

Total registered tools: **38**

- Order tools: 6
- User/admin tools: 12
- Common tools: 4
- Driver tools: 4
- Docs tools: 3
- Knowledge tools: 9

Important note:
- `get_delayed_orders` is intentionally not registered (overlaps `get_orders_admin_panel(status_cd=[4])`).

## Authentication Model

- `/chat` request must pass chat API key (header auth)
- `/chat.service_token` is forwarded to downstream order/user service calls
- No credential-based auto-login from environment

## Example Requests

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-strong-random-secret" \
  -d '{
    "message": "What is the status of order 12345?",
    "conversation_id": null,
    "service_token": "Bearer <admin-access-token>"
  }'
```

## Codebase Indexer

Indexer builds offline knowledge (SQLite + vector store) used by docs/knowledge tools.

**Parsing**: Go extractors use **tree-sitter** for robust AST-based parsing when installed, falling back to regex otherwise. Install `tree-sitter`, `tree-sitter-go`, and `tree-sitter-java` (already in `requirements.txt`).

**Incremental indexing**: The runner hashes all source files (SHA-256) and skips re-indexing when nothing has changed. Use `--force` to bypass the hash check.

**Embedding model**: Vector search is disabled — `data/knowledge/knowledge.db` uses FTS5 full-text search only.

Main commands:

```bash
make index-order-service
make index-user-service
make index-driver-service
make index-common-service
make index-web2
make index-service SERVICE_REPO=/path/to/repo SERVICE_NAME=my-service LANG=go
make index-admin-service
make link
make index-all
make seed-personas
```

`make index-all` runs order-service + web2 + user-service + driver-service + common-service indexing, then linker.

## Makefile Commands

| Command | Description |
|---|---|
| `make install` | Create venv and install dependencies |
| `make deps` | Reinstall dependencies into existing venv |
| `make run` | Run server |
| `make debug` | Run server with auto-reload |
| `make docker-run` | Run via Docker Compose |
| `make index-service` | Generic index entry point |
| `make index-order-service` | Index order-service repo |
| `make index-user-service` | Index user-service repo |
| `make index-driver-service` | Index driver-service repo |
| `make index-common-service` | Index common-service repo |
| `make index-admin-service` | Index admin-service repo (Java Spring Boot) |
| `make index-web2` | Index web2 repo |
| `make link` | Build cross-service endpoint links |
| `make index-all` | Run all configured indexers + linker (add `FORCE=1` to bypass incremental cache) |
| `make seed-personas` | Seed persona tags |
| `make clean` | Remove virtual environment |
