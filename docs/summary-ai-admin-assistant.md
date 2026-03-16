# AI Admin Assistant Codebase Summary (Current State)

## 1. System Overview
This repository is a read-only AI admin assistant service built with FastAPI and Gemini tool-calling.

Main capability:
- Accept natural-language admin questions via `/chat`
- Use tool-calling to query logistics data
- Return concise factual responses with a list of tools used

Current direction is no longer pure demo-only. The order query path is already integrated to real backend APIs (User Service + Order Service), while some tools are still mock.

## 2. Current Runtime Flow
1. API receives chat message.
2. Orchestrator sends message to Gemini model with registered tools.
3. Gemini requests tool calls.
4. Tool layer executes wrappers.
5. Service layer calls external APIs with token auth and normalized payloads.
6. Orchestrator sends tool results back to Gemini and returns final answer.

Important protections in current flow:
- Max tool loop limit (`MAX_TOOL_LOOPS = 3`)
- Duplicate tool-call detection in one conversation turn
- Structured failure fallback when loop becomes repetitive
- Per-turn cache for `get_order` after `search_orders` results to avoid redundant HTTP calls
- Auth + API key guard on `/chat` endpoint
- Request rate limiting (configurable via .env)

## 3. Implemented APIs
- `GET /health`
  - Liveness check
  - Returns `{ "status": "ok" }`

- `POST /chat`
  - Input: `{ "message": "...", "conversation_id": "optional" }`
  - Output: `{ "reply": "...", "tools_called": ["..."], "conversation_id": "..." }`
  - Validation: message min/max length enforced
  - Error mapping includes Gemini quota exhaustion -> HTTP 429

## 4. Tooling Status (Actual)

### Order tools (live API-backed)
- `get_order_detail(order_id)` — fetch single order
- `get_orders(status)` — search orders by status
- `get_order_payment_status(order_id)` — payment status
- `get_order_cancel_fee(order_id)` — cancel fee lookup
- `get_order_statistics()` — order counts by status
- `get_coupons()` — available coupons
- `estimate_guest_price(payload)` — guest price estimate
- `estimate_authenticated_price(payload)` — auth price estimate
- `check_driver_price(payload)` — driver price estimate
- `estimate_guest_home_moving_price(payload)` — home moving estimate

### Discovery docs tools (reads from docs/discovery/)
- `list_available_docs()` — list discovery directories
- `search_endpoints(keyword)` — search BE endpoints by path/handler
- `get_handler_context(name)` — Go handler source code snippet
- `get_feature_requirement(name)` — feature requirement docs

### Knowledge tools (reads from SQLite + ChromaDB)
- `lookup_enum(name)` — enum/const lookup
- `explain_status(code)` — explain numeric status code (persona-aware)
- `trace_service_flow(handler)` — handler → service → repo chain
- `get_struct_definition(name)` — struct fields + JSON tags
- `search_codebase(query)` — semantic + FTS code search
- `traverse_graph(name, edge_types)` — multi-hop graph traversal
- `find_api_consumers(endpoint)` — React components calling an API
- `trace_full_stack(endpoint)` — React → API → handler → service → repo
- `get_knowledge_stats()` — indexed knowledge summary

### Tool categories
- Order tools: real API-backed (read-only)
- Docs tools: reads pre-generated discovery docs (markdown/JSON)
- Knowledge tools: queries indexed knowledge store (SQLite + ChromaDB vector search)

## 5. Service Integration State

### Auth token manager
- Login endpoint integration implemented (`/api/v1/auth/login`)
- In-memory token cache with TTL
- Re-login only when token missing/expired or invalidated by 401

### Order service client
- Uses persistent `httpx.Client` connection reuse
- Handles 401 retry once with token refresh
- Returns structured error contracts:
  - `ORDER_NOT_FOUND`
  - `NETWORK_ERROR`
  - `ORDER_SERVICE_ERROR`
  - `UNEXPECTED_ERROR`
- Payload slimming is implemented to reduce LLM token load (`fromPlace`, `toPlace`, `driver`, payment fields)

## 6. Performance and Reliability Snapshot
Observed improvements compared to earlier runs:
- Reduced duplicate tool calls
- Reduced multi-round tool-calling loops
- Lower end-to-end response time for common query patterns

Remaining practical bottlenecks:
- First request after process startup still includes login latency (expected behavior)
- Gemini latency/quota still dominates tail latency in free-tier or constrained quota scenarios

## 7. Codebase Indexer & Knowledge Store

Offline pipeline that extracts structured knowledge from Go and React repos.

### Pipeline
1. `indexer/runner.py` — 4-pass extract: enums → types → flows → graph edges
2. `indexer/parsers/go/` — Go parser (handler chains, enums, structs)
3. `indexer/parsers/react/` — React parser (components, API calls, routes)
4. `indexer/linker.py` — matches React API calls → Go handlers across services
5. `indexer/store.py` — SQLite knowledge store (FTS5 + graph edges)
6. `indexer/vector_store.py` — ChromaDB semantic embeddings

### Current indexed services
- `order-service` (Go) — 104 enums, 531 structs, 182 flows
- `web2` (React) — 30 enums, 217 types, 85 flows, 391 edges

### Graph edges (598 total)
- `defines` (337): file → function/component
- `handles` (113): API endpoint → Go handler
- `calls` (42): handler → service method
- `calls_api` (42): React component → API endpoint
- `exposes_api` (41): API module method → endpoint
- `routes_to` (12): Next.js route → component
- `x_calls` (11): React component → Go handler (cross-service)

### Integration with explorer/
The indexer runs explorer modules via `--docs` flag to regenerate
`be_endpoints.json` and `*.context.md` for Go services.
Explorer docs provide handler source code; indexer provides queryable graph.

## 8. Gaps and Risks (Current)
- Test coverage is still narrow (mostly `/chat` API integration style tests)
- Driver and analytics tools were removed (previously mock); not yet replaced
- Conversation continuity exists but is process-local in-memory only (not shared across replicas/restarts)
- Observability is log-based only (no metrics/traces dashboard)
- Cross-service links limited to order-service + web2 (15 FE endpoints unmatched — need user-service, common-service indexed)

## 9. Recommended Next Steps
1. Index user-service and common-service to expand cross-service coverage.
2. Replace mock driver and analytics tools with real backend data sources.
3. Expand tests around orchestrator loop controls (duplicate calls, max-loop fallback, unknown tool handling).
4. Move conversation context store to shared backing store (Redis/DB) for multi-instance stability.
5. Add observability (structured metrics, traces) beyond log-based monitoring.
