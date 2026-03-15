---
description: "Workspace coding rules for AI Admin Assistant (FastAPI + Gemini tool-calling). Use when editing API, orchestrator, tools, prompts, or service clients."
applyTo: "**/*.py"
---

# AI Admin Assistant - Copilot Instructions

## Product intent
- This service is a read-only logistics admin assistant.
- Never introduce create/update/delete business actions.
- Favor factual, concise responses and deterministic behavior.

## Architecture constraints
- Keep clear boundaries:
  - `app/main.py`: transport/API layer only.
  - `app/orchestrator/`: LLM tool-calling loop and control flow.
  - `app/tools/`: thin tool wrappers only.
  - `app/services/`: external API integration, auth, payload normalization.
- Do not bypass the orchestrator by calling services directly from API routes.

## Performance rules (high priority)
- Optimize for end-to-end latency target: 3-6 seconds per `/chat` request.
- Minimize Gemini round-trips:
  - Prefer one search tool call + one final generation.
  - Avoid tool duplication and repeated equivalent queries.
- Keep tool payloads small:
  - Return only fields required for user-facing answers.
  - Always slim nested objects (`fromPlace`, `toPlace`, `driver`, `payment`) to compact shape.
  - Use list limits (`pageSize`, slices) to cap token volume.
- When changing prompts, prioritize tool selection efficiency over verbosity.

## Tool-calling safety rules
- Never add two tools that represent the same logical query unless strongly justified.
- If a tool fails, surface the error clearly; do not blindly retry with unrelated tools.
- Keep loop protection in place (`MAX_TOOL_LOOPS`, duplicate-call detection).
- Preserve deterministic ordering and stable JSON keys where practical.

## Auth and external API rules
- Keep token caching behavior:
  - Re-login only when token is missing, expired, or invalidated by 401.
- Reuse HTTP connections (`httpx.Client`) for service clients.
- Handle external errors with structured responses:
  - `ORDER_NOT_FOUND`, `NETWORK_ERROR`, `ORDER_SERVICE_ERROR`, `UNEXPECTED_ERROR`.
- Avoid raising raw service exceptions to tool/LLM layer.

## Security and secrets
- Never hardcode secrets, credentials, API keys, or tokens.
- Treat `.env` as sensitive local-only data.
- Do not log passwords or raw auth tokens.

## API behavior and error mapping
- Keep `/chat` responses stable: `{ reply, tools_called }`.
- Use explicit HTTP status mapping:
  - Validation issues -> 422
  - Quota/rate limit issues -> 429
  - Internal failures -> 500
- Prefer user-safe error messages; avoid leaking stack traces.

## Coding style for this repo
- Python 3.11 style with type hints.
- Keep functions small and single-purpose.
- Add comments only for non-obvious logic.
- Preserve existing logging style and prefixes.
- Do not introduce heavy dependencies unless necessary.

## Test and verification expectations
- After changes, verify no type/lint/runtime errors in touched files.
- For latency-related changes, include before/after timing notes when available.
- Avoid behavior regressions in tool contracts and response schema.

## Non-goals
- Do not redesign the entire stack.
- Do not add mock-only features to production paths.
- Do not add broad prompt text that increases token usage without clear value.
- Strict evidence only 