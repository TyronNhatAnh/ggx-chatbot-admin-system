# Prompt Consolidation Map

## Goal
Reduce conflicts between prompt files and runtime-injected instructions while keeping report behavior stable.

## Ownership Rules

### Keep In app/prompts (Source Of Truth)
These are policy/behavior rules that should be human-readable and easy to maintain.

1. Domain decision rules
- Scope detection (customer vs driver vs both).
- Summary vs detail selection.
- Parameter semantics (date, organization_id, pay semantics).
- Output contract (field names, table shape, required totals, language).

2. Data presentation rules
- Which fields must be preserved.
- When compact display is allowed.
- How to expand omitted fields on follow-up.

3. User-facing communication policy
- Tone, structure, no reasoning leakage, no fabricated values.

Files:
- app/prompts/base/persona.md
- app/prompts/base/safety.md
- app/prompts/base/output-format.md
- app/prompts/features/report-summary.md
- app/prompts/features/order-lookup.md
- app/prompts/features/driver-tracking.md

### Keep In Runtime Guard (Code Enforcement)
These are non-negotiable technical controls that must be deterministic.

1. Tool execution safety
- Unknown tool rejection.
- Duplicate tool-call suppression in same turn.
- Max tool loops and forced synthesis fallback.
- One-time retry for transient NETWORK_ERROR.

2. Hard correctness guards
- Scope guard that blocks out-of-scope tools.
- Argument sanitization/normalization before tool invocation.
- Appointment-based date injection from known order context.

3. Operational constraints
- Row caps/token caps/truncation limits.
- Context size budgeting and summarization.
- Prompt-injection marker sanitization.

Files:
- app/orchestrator/ai_orchestrator.py
- app/orchestrator/context_builder.py
- app/orchestrator/memory_service.py
- app/services/order_service_client.py
- app/limits.py

### Move Out Of Runtime String Instructions (Into app/prompts)
These currently exist as natural-language strings in orchestrator and can conflict with feature prompts.

1. "Call X tool immediately" directives.
2. "Do not call lookup_enum first" style sequencing hints.
3. Retry narrative prompts that restate report policy.

Target approach:
- Keep runtime logic as boolean guards.
- Keep behavioral wording in app/prompts only.

## Conflict Hotspots (Current)

1. app/prompts rules vs runtime injected report instructions.
2. Base output-format guidance vs report-specific formatting requirements.
3. Tool docstring guidance vs feature prompt guidance.

## Consolidation Plan (Phased)

### Phase 1 (Low Risk)
1. Keep current runtime guards.
2. Minimize runtime natural-language instruction text; prefer neutral metadata notes.
3. Ensure report formatting contract is fully defined only in report-summary.md.

### Phase 2 (Medium Risk)
1. Replace hardcoded "Call tool immediately" strings with a structured planner hint object (non-natural-language).
2. Let feature prompt explain behavior; runtime only enforces constraints.

### Phase 3 (Higher Impact)
1. Reduce duplicated business guidance from tool docstrings; keep docstrings API-focused.
2. Add tests for policy invariants:
- No out-of-scope report tool calls.
- Date carry-over behavior.
- Summary must not drop non-null fields.
- Detail field expansion on follow-up.

## Rule Priority
When conflicts occur, enforce this order:
1. Runtime Guard (hard safety/correctness constraints)
2. Feature Prompt (domain policy)
3. Base Prompt (global style/safety)
4. Tool Docstring guidance

## Practical Definition Of Done
1. All business/report policy text lives in app/prompts.
2. Runtime code contains guard logic, not duplicated policy prose.
3. No contradictory statements across base/features/runtime.
4. Regression tests cover the top 4 report invariants.
