# AI Admin Assistant

Read-only AI chatbot service for internal logistics/admin operations, built with FastAPI and Google Gemini.

The assistant answers questions about orders, drivers, organizations, and indexed code knowledge by combining:
1. Live API tools (order-service, user-service)
2. Offline indexed code intelligence (docs + graph + semantic search)

## Current API Surface

- `GET /health`
- `POST /chat`

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
  - `MAX_TOOL_LOOPS = 3`
  - duplicate tool-call suppression
  - fallback answer when loop becomes unproductive

## High-Level Architecture

```text
POST /chat
  -> app/main.py
  -> app/orchestrator/ai_orchestrator.py
  -> app/prompts/builder.py (modular prompt assembly)
  -> app/llm/gemini_client.py
  -> app/tools/*.py (tool wrappers)
  -> app/services/*.py (external API integrations)
```

Layering rules:
- `app/main.py`: HTTP transport only
- `app/orchestrator/`: tool-calling loop + context + summarization
- `app/tools/`: thin function wrappers (schema from signatures/docstrings)
- `app/services/`: external API calls + auth + payload normalization

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
GEMINI_API_KEY=your-gemini-api-key
CHAT_API_KEY=replace-with-strong-random-secret
```

Optional but commonly used:

```env
MODEL_NAME=gemini-flash-latest
CHAT_AUTH_ENABLED=true
CHAT_RATE_LIMIT_ENABLED=true
CHAT_RATE_LIMIT_REQUESTS=30
CHAT_RATE_LIMIT_WINDOW_SECONDS=60
CHAT_ORDER_CACHE_TTL_SECONDS=60
COMMON_SERVICE_BASE_URL=https://stag-api.gogox.co.kr/common
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

Total registered tools: **50**

- Order/report tools: 18
- User/admin tools: 20
- Docs tools: 3
- Knowledge tools: 9

Important note:
- `get_delayed_orders` is intentionally not registered to avoid duplicate logical calls with `get_orders(status='Transit')`.

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
| `make index-all` | Run all configured indexers + linker |
| `make seed-personas` | Seed persona tags |
| `make clean` | Remove virtual environment |
