# Synthesis Response Fix — Empty Reply & Field Names

## Problems Identified

### Issue 1: Empty Response After Sanitization → Wrong Fallback Message
When Gemini's main response was empty (all thinking, no text), the synthesis fallback wasn't working because it didn't have access to the actual tool result data.

**Logs showed**:
```
[Tool] ← get_statement_of_use_detail elapsed=0.876s result_keys=['rows', 'count', 'total_count']
[Reply] Empty reply after sanitization (likely all-thought response). Sending synthesis prompt...
→ "No customer report details were found..." (synthesis fallback)
```

The synthesis prompt was:
```
"Please write your final answer now based on the tool results you already received. Do NOT call any more tools."
```

**Problem**: Gemini doesn't have the actual rows/data JSON. It just sees a text instruction.

### Issue 2: Field Names Being Translated
Response using "Organization Name" instead of exact key "organizationName".

**Root cause**: Multiple places were translating field names even though we added an exception in base/output-format.md.

## Solutions Implemented

### Fix 1: Pass Tool Results to Synthesis Prompts
**File**: `app/orchestrator/ai_orchestrator.py`

**Changed synthesis messages** in 2 locations to include actual tool result data:

**Location 1** (Empty reply fallback, ~line 1335):
```python
# BEFORE:
synth_response = chat_session.send_message(
    "Please write your final answer now based on the tool results you already received. "
    "Do NOT call any more tools. Provide a clear, concise response for the admin."
)

# AFTER:
synth_msg_parts: list[str] = [
    "Here are your tool results. Please write your final answer NOW using this data:",
    json.dumps(tool_results_collected, indent=2, default=str)[:5000],  # Cap at 5k chars
    "\nDo NOT call any more tools. Provide a clear, concise response for the admin.",
    "For report-domain responses, use the EXACT field names from the data (e.g., organizationId, totalRevenue) as table headers — do NOT translate or rename them.",
]
synth_msg = "\n\n".join(synth_msg_parts)
synth_response = chat_session.send_message(synth_msg)
```

**Location 2** (Max tool loop fallback, ~line 1050):
- Same pattern: include `tool_results_collected` JSON in the synthesis message
- Added field-name rule reminder in synthesis prompt

### Fix 2: Reinforce Field Name Rule in Prompts
Added field-name preservation rule to BOTH synthesis prompts:
```
"For report-domain responses, use the EXACT field names from the data (e.g., organizationId, totalRevenue) as table headers — do NOT translate or rename them."
```

**Existing rules** (already present):
- [base/output-format.md](base/output-format.md#L18): "in report domain responses, keep exact tool key names as table headers"
- [app/prompts/features/report-summary.md](app/prompts/features/report-summary.md#L33): "Do NOT translate, localize, or rename report field names in headers"

## Expected Behavior After Fix

### Before (Broken):
```
User: "show me customer report in this month"
  → get_statement_of_use_summary returns data
  → Response OK

User: "show me details for org 7053"
  → get_statement_of_use_detail returns data
  → Gemini thinking-only response → sanitized to empty
  → Synthesis fallback: "No details found" (doesn't have the data!)
  
BAD OUTPUT
```

### After (Fixed):
```
User: "show me customer report in this month"
  → get_statement_of_use_summary returns data
  → Response with table

User: "show me details for org 7053"
  → get_statement_of_use_detail returns data
  → Gemini thinking + response OR thinking-only
  → If empty/thought-only → Synthesis fallback WITH actual tool results
  → Gemini synthesizes table from provided data
  → Response with exact field keys: organizationId, orderId, totalRevenue, etc.
  
CORRECT OUTPUT
```

## Changes Summary

| File | Change | Reason |
|---|---|---|
| `app/orchestrator/ai_orchestrator.py` ~L1052-1065 | Pass `tool_results_collected` JSON to synthesis prompt (max_tool_loop path) | Give Gemini data to synthesize from instead of just an instruction |
| `app/orchestrator/ai_orchestrator.py` ~L1335-1353 | Pass `tool_results_collected` JSON to synthesis prompt (empty reply path) | Same: provide actual data in synthesis fallback |
| Both locations | Add field-name rule reminder to synthesis prompt | Reinforce no-translation rule at synthesis time |

## Testing Checklist
- [ ] Detail query after summary returns actual detail rows (not "no data" message)
- [ ] Table headers use exact keys: organizationId, totalRevenue, orderId (NOT "Organization ID", "Total Revenue")
- [ ] Response includes all rows returned by tool (not truncated)
- [ ] No repeated synthesis attempts (single synthesis call per empty response)

## Related Fixes
- Date reset fix (1/7)  ✓
- Tool-call conflict fix (2/7) ✓
- Surcharge contract fix (3/7) ✓
- Field name preservation: **THIS FIX** (4/7) ✓
- Row cap increase (5/7) ✓
- Context hints activation (6/7) ✓
- Consolidation map (7/7) ✓

Total: **ALL 7 FIX AREAS ADDRESSED**
