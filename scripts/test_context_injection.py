#!/usr/bin/env python3
"""Test that context hints are extracted from tool results."""

import sys
sys.path.insert(0, ".")

from app.orchestrator.ai_orchestrator import _extract_context_hints

# Test 1: Report with organizations
print("Test 1: Extract org names from report results...")
report_results = {
    "get_statement_of_use_summary": {
        "rows": [
            {"organizationName": "DHLSC", "total": 100},
            {"organizationName": "ABC Corp", "total": 200},
            {"organizationName": "XYZ Ltd", "total": 300},
        ],
        "count": 3
    }
}

hints = _extract_context_hints(report_results)
print(f"  Extracted hints:\n{hints}\n")

assert "DHLSC" in hints, "DHLSC should be in context hints"
assert "ABC Corp" in hints, "ABC Corp should be in context hints"
assert "XYZ Ltd" in hints, "XYZ Ltd should be in context hints"
print("  ✓ Organizations correctly extracted into context hints\n")

# Test 2: Orders list
print("Test 2: Extract order IDs from orders list...")
order_results = {
    "get_orders": {
        "orders": [
            {"orderId": "ORD-123", "status": "Active"},
            {"orderId": "ORD-456", "status": "Transit"},
            {"orderId": "ORD-789", "status": "Completed"},
        ],
        "count": 3
    }
}

hints2 = _extract_context_hints(order_results)
print(f"  Extracted hints:\n{hints2}\n")

assert "ORD-123" in hints2, "ORD-123 should be in hints"
assert "ORD-456" in hints2, "ORD-456 should be in hints"
print("  ✓ Orders correctly extracted into context hints\n")

# Test 3: Context injection in multi-turn
print("Test 3: Verify context is injected into multi-turn message...")
from app.orchestrator.context_store import ConversationState, ConversationTurn

state = ConversationState(conversation_id="test-conv")
# Simulate first turn with org report
state.turns.append(ConversationTurn(
    user_message="show me report",
    assistant_reply="Here's the report for DHLSC...",
    tools_called=["get_statement_of_use_summary"],
    tool_results={
        "get_statement_of_use_summary": {
            "rows": [{"organizationName": "DHLSC"}, {"organizationName": "ABC"}],
            "count": 2
        }
    }
))

from app.orchestrator.ai_orchestrator import _build_contextual_message

# Simulate second turn where user asks about DHLSC
contextual_msg = _build_contextual_message("what about DHLSC?", state)
print(f"  Contextual message (excerpt):\n{contextual_msg[:500]}...\n")

# Verify org names are included in contextual message
assert "DHLSC" in contextual_msg, "DHLSC should be in contextual message"
assert "ABC" in contextual_msg, "ABC should be in contextual message"
assert "Data returned:" in contextual_msg, "Data returned hint should be present"
print("  ✓ Organization names injected into contextual message\n")

print("✅ All context injection tests passed!")
