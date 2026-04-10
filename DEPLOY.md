
### Deployment checklist — AI Admin Assistant

|Service Name| Content  | From Infra Teams  |
|--|--|--|
| Routing | `/` (no path prefix — direct root access) | [ ] |
| Exposed Port | HTTP **8000** — FastAPI/uvicorn (no gRPC) | [ ] |
| Health Check | `:8000/health` — returns `{"status":"ok"}` | [ ] |
| Metrics | N/A — no metrics endpoint | [ ] |
| ENV | `CHAT_API_KEY`: Auth secret for `/chat` endpoint (**required**) <br> `VERTEX_AI_CREDENTIALS_FILE`: Path to Vertex AI SA credentials JSON (**required**) <br> `REDIS_URL`: Redis connection string for session persistence (e.g. `redis://redis-service:6379/0`) <br> `CHAT_AUTH_ENABLED`: Enable API key auth — default `true` <br> `MODEL_NAME` / `PRO_MODEL_NAME`: Gemini model names <br> `ORDER_SERVICE_BASE_URL`, `USER_SERVICE_BASE_URL`, `DRIVER_SERVICE_BASE_URL`, `COMMON_SERVICE_BASE_URL`: Downstream service URLs | [ ] |
| Dependencies | Redis (session store) — must be reachable via `REDIS_URL` | [ ] |
| Note | All routes require `X-API-Key` or `Authorization: Bearer <token>` header when `CHAT_AUTH_ENABLED=true`. The only unauthenticated endpoint is `GET /health`. | [ ] |
