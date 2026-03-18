#!/usr/bin/env python3
"""Test context injection in multi-turn conversations."""

from app.orchestrator.context_store import ConversationState, ConversationTurn
from app.orchestrator.ai_orchestrator import _build_contextual_message

# Create state with first turn (report query)
state = ConversationState(conversation_id="test-conv")
state.turns.append(ConversationTurn(
    user_message="show me report",
    assistant_reply="Report ready",
    tools_called=["get_statement_of_use_summary"],
    tool_results={
        "get_statement_of_use_summary": {
            "rows": [
                {"organizationName": "DHLSC"},
                {"organizationName": "ABC Corp"},
            ],
            "count": 2
        }
    }
))

# Next turn where user asks about org
msg = _build_contextual_message("view DHLSC", state)

# Verify org names are injected  
success = ("DHLSC" in msg and "ABC Corp" in msg and "Data returned:" in msg)
print("PASSED" if success else "FAILED")
