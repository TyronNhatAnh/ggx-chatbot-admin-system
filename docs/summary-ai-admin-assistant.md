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
- Max tool loop limit (`MAX_TOOL_LOOPS = 2`)
- Duplicate tool-call detection in one conversation turn
- Structured failure fallback when loop becomes repetitive
- Per-turn cache for `get_order` after `search_orders` results to avoid redundant HTTP calls

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

### Tools currently exposed to Gemini
- `get_order(order_id)`
- `search_orders(status)`
- `estimate_guest_price(payload)`
- `estimate_authenticated_price(payload)`
- `check_driver_price(payload)`
- `estimate_guest_home_moving_price(payload)`
- `get_driver(driver_id)`
- `list_active_drivers()`
- `get_order_summary()`
- `get_revenue_today()`

Note:
- `get_delayed_orders()` still exists in code but is intentionally not registered to Gemini because it duplicates `search_orders(status='Transit')` logic.

### Tool categories
- Order tools: real API-backed (read-only)
- Driver tools: mock in-memory dataset
- Analytics tools: mock aggregate values

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

## 7. Discovery and Documentation Context
This source already contains discovery artifacts for broader logistics domain understanding:
- Scan summary for this assistant service
- Scan summary for Order Service domain and APIs

These docs support the larger plan:
- Start from targeted function analysis (e.g., check-price/estimate paths)
- Expand to full Web2 FE + BE API mapping
- Consolidate requirements and business logic before scaling to full logistics system coverage

## 8. Gaps and Risks (Current)
- `/chat` endpoint still has no caller authentication/authorization
- No request-level rate limiting
- Test coverage is still narrow (mostly `/chat` API integration style tests)
- Driver and analytics tools still rely on mock data
- Conversation continuity exists but is process-local in-memory only (not shared across replicas/restarts)
- Observability is log-based only (no metrics/traces dashboard)

## 9. Recommended Next Steps
1. Add auth + rate limit for `/chat`.
2. Replace mock driver and analytics tools with real backend data sources.
3. Expand tests around orchestrator loop controls (duplicate calls, max-loop fallback, unknown tool handling).
4. Add request correlation ID and metrics (tool time, Gemini time, total time).
5. Move conversation context store to shared backing store (Redis/DB) for multi-instance stability.
6. Create formal API mapping docs for Web2 FE + BE flows and bind each flow to tool coverage.
