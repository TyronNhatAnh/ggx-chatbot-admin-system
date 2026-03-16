# AI Admin Assistant

A read-only AI chatbot service for admin systems, built with FastAPI and
Google Gemini. Operators can ask questions about orders, drivers, and system
analytics in plain English. The AI fetches real data through internal tools
and returns factual answers.

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
  driver_tools.py        ← get_driver, list_active_drivers
  analytics_tools.py     ← get_order_summary, get_revenue_today
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

Open `.env` and set your Gemini API key:

```
GEMINI_API_KEY=your-gemini-api-key-here
CHAT_API_KEY=replace-with-strong-random-secret
```

`/chat` is protected by API key auth and request rate limiting by default.
You can tune guardrails with:

```
CHAT_AUTH_ENABLED=true
CHAT_RATE_LIMIT_ENABLED=true
CHAT_RATE_LIMIT_REQUESTS=30
CHAT_RATE_LIMIT_WINDOW_SECONDS=60
CHAT_ORDER_CACHE_TTL_SECONDS=60
```

`/chat` also supports request correlation ID via `X-Request-ID`.
If provided, the same value is echoed back in the response header and appears in logs.

Get a free key at <https://aistudio.google.com/app/apikey>.

**3. Install dependencies**

```bash
make install
```

## Discovery And Feature Exploration

This repository has two different analysis workflows. They solve different jobs:

1. System discovery (broad inventory and mapping)

- Script: scripts/run_discovery.py
- Output:
  - docs/discovery/web2/fe_api_inventory.json
  - docs/discovery/order-services/be_endpoints.json
  - docs/discovery/order-services/code_context/*.context.md
  - docs/discovery/flow_mappings.json
- Use this when:
  - onboarding a new FE/BE repo
  - APIs changed a lot and baseline mapping is stale
  - you need broad FE -> BE coverage before choosing features

2. Feature exploration (deep requirement/spec for one feature)

- Script: scripts/explore_feature.py
- Input: explorer/feature_specs/<feature>.yaml
- Output: docs/features/<feature>/index.json and requirement.md
- Use this when:
  - you already know the feature scope
  - you need detailed use cases, endpoint contracts, and business rules

Current recommended path:

1. Run run_discovery only when baseline mapping is missing or outdated.
2. For day-to-day feature analysis, run explore_feature only.

### Strict Evidence Policy (Default)

Feature exploration enforces strict evidence only:

- No inference or assumptions in generated requirement/spec output.
- Every use case and endpoint must include evidence refs to matched source files.
- Missing evidence must be labeled as UNKNOWN/evidence_gap.
- Invalid output is rejected and written to error artifacts, not to final docs.

Run feature exploration:

```bash
. .venv/bin/activate
python scripts/explore_feature.py --spec explorer/feature_specs/check_price.yaml
```

Simplest workflows:

```bash
# 1) Interactive menu: choose existing spec or describe new feature
python scripts/explore_feature.py --interactive

# 2) One-line feature text: auto-create spec and run
python scripts/explore_feature.py --feature "check price for guest and home moving"

# 3) One-shot full auto (recommended for minimal manual steps):
#    - runs discovery scan-all
#    - auto-builds and Gemini-enriches feature spec
#    - runs explore and writes docs/features/<feature>/...
python scripts/explore_feature.py --full-auto --feature "login base"
```

Use template for new features:

- Spec template: explorer/feature_specs/_template.yaml
- Authoring guide: docs/features/README.md

---

## Running the server

**Production mode**

```bash
make run
```

**Development mode** (auto-reload on file save)

```bash
make debug
```

**Docker**

```bash
make docker-run
```

The server starts on `http://localhost:8000`.

Interactive Swagger docs: `http://localhost:8000/docs`

---

## How tool calling works

The AI **never guesses** data. Instead, Gemini is given a set of Python
functions as "tools". When the user asks a question that requires data, Gemini
decides which tool to call and with what arguments. The orchestrator executes
the function locally and sends the result back to Gemini, which then produces
the final response.

```
User:      "What is the status of order ORD-002?"
    │
    ▼
Gemini:    [tool call] get_order(order_id="ORD-002")
    │
    ▼
Orchestrator executes: get_order("ORD-002")
    │  returns: {"id": "ORD-002", "status": "pending", ...}
    │
    ▼
Gemini:    "Order ORD-002 is currently pending."
    │
    ▼
User:      receives final answer
```

This loop repeats until Gemini produces a plain-text answer with no further
tool calls. The system prompt enforces that the AI never modifies data.

---

## Available tools

| Tool | Description |
|---|---|
| `get_order(order_id)` | Fetch a single order by ID |
| `search_orders(status)` | Find all orders with a given status |
| `estimate_guest_price(payload)` | Estimate new order price for guest flow |
| `estimate_authenticated_price(payload)` | Estimate new order price for authenticated flow |
| `check_driver_price(payload)` | Estimate price for a specific driver |
| `estimate_guest_home_moving_price(payload)` | Estimate guest home-moving order price |
| `get_driver(driver_id)` | Fetch a single driver by ID |
| `list_active_drivers()` | List all currently active drivers |
| `get_order_summary()` | Order counts grouped by status |
| `get_revenue_today()` | Revenue total from today's delivered orders |

---

## Example API requests

**Query an order**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-strong-random-secret" \
  -H "X-Request-ID: req-demo-001" \
  -d '{"message": "What is the status of order ORD-002?"}'
```

### Structured metrics in logs

For each `/chat` request, orchestrator emits one structured metrics log event containing:

- `gemini` latency (seconds)
- `tools` latency (seconds)
- `total` latency (seconds)
- `tool_call_count` and `tool_unique_count`
- fallback reason and cumulative fallback counters

```json
{
  "reply": "Order ORD-002 is currently pending. It is for Wireless Headphones ordered by Bob Tan, totalling $199.99.",
  "tools_called": ["get_order"],
  "conversation_id": "0f1f10df-77c5-498b-90be-7eb58f49fe17"
}
```

### Conversation continuity

You can send `conversation_id` in follow-up `/chat` requests to keep short context
across turns.

Example:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-strong-random-secret" \
  -d '{"message":"What about its driver fee?","conversation_id":"0f1f10df-77c5-498b-90be-7eb58f49fe17"}'
```

**Find delayed orders**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-strong-random-secret" \
  -d '{"message": "Are there any delayed orders?"}'
```

**Get a driver**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-strong-random-secret" \
  -d '{"message": "Tell me about driver DRV-001"}'
```

---

## Makefile commands

| Command | Description |
|---|---|
| `make install` | Create virtualenv and install dependencies |
| `make run` | Start the server |
| `make debug` | Start the server with hot-reload |
| `make docker-run` | Build and run with Docker Compose |
| `make clean` | Remove the virtualenv |
