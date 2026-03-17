# AI Admin Assistant

A read-only AI chatbot service for admin systems, built with FastAPI and
Google Gemini. Operators can ask questions about orders, drivers, and system
analytics in plain English. The AI fetches real data through internal tools
and returns factual answers.

The system combines two knowledge sources:
1. **Live API calls** — real-time order/pricing data from backend services.
2. **Indexed codebase knowledge** — offline-extracted enums, structs, handler source code, API routes, and call graphs from Go and React repos.

---

## Architecture

```
POST /chat
    │
    ▼
app/main.py              ← FastAPI entry point
    │
    ▼
orchestrator/
  ai_orchestrator.py     ← tool-calling loop (send → detect → execute → reply)
  prompt_builder.py      ← system prompt (read-only rules)
    │
    ▼
llm/
  gemini_client.py       ← configures Gemini chat sessions (google.genai)
    │
    ▼
tools/
  order_tools.py         ← get_order, search_orders, estimate/check-price tools
  docs_tools.py          ← search_endpoints, get_handler_context
  knowledge_tools.py     ← enum lookup, flow trace, struct, graph traversal

  ┌─────────────────────────────────────────────────────┐
  │  Offline indexing pipeline (not part of /chat)      │
  │                                                     │
  │  indexer/                                           │
  │    runner.py         ← orchestrates 4-pass indexing │
  │    parsers/go/       ← Go enum/flow/type/route ext  │
  │    parsers/react/    ← React component/API parsers  │
  │    store.py          ← SQLite knowledge store       │
  │    vector_store.py   ← ChromaDB semantic search     │
  │    linker.py         ← cross-service endpoint match │
  └─────────────────────────────────────────────────────┘
```

---

## Setup

**1. Clone the repo and enter the directory**

```bash
git clone <repo-url>
cd ai-admin-assistant
```

**2. Create your `.env` file**

```bash
cp .env.example .env
```

Open `.env` and set your Gemini API key + chat secret:

```
GEMINI_API_KEY=your-gemini-api-key-here
CHAT_API_KEY=replace-with-strong-random-secret
```

For indexing, also set repo paths:

```
ORDER_SERVICE_REPO_PATH=/path/to/ggx-kr-order-service
USER_SERVICE_REPO_PATH=/path/to/ggx-kr-user-service
WEB2_REPO_PATH=/path/to/ggx-kr-consumer-web
```

Get a free Gemini key at <https://aistudio.google.com/app/apikey>.

**3. Install dependencies**

```bash
make install
```

---

## Running the server

```bash
make run          # Production mode
make debug        # Development mode (auto-reload)
make docker-run   # Docker
```

The server starts on `http://localhost:8000`. Swagger docs: `http://localhost:8000/docs`

---

## Codebase indexer

The indexer is the offline pipeline that reads Go and React source repos and extracts structured knowledge into a SQLite store + ChromaDB vector index. This knowledge powers the AI's ability to answer code/architecture questions at runtime.

### What gets extracted

| Entity | Go | React |
|---|---|---|
| Enums / const groups | ✅ | ✅ |
| Struct / interface definitions | ✅ | ✅ |
| Handler → service → repo flows | ✅ | Component → API call flows |
| HTTP routes (Gin router parsing) | ✅ | — |
| Handler source code (CodeChunks) | ✅ | — |
| Graph edges (calls, defines, handles) | ✅ | routes_to, calls_api, dispatches |
| Cross-service edges (x_calls) | — | Matched by linker |
| Vector embeddings (semantic search) | ✅ | ✅ |

### Index a new Go service (e.g. user-service)

**Step 1.** Add the repo path to `.env`:

```
USER_SERVICE_REPO_PATH=/path/to/ggx-kr-user-service
```

**Step 2.** Run the indexer:

```bash
make index-user-service
```

Or use the generic command for any service:

```bash
make index-service SERVICE_REPO=/path/to/repo SERVICE_NAME=my-service LANG=go
```

**Step 3.** Run the linker (matches React API calls → Go handlers across services):

```bash
make link
```

**Step 4.** (Optional) Seed persona tags after indexing order-service:

```bash
make seed-personas
```

### Full pipeline (all services + link)

```bash
make index-all
```

Reads `ORDER_SERVICE_REPO_PATH`, `WEB2_REPO_PATH`, `USER_SERVICE_REPO_PATH` from `.env` and runs:
order-service → web2 → user-service → linker.

### Adding a new pre-configured service shortcut

To add a new Makefile shortcut (e.g. `make index-driver-service`):

1. Add `DRIVER_SERVICE_REPO_PATH=/path/to/repo` to `.env` and `.env.example`
2. Add to Makefile:
   ```makefile
   index-driver-service:
   	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep DRIVER_SERVICE_REPO_PATH | cut -d= -f2)" --service driver-service --lang go --vectors
   ```
3. Add to `index-all` target if you want it included in the full pipeline.

---

## How tool calling works

The AI **never guesses** data. Gemini is given Python functions as "tools".
When the user asks a question requiring data, Gemini calls the appropriate tool,
the orchestrator executes it locally, and sends the result back to Gemini for
the final answer.

```
User:      "What is the status of order 12345?"
    │
    ▼
Gemini:    [tool call] get_order_detail(order_id="12345")
    │
    ▼
Orchestrator executes → returns order data
    │
    ▼
Gemini:    "Order 12345 is currently in Transit status."
```

---

## Available tools (42)

### Order tools — live API (10)

| Tool | Description |
|---|---|
| `get_order_detail(order_id)` | Fetch a single order by ID |
| `get_orders(status)` | Find orders by status |
| `get_order_payment_status(order_id)` | Payment status for an order |
| `get_order_cancel_fee(order_id)` | Cancel fee for an order |
| `get_order_statistics()` | Order counts grouped by status |
| `get_coupons()` | List available coupons |
| `estimate_guest_price(payload)` | Estimate price for guest flow |
| `estimate_authenticated_price(payload)` | Estimate price for authenticated flow |
| `check_driver_price(payload)` | Estimate price for a specific driver |
| `estimate_guest_home_moving_price(payload)` | Estimate guest home-moving price |

### User tools — live API (18)
### User tools — live API (20)

| Tool | Description |
|---|---|
| `get_withdraw_reasons()` | Get withdrawal reason list |
| `get_tos_contents()` | Get guest terms-of-service contents |
| `get_feature_flags()` | Get global feature flags |
| `get_my_feature_flags()` | Get feature flags for current authenticated user |
| `get_user_profile(user_id)` | Get user profile by ID (includes lastSignIn/lastAccessedAt when available) |
| `get_my_user_profile()` | Get current authenticated user profile (includes lastSignIn/lastAccessedAt when available) |
| `search_users(name, phone_number, email, page_index, page_size)` | Search users with paging |
| `get_user_driver(user_id)` | Get driver-linked user profile by user ID |
| `get_branch_by_id(branch_id)` | Get branch by ID |
| `search_branches(org_name, branch_name, page_index, page_size)` | Search branches |
| `get_organization_by_id(organization_id)` | Get organization by ID |
| `search_organizations(organization_name, division, page_index, page_size)` | Search organizations |
| `verify_client_token(token)` | Verify client token (read-only validation endpoint) |
| `list_admin_roles(department_id)` | List admin roles (optional department filter) |
| `list_admin_departments()` | List admin departments |
| `list_admin_menus()` | List admin menus |
| `get_admin_permissions(role_id)` | Get permissions by role |
| `get_accessible_menu_tree(role_id)` | Get accessible menu tree by role |
| `validate_b2c_org_code(org_code)` | Validate B2C organization code (B2B admin workflows) |
| `verify_biz_registration_number(biz_number, user_id)` | Verify business registration number (compliance audits) |

### Docs tools — indexed endpoint/handler knowledge (3)

| Tool | Description |
|---|---|
| `list_available_docs()` | List available handlers, endpoints, indexed services |
| `search_endpoints(keyword)` | Search BE endpoints by path/handler name |
| `get_handler_context(name)` | Get Go handler source code + endpoint + service calls |

### Knowledge tools — indexed codebase (9)

| Tool | Description |
|---|---|
| `lookup_enum(name)` | Look up enum/const definitions |
| `explain_status(code)` | Explain a numeric status code across all enums |
| `trace_service_flow(handler)` | Trace handler → service → repo call chain |
| `get_struct_definition(name)` | Look up Go struct fields and JSON tags |
| `search_codebase(query)` | Semantic + full-text code search |
| `traverse_graph(name, edge_types)` | Multi-hop graph traversal across code entities |
| `find_api_consumers(endpoint)` | Find React components calling an API endpoint |
| `trace_full_stack(endpoint)` | Full trace: React page → API → handler → service → repo |
| `get_knowledge_stats()` | Summary stats of indexed knowledge |

---

## Example API requests

```bash
# Query an order
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-strong-random-secret" \
  -d '{"message": "What is the status of order 12345?"}'

# Ask about code
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-strong-random-secret" \
  -d '{"message": "How does the EstimateGuest handler work?"}'

# Follow-up with conversation continuity
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-strong-random-secret" \
  -d '{"message":"What about its cancel fee?","conversation_id":"<id-from-previous-response>"}'
```

---

## Makefile commands

| Command | Description |
|---|---|
| `make install` | Create virtualenv and install dependencies |
| `make run` | Start the server |
| `make debug` | Start the server with hot-reload |
| `make docker-run` | Build and run with Docker Compose |
| `make index-order-service` | Index order-service |
| `make index-user-service` | Index user-service |
| `make index-web2` | Index web2 (React frontend) |
| `make index-service` | Index any service: `SERVICE_REPO=... SERVICE_NAME=... LANG=...` |
| `make link` | Run cross-service endpoint linker |
| `make index-all` | Index all configured services + link |
| `make seed-personas` | Seed persona tags on enums (after order-service index) |
| `make clean` | Remove the virtualenv |
