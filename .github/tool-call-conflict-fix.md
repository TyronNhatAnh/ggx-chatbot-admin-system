# Tool-Call Conflict Fix — Context Carry-Over for Report Scope

## Problem
When user followed up a report summary with "show me details for org XYZ" without explicitly saying "customer" or "driver", the system would:
1. Detect both `_wants_customer_report()` and `_wants_driver_report()` as FALSE (ambiguous)
2. Fall through to the ELSE case which defaults to calling BOTH summary tools
3. This re-called `get_statement_of_use_summary` + `get_statement_of_use_driver_summary` instead of the detail tools

Example bug flow:
```
Turn 1: "show me customer report"
  → Calls get_statement_of_use_summary
  → session.report_scope = "customer" (stored)

Turn 2: "show me details for org XYZ"
  → Detection: _wants_customer_report("...") = FALSE (no "customer" keyword)
  → Detection: _wants_driver_report("...") = FALSE (no "driver" keyword)  
  → Both ambiguous → defaults to calling BOTH summary tools
  → BUG: Re-calls summary instead of detail!
```

## Solution
Added **context carry-over** for customer/driver scope from prior turns:

### 1. Added `report_scope` field to SessionState
- File: `app/orchestrator/memory_service.py`
- New field: `report_scope: str | None = None` (stores "customer" | "driver" | "both")
- Persists scope like `feature_key` across conversation turns

### 2. Updated Database Schema
- File: `app/persistence/chat_store.py`
- Added `report_scope TEXT DEFAULT NULL` column to sessions table (via _DDL)
- Updated `load_session()` to fetch report_scope
- Updated `save_session_meta()` to persist report_scope (already done in earlier commits)
- Migration: `_migrate_feature_key()` automatically adds column on first run

### 3. Implemented Context Carry-Over Logic
- File: `app/orchestrator/ai_orchestrator.py`
- **Location 1** (Instruction injection, line ~854-863):
  ```python
  # If detection is ambiguous (both False), inherit scope from prior turn
  if not is_driver and not is_customer and session.report_scope:
      prior_scope = session.report_scope
      if prior_scope == "driver":
          is_driver = True
      elif prior_scope == "customer":
          is_customer = True
      elif prior_scope == "both":
          is_driver = True
          is_customer = True
  ```

- **Location 2** (Scope guard, line ~1116-1125):
  ```python
  # Inherit scope from prior turn if ambiguous
  if not _is_driver and not _is_customer and session.report_scope:
      prior_scope = session.report_scope
      if prior_scope == "driver":
          _is_driver = True
      elif prior_scope == "customer":
          _is_customer = True
      elif prior_scope == "both":
          _is_driver = True
          _is_customer = True
  ```

### 4. Scope Persistence After Detection
- File: `app/orchestrator/ai_orchestrator.py`
- After every report query detection, store the resolved scope (line ~914-920):
  ```python
  # Persist detected scope for follow-up requests
  if is_driver and is_customer:
      session.report_scope = "both"
  elif is_driver:
      session.report_scope = "driver"
  elif is_customer:
      session.report_scope = "customer"
  ```

## Expected Behavior After Fix

```
Turn 1: "show me customer report"
  → Detection: customer only
  → Calls get_statement_of_use_summary
  → session.report_scope = "customer" ✓

Turn 2: "show me details for org XYZ"
  → Detection: both FALSE (ambiguous)
  → Carry-over: prior scope = "customer" → set is_customer = True
  → Calls get_statement_of_use_detail (customer detail, NOT summary) ✓
  → session.report_scope = "customer" (unchanged)

Turn 3: "also show driver"
  → Detection: is_driver = TRUE (explicit)
  → is_customer = FALSE (not mentioned)
  → Calls get_statement_of_use_driver_summary (new scope)
  → session.report_scope = "driver" (updated to new explicit signal)

Turn 4: "show detail"
  → Detection: both FALSE (ambiguous)
  → Carry-over: prior scope = "driver" → set is_driver = True
  → Calls get_statement_of_use_driver_detail ✓
```

## Testing Checklist
- [ ] Turn 1: Customer summary report works
- [ ] Turn 2: Follow-up "detail for org X" calls detail (not summary)
- [ ] Turn 3: Explicit "driver" signal updates scope 
- [ ] Turn 4: Follow-up detail request uses new driver scope
- [ ] Turn 5: Explicit "customer" signal reverts scope back
- [ ] Follow-up queries preserve correct scope in database (after restart)

## Changes Summary
| File | Changes |
|---|---|
| `app/orchestrator/memory_service.py` | Added `report_scope` field to SessionState |
| `app/persistence/chat_store.py` | Schema: added report_scope column; load/save methods updated |
| `app/orchestrator/ai_orchestrator.py` | Added scope carry-over at 2 locations; persist scope after detection |
| Database | Auto-migrated via `_migrate_feature_key()` |

## Related Issues
- Fixes: Tool-call conflict where follow-up detail requests would re-call summary tools
- Related to: Date-reset fix (both carry context across turns)
- Related to: Context-hints activation (both improve follow-up continuity)
