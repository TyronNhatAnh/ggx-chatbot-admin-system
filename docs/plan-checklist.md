# AI Admin Assistant Plan Checklist

## Goal
Build a production-ready read-only logistics AI assistant by using a staged discovery and implementation plan:
1. Analyze key functions first (started from check-price flow).
2. Scan full Web2 FE + BE and map API usage.
3. Consolidate business logic and requirements into docs.
4. Expand tool layer and assistant coverage for full logistics operations.

## Strategy Decision (Current)
- Primary track: optimize one FE/BE pair first (`web2` + `order`) for speed, quality, and deterministic output.
- Expansion track: add multi-repo support immediately after single-pair quality gate passes.
- Why this order:
  - lower implementation risk and easier debugging
  - faster feedback loop for prompt/spec/discovery quality
  - avoids over-generalizing before baseline contracts are stable

## Scope Baseline
- Source A: AI Admin Assistant (this repo)
- Source B: Web2 FE + BE systems (legacy/current production flows)
- Domain target: End-to-end logistics operations (order lifecycle, driver, pricing, payment, reports)

## Phase 0 - Current State Check
- [x] FastAPI service with `/chat` and `/health`
- [x] Gemini function-calling orchestrator integrated
- [x] Loop safety guard (`MAX_TOOL_LOOPS`) and duplicate-call prevention
- [x] Order service real API integration (auth token + order query)
- [x] Token cache with TTL and 401 refresh path
- [x] Slim response payload to reduce LLM latency
- [x] Quota error mapping to HTTP 429
- [ ] Chat endpoint auth and rate limiting
- [ ] Test suite (unit + integration)

## Phase 1 - Discovery Foundation (Started)
- [x] Initial function-first analysis approach established (check-price style flow)
- [x] Created service-level discovery notes in docs
- [x] Define one canonical template for every discovered API (endpoint, caller, payload, business rule, dependencies)
- [x] Define naming standard for docs output files
- [x] Add feature exploration template (`explorer/feature_specs/_template.yaml`)
- [x] Add feature exploration guide (`docs/features/README.md`)
- [x] Enforce strict evidence-only generation for feature requirement/spec outputs

## Phase 1A - Single Pair Hardening (Now)
- Scope: only one FE + one BE repo (`web2` + `order`)
- [ ] Freeze canonical golden feature specs for top journeys in this pair (check_price, tracking, cancel)
- [ ] Tighten `be_files` / `fe_files` globs to minimize noise and token volume
- [ ] Validate evidence quality: no UNKNOWN on in-scope handlers unless true code gap
- [ ] Baseline latency and output size for repeated explore runs
- [ ] Finalize docs output contract and cleanup behavior for error artifacts

Exit criteria:
- [ ] 3 priority features generate stable docs twice in a row with no manual fixes
- [ ] Discovery outputs are reproducible for same commit and same spec
- [ ] Team agrees output readability is sufficient for business review

## Phase 1B - Multi-Repo Foundation (Next)
- Target services to onboard:
  - admin (java spring)
  - user / driver / common / notification (golang)
  - ruby integration services (2)
  - DA / CA apps (2)
- [ ] Add multi-repo config support (list of FE repos, list of BE repos)
- [ ] Add namespaced discovery outputs per repo (avoid overwrite collisions)
- [ ] Extend flow mapping to include source repo identifiers
- [ ] Add merge step for cross-repo endpoint inventory and flow mappings
- [ ] Update feature spec format to optionally include repo namespace per file glob

Exit criteria:
- [ ] At least 3 BE services + 2 FE apps scanned in one orchestrated run
- [ ] No artifact overwrite across repos
- [ ] Cross-service feature can cite evidence from multiple repos in one requirement

## Phase 2 - Web2 FE Scan Checklist
- [ ] Inventory all FE modules/pages related to logistics domain
- [ ] Extract every API call used by FE (method + URL + params + body)
- [ ] Map API call to feature/user action
- [ ] Mark critical journeys:
  - [ ] Create/estimate/check-price
  - [ ] Order tracking/status
  - [ ] Driver assignment/visibility
  - [ ] Payment/coupon/tip
  - [ ] Report/export
- [ ] Capture FE-side validation rules and conditional flows

## Phase 3 - Web2 BE Scan Checklist
- [ ] Inventory service boundaries and major domains (order, user, payment, driver, reporting)
- [ ] Map endpoint -> handler -> service -> persistence/integration chain
- [ ] Capture business constraints per endpoint
- [ ] Capture status transitions and state machine rules
- [ ] Capture external dependencies and failure handling
- [ ] Mark read-only safe endpoints for assistant tools

## Phase 4 - FE-BE Mapping Docs (Core Deliverable)
- [ ] Build FE action -> BE API -> business logic mapping table
- [ ] Link every flow to source files and docs references
- [ ] Identify missing or inconsistent requirements
- [ ] Identify duplicated APIs and overlapping semantics
- [ ] Produce domain glossary (status codes, enums, key entities)

## Phase 5 - Tool Design and Expansion
- [ ] Keep current small query tools as reusable building blocks
- [ ] Group tools by domain:
  - [ ] order tools
  - [ ] driver tools
  - [ ] pricing tools
  - [ ] payment/report tools
- [ ] Add only read-only tools needed by mapped user journeys
- [ ] For each new tool, define:
  - [ ] minimal response contract
  - [ ] pagination/limit strategy
  - [ ] error contract
  - [ ] latency budget target

## Phase 6 - Reliability and Performance Hardening
- [ ] Add API auth for `/chat`
- [ ] Add rate limit and abuse guard
- [ ] Add structured metrics:
  - [ ] model round-trip time
  - [ ] tool execution time
  - [ ] total request latency
  - [ ] tool-call count per request
- [ ] Add alerting thresholds for latency and error rates
- [ ] Add regression tests for prompt/tool routing behavior

## Phase 7 - Product Readiness Gate
- [ ] Requirements and business logic docs complete for target scope
- [ ] Tool coverage mapped to priority logistics queries
- [ ] No critical mock dependency in production path
- [ ] SLO target defined and measured (p50/p95 latency)
- [ ] Security review complete (secrets, authz, logging hygiene)
- [ ] Rollout checklist complete (staging test + monitoring + fallback)

## Immediate Next Actions (Recommended)
- [ ] Finish Phase 1A first: top 3 features in single pair and stabilize outputs
- [ ] Draft multi-repo config schema and artifact naming convention before coding
- [ ] Implement Phase 1B in small increments (config -> scan -> map -> explore)
- [ ] Replace mock analytics with real read-only aggregation source
- [ ] Add minimal auth + rate limit for `/chat`
