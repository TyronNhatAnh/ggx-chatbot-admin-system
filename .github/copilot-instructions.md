---
description: "Single source of truth for AI Admin Assistant context (architecture, runtime behavior, tools, constraints, roadmap). Use for all code changes in this workspace."
applyTo: "**/*.py"
---

# AI Admin Assistant - Copilot Instructions

## Product intent
- This service is a read-only logistics admin assistant.
- Never introduce create/update/delete business actions.
- Favor factual, concise responses and deterministic behavior.

## Current system snapshot (March 2026)
- API surface: `GET /health`, `POST /chat`.
- `/chat` schema is stable:
  - Input: `message` (required), `conversation_id` (optional)
  - Output: `reply`, `tools_called`, `conversation_id`
- Runtime guardrails already in place:
  - API key auth (`x-api-key` or Bearer)
  - Configurable in-memory fixed-window rate limiting
  - Validation error mapping (422), Gemini quota mapping (429), internal errors (500)
- Orchestrator loop controls:
  - `MAX_TOOL_LOOPS = 3`
  - Duplicate tool-call suppression per turn
  - Fallback reply when loop becomes unproductive
- Context continuity:
  - Conversation state is in-memory with TTL (process-local only)
  - Not shared across multi-instance deployments
- Prompt architecture:
  - Modular prompt assembly in `app/prompts/builder.py`
  - Base prompts always loaded: persona, safety, output-format
  - Feature prompt selected by keyword routing in orchestrator
- Observability:
  - Request correlation ID logging
  - Structured latency metrics (Gemini/tool/total, tool counts)

## Runtime architecture (must preserve)
- Layer boundaries are strict:
  - `app/main.py`: transport + HTTP concerns only
  - `app/orchestrator/`: tool-calling loop, context, summarization, prompt selection
  - `app/tools/`: thin wrappers; signatures/docstrings define tool schemas
  - `app/services/`: external API calls, auth handling, payload normalization/slimming
- Do not bypass orchestrator from API routes.
- Do not embed service/business logic in tools or API layer.

## System personas and applications

### Frontend applications
- **web2**: consumer/customer web application (React) — CUSTOMER perspective.
- **driver app**: used by delivery drivers — DRIVER perspective.
- **admin system**: used by internal operators — INTERNAL OPERATIONS perspective.

### Backend services
- **order-service** (Go)
- **admin-service** (Java)
- **driver-service** (Go)
- **user-service** (Go)
- **common-service** (Go)
- **notification-service** (Go)
- **report-service** (Go)
- _(more services to be added)_

### Persona rules
- web2 = CUSTOMER perspective.
- Driver applications = DRIVER perspective.
- Admin tools = INTERNAL OPERATIONS perspective.
- When answering questions about UI or behavior, identify which persona the question refers to.
- If the persona is unclear, ask the user to clarify.

## Tooling inventory (current)

### Order/report tools (live API-backed)
- `get_order_detail`, `get_orders`, `get_order_payment_status`, `get_order_cancel_fee`
- `get_order_statistics` (per-user scope, not full-system aggregate)
- `get_statement_of_use_summary`, `get_statement_of_use_detail`
- `get_statement_of_use_driver_summary`, `get_statement_of_use_driver_detail`
- `get_b2b_tracking_service_detail`, `get_coupons`
- Pricing: `estimate_guest_price`, `estimate_authenticated_price`, `check_driver_price`, `estimate_guest_home_moving_price`
- Route/reorder: `get_order_route`, `get_order_shipping_records`, `get_order_reorder_info`

### User/admin tools (live API-backed)
- User profile/search: `get_user_profile`, `get_my_user_profile`, `search_users`, `get_user_driver`
- Org/branch: `get_organization_by_id`, `search_organizations`, `get_branch_by_id`, `search_branches`
- Admin RBAC/menu: `list_admin_roles`, `list_admin_departments`, `list_admin_menus`, `get_admin_permissions`, `get_accessible_menu_tree`
- Validation/reference: `verify_client_token`, `validate_b2c_org_code`, `verify_biz_registration_number`, `get_withdraw_reasons`, `get_tos_contents`, `get_feature_flags`, `get_my_feature_flags`

### Docs + knowledge tools (indexed codebase)
- Docs tools: `list_available_docs`, `search_endpoints`, `get_handler_context`
- Knowledge tools: `lookup_enum`, `explain_status`, `trace_service_flow`, `get_struct_definition`, `search_codebase`, `traverse_graph`, `find_api_consumers`, `trace_full_stack`, `get_knowledge_stats`

### Tooling notes
- Keep `ALL_TOOL_FUNCTIONS` and `TOOL_REGISTRY` aligned.
- `get_delayed_orders` is intentionally not registered (duplicates `get_orders(status='Transit')` behavior and can trigger duplicate calls).
- Do not add overlapping tools for the same logical query unless strictly necessary.

## Architecture constraints
- Keep strict boundaries and current modular prompt structure.
- Prompt sources:
  - `app/prompts/base/persona.md`
  - `app/prompts/base/safety.md`
  - `app/prompts/base/output-format.md`
  - `app/prompts/features/*.md` selected by feature routing
- `app/orchestrator/prompt_builder.py` is a thin re-export; prompt content lives in `app/prompts/`.

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
- Preserve report argument sanitization behavior: do not carry stale date ranges across turns when user did not specify date intent in current message.

## Tool-calling safety rules
- Never add two tools that represent the same logical query unless strongly justified.
- If a tool fails, surface the error clearly; do not blindly retry with unrelated tools.
- Keep loop protection in place (`MAX_TOOL_LOOPS`, duplicate-call detection).
- Preserve deterministic ordering and stable JSON keys where practical.
- Respect summary vs detail report tool semantics:
  - Summary tools for aggregate views
  - Detail tools for per-order/orderId views
  - Do not call both in one turn unless user explicitly asks for both

## Auth and external API rules
- Keep token caching behavior:
  - Re-login only when token is missing, expired, or invalidated by 401.
- Reuse HTTP connections (`httpx.Client`) for service clients.
- Handle external errors with structured responses:
  - `ORDER_NOT_FOUND`, `NETWORK_ERROR`, `ORDER_SERVICE_ERROR`, `UNEXPECTED_ERROR`.
- Avoid raising raw service exceptions to tool/LLM layer.
- Keep one-retry-on-401 behavior where already implemented.

## Security and secrets
- Never hardcode secrets, credentials, API keys, or tokens.
- Treat `.env` as sensitive local-only data.
- Do not log passwords or raw auth tokens.

## API behavior and error mapping
- Keep `/chat` responses stable: `{ reply, tools_called, conversation_id }`.
- Use explicit HTTP status mapping:
  - Validation issues -> 422
  - Quota/rate limit issues -> 429
  - Internal failures -> 500
- Prefer user-safe error messages; avoid leaking stack traces.

## Indexer and knowledge-system context
- Knowledge stack is offline-index-first:
  - SQLite store (FTS + graph edges)
  - Vector store (semantic retrieval)
- Current known indexed domains include `order-service`, `web2`, and user-service support.
- Docs/knowledge tools must read from indexer store abstractions, not ad-hoc filesystem crawling.

## Coding style for this repo
- Python 3.11 style with type hints.
- Keep functions small and single-purpose.
- Add comments only for non-obvious logic.
- Preserve existing logging style and prefixes.
- Do not introduce heavy dependencies unless necessary.
- Preserve stable tool function signatures when possible (Gemini schema compatibility).

## Test and verification expectations
- After changes, verify no type/lint/runtime errors in touched files.
- For latency-related changes, include before/after timing notes when available.
- Avoid behavior regressions in tool contracts and response schema.
- For orchestrator changes, prioritize regression checks for:
  - duplicate tool-call suppression
  - max-loop fallback behavior
  - unknown-tool handling
  - conversation context continuity behavior

## Current risks and roadmap anchors
- Process-local memory only (no shared backing store yet).
- Test depth still behind orchestrator complexity.
- Some service coverage is still expanding (admin-service parsing, broader cross-service links).
- Prefer implementing from existing backlog docs:
  - `docs/chat-api-deep-audit.md`
  - `docs/plan-checklist.md`
  - `docs/summary-ai-admin-assistant.md`

## Non-goals
- Do not redesign the entire stack.
- Do not add mock-only features to production paths.
- Do not add broad prompt text that increases token usage without clear value.
- Strict evidence only 