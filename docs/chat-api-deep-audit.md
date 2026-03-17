# /chat API Deep Audit (2026-03-16)

## Scope
- Endpoint: `POST /chat`
- Layers reviewed:
  - API transport: `app/main.py`
  - Request/response schema: `app/schemas/chat_schema.py`
  - Orchestration loop and context: `app/orchestrator/ai_orchestrator.py`, `app/orchestrator/context_store.py`, `app/orchestrator/prompt_builder.py`
  - Tool registry and tool contracts: `app/tools/__init__.py`, `app/tools/order_tools.py`
  - Existing tests and docs: `tests/test_chat_pricing_integration.py`, `README.md`, `docs/summary-ai-admin-assistant.md`, `docs/plan-checklist.md`

## Executive Summary
- `/chat` implementation is functionally solid for core read-only behavior: validation, tool-calling loop controls, duplicate call suppression, quota mapping, and compact context continuity.
- Documentation drift is material: response schema, tool inventory, and loop limit were out of date.
- Test coverage exists but remains shallow relative to orchestrator complexity.
- Primary production risks remain security and operability: no endpoint auth/rate limit, in-memory-only conversation state, and metrics gap.

## What Is Implemented Well
- Strong request validation via Pydantic (`message` and optional `conversation_id`).
- Deterministic tool-calling safeguards:
  - duplicate tool call suppression by `(tool_name, sorted_args_json)` key
  - max loop guard with user-safe fallback
  - early return when no new tool responses are available
- Payload efficiency controls:
  - search result enrichment note to reduce unnecessary `get_order`
  - per-turn order cache to skip redundant order detail calls
- Error handling:
  - Gemini quota/resource-exhausted mapped to HTTP 429
  - unknown tool requests fail fast with clear error intent

## Findings (Prioritized)

### High
1. ~~Missing caller auth on `/chat`~~ — RESOLVED: API key auth added.

2. ~~No request-level rate limiting~~ — RESOLVED: Configurable rate limiting added.

### Medium
3. Conversation memory is process-local only
- Current behavior: context store is in-memory with TTL and max turns.
- Impact: continuity breaks across restarts/multi-instance deployments.
- Recommendation: optional shared store (Redis) for production continuity.

4. ~~Observability is log-centric, not metrics-centric~~ — PARTIALLY RESOLVED: Structured metrics (model/tool/total latency, tool counts) now emitted per request.

5. Test depth does not match orchestration complexity
- Current behavior: API tests cover basic pricing routing and quota mapping.
- Impact: regressions in loop guard and duplicate suppression can slip.
- Recommendation: add orchestrator-focused tests for max-loop, duplicate-call suppression, unknown tool, and context truncation.

### Low
6. Prompt/tool guidance and docs can diverge over time
- Current behavior: prompt references tool behavior details that may evolve quickly.
- Impact: stale docs lead to incorrect operational assumptions.
- Recommendation: add a lightweight docs sync checklist per tool registry change.

## Docs and Plan Delta (Before -> After)

### README
- Corrected exposed tool list (removed non-registered `get_delayed_orders`, added estimate/check-price tools).
- Updated sample `/chat` response to include `conversation_id`.
- Added follow-up request example with `conversation_id` for continuity.

### docs/summary-ai-admin-assistant.md
- Corrected `MAX_TOOL_LOOPS` value (`2` not `3`).
- Updated `/chat` input/output schema to include `conversation_id`.
- Updated tool inventory with pricing-related tools.
- Corrected testing statement from "no test suite" to "basic coverage exists, depth still insufficient".
- Corrected context statement from "no persistent state" to "process-local continuity only".

### docs/plan-checklist.md
- Marked basic `/chat` integration tests as completed.
- Split remaining testing item into depth expansion goals.
- Added hardening tasks from this audit (correlation ID logging, timeout/retry guardrails, duplicate/max-loop regression tests).
- Added explicit reference to this audit file as `/chat` hardening backlog seed.

## Recommended Execution Plan (Next 2 Sprints)

### Sprint 1 (Security + Reliability Baseline)
1. Add auth guard for `/chat` (gateway token or API key/JWT).
2. Add rate limiting (client + global).
3. Add request correlation ID propagation in logs.
4. Add orchestrator regression tests:
   - duplicate call suppression
   - max-loop fallback
   - unknown-tool error path

### Sprint 2 (Operability + Scale Readiness)
1. Add metrics/tracing for model/tool/total latency and loop counts.
2. Move conversation store to optional Redis backend.
3. Add dashboard + alert thresholds (429 rate, p95 latency, fallback frequency).
4. Replace mock driver/analytics tools with real read-only providers.

## Acceptance Checks
- `/chat` remains response-stable: `reply`, `tools_called`, `conversation_id`.
- Error mapping remains stable (validation 422, quota 429, internal 500).
- No duplicate tool-call execution in one turn.
- Max-loop path returns safe user message without crashing.
- Docs stay aligned with exposed tool registry and schema.
