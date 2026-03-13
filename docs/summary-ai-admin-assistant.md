# AI Admin Assistant Codebase Summary

## 1. System Overview
This repository is a read-only AI admin assistant service built with FastAPI and Google Gemini.

It provides a chat endpoint that answers logistics-related operational questions by calling internal tools for:
- Order lookup and filtering
- Driver lookup and listing
- Basic analytics summaries

Current implementation is demo/MVP style:
- Uses in-memory mock datasets and hardcoded analytics values
- No database integration
- No state persisted across restarts

## 2. Core Features Implemented

### Read-Only AI Assistant Behavior
The system prompt enforces strict read-only behavior:
- No create/update/delete actions
- Must use tools for factual data retrieval
- Must not guess missing data
- Must report tool errors clearly

### Tool-Calling Orchestration
The orchestrator runs a function-calling loop:
1. Receive user message
2. Send to Gemini model configured with tools
3. Detect requested function calls
4. Execute local Python tool functions
5. Send function outputs back to Gemini
6. Repeat until final text answer is generated

### Exposed API Endpoints
- `GET /health`
  - Liveness check
  - Returns: `{ "status": "ok" }`

- `POST /chat`
  - Accepts: `{ "message": "..." }`
  - Returns: `{ "reply": "...", "tools_called": ["..."] }`

## 3. Tool Capabilities

### Order Tools
- `get_order(order_id)`
  - Returns a single order by ID
  - Returns error payload if not found

- `search_orders(status)`
  - Returns list of orders by status and count

- `get_delayed_orders()`
  - Returns delayed orders and count

### Driver Tools
- `get_driver(driver_id)`
  - Returns a single driver by ID (case-insensitive)
  - Returns error payload if not found

- `list_active_drivers()`
  - Returns active drivers and count

### Analytics Tools
- `get_order_summary()`
  - Returns order totals by status

- `get_revenue_today()`
  - Returns today's revenue summary

## 4. Data and Domain State
There is no persistent domain model layer in this repo.

Current sources of truth:
- `MOCK_ORDERS` dictionary in order tools
- `MOCK_DRIVERS` dictionary in driver tools
- Hardcoded aggregate values in analytics tools

Implications:
- Data resets on process restart
- No shared consistency between multiple running instances
- Not suitable for production analytics without real data source integration

## 5. Architecture Components
- `app/main.py`
  - FastAPI app and route definitions

- `app/orchestrator/ai_orchestrator.py`
  - Chat loop and tool execution lifecycle

- `app/orchestrator/prompt_builder.py`
  - System prompt with read-only constraints

- `app/llm/gemini_client.py`
  - Gemini model creation and tool registration

- `app/tools/*`
  - Business-facing retrieval tools exposed to model

- `app/schemas/chat_schema.py`
  - Request/response contracts for `/chat`

- `app/config.py`
  - Environment-backed settings

## 6. Configuration and Runtime
Environment variables:
- `GEMINI_API_KEY` (required)
- `MODEL_NAME` (optional; default exists in app config)

Dependencies:
- FastAPI, Uvicorn, Pydantic, pydantic-settings
- google-generativeai
- python-dotenv

Run options:
- Local via Makefile (`make run`, `make debug`)
- Docker image via Dockerfile
- Docker Compose for local containerized dev

## 7. Current Gaps and Limitations
Not currently implemented:
- Authentication and authorization
- Rate limiting and abuse protection
- Database/repository layer
- Test suite
- Structured observability (metrics/tracing)
- Multi-turn conversation memory between requests

## 8. Recommended Next Improvements
1. Add API authentication and rate limiting for `/chat`.
2. Replace mock datasets with real storage/services.
3. Add unit tests for tools and integration tests for `/chat` loop.
4. Improve API error mapping with explicit status codes and error schema.
5. Add request IDs, structured logs, and basic metrics.
6. Derive analytics from the same order data source to avoid drift.
