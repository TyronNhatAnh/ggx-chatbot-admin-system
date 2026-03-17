# AI Admin Assistant Plan Checklist

## Goal
Build a production-ready read-only logistics AI assistant with:
1. Indexed codebase knowledge (Go + React repos) for deep system understanding.
2. Live API integration for real-time order/pricing queries.
3. Multi-service coverage across the full logistics platform.

## Strategy
- Single offline indexing pipeline (`indexer/`) extracts all structured knowledge.
- Docs tools query the indexed knowledge store (no separate discovery/explorer step).
- Live tools query real backend APIs (order-service, user-service) at runtime.

## Phase 0 - Foundation (DONE)
- [x] FastAPI service with `/chat` and `/health`
- [x] Gemini function-calling orchestrator integrated
- [x] Loop safety guard (`MAX_TOOL_LOOPS`) and duplicate-call prevention
- [x] Order service real API integration (auth token + order query)
- [x] Token cache with TTL and 401 refresh path
- [x] Slim response payload to reduce LLM latency
- [x] Quota error mapping to HTTP 429
- [x] Basic `/chat` API integration tests (pricing paths + quota mapping + auth/rate-limit checks)
- [x] Chat endpoint auth and rate limiting
- [x] Request correlation ID propagation

## Phase 1 - Codebase Indexer (DONE)
- [x] 4-pass Go parser: enums → types → flows → graph edges
- [x] React parser: components, API calls, routes, types
- [x] Go route extraction (Gin router patterns → handler-endpoint mapping)
- [x] Handler source code storage as indexed CodeChunks
- [x] SQLite knowledge store with FTS5 + graph edges
- [x] ChromaDB vector embeddings for semantic search
- [x] Cross-service linker (React API calls → Go handlers)
- [x] Docs tools rewritten to query indexer store (no file-based discovery)
- [x] Explorer module removed — indexer covers all functionality
- [x] Indexed: order-service (104 enums, 531 structs, 182 flows, 999 chunks)
- [x] Indexed: web2 (30 enums, 217 types, 85 flows)

## Phase 2 - Multi-Service Expansion
- [x] user-service indexing support (Go)
- [ ] Index admin-service (Java Spring — needs Java parser)
- [ ] Index driver-service, common-service, notification-service (Go)
- [ ] Index DA/CA mobile apps if applicable
- [ ] Expand cross-service links with more backend services

## Phase 3 - Tool Coverage Expansion
- [ ] Replace mock driver tools with real read-only providers
- [ ] Add analytics/reporting tools backed by real data
- [ ] Group tools by domain: order, driver, pricing, payment, report
- [ ] For each new tool: define response contract, pagination, error contract, latency budget

## Phase 4 - Reliability and Performance Hardening
- [x] Auth guard for `/chat` (API key)
- [x] Rate limiting (configurable via .env)
- [x] Request correlation ID in logs
- [x] Structured metrics (model/tool/total latency, tool counts)
- [ ] Timeout and retry policy guardrails for external calls
- [ ] Expand orchestrator regression tests (duplicate calls, max-loop, unknown tool)
- [ ] Alerting thresholds for latency and error rates

## Phase 5 - Production Readiness
- [ ] Move conversation store to shared backing store (Redis/DB)
- [ ] Add observability dashboard (metrics, traces)
- [ ] Security review complete (secrets, authz, logging hygiene)
- [ ] SLO target defined and measured (p50/p95 latency)
- [ ] Staging test + monitoring + fallback rollout plan
- [ ] No mock dependencies in production path

## Immediate Next Actions
- [ ] Index remaining Go services (driver, common, notification)
- [ ] Investigate Java parser for admin-service
- [ ] Replace mock driver/analytics tools
- [ ] Expand test suite depth (orchestrator loop controls, schema consistency)
- [ ] Use `docs/chat-api-deep-audit.md` as the backlog for `/chat` hardening tasks
