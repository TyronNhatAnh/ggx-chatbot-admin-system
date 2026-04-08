"""
Context builder — converts the three memory layers into native Gemini conversation history.

Returns a list of Content objects to pass as ``history=`` to ``chats.create()``.
The current user message is NOT included — it is sent separately via ``send_message()``.

Memory layout injected as history:
  1. Preamble turn  (user):  conversation summary + top-5 retrieved long-term facts
  2. Preamble ack   (model): "Understood." — maintains required user/model alternation
  3. Recent verbatim turns   (user/model pairs, last N turns from short-term memory)
"""

import logging

from google.genai import types

from app.orchestrator.memory_service import MemoryService

logger = logging.getLogger(__name__)


def build_history(
    session_id: str,
    current_message: str,
    memory_service: MemoryService,
) -> list[types.Content]:
    """Build native Gemini conversation history from the three memory layers.

    Returns a (possibly empty) list of Content objects for ``chats.create(history=...)``.
    """
    history: list[types.Content] = []

    # --- Preamble: summary + retrieved long-term memory ---
    preamble_parts: list[str] = []

    summary = memory_service.get_summary(session_id)
    if summary:
        preamble_parts.append(f"Conversation summary (prior context):\n{summary}")

    retrieved = memory_service.retrieve_memory(session_id, current_message, limit=5)
    if retrieved:
        mem_lines = "\n".join(f"- [{item.type.value}] {item.content}" for item in retrieved)
        preamble_parts.append(f"Remembered facts:\n{mem_lines}")

    if preamble_parts:
        history.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text="\n\n".join(preamble_parts))],
        ))
        history.append(types.Content(
            role="model",
            parts=[types.Part.from_text(text="Understood.")],
        ))

    # --- Recent verbatim turns ---
    recent_turns = memory_service.get_recent_turns(session_id)
    for turn in recent_turns:
        role = "model" if turn.role == "assistant" else "user"
        if not turn.content:
            continue
        text = turn.content
        # Append tool hint on model turns so the model knows what data was retrieved
        if turn.tools_called and role == "model":
            text = f"[Tools used: {', '.join(turn.tools_called)}]\n{text}"
        history.append(types.Content(
            role=role,
            parts=[types.Part.from_text(text=text)],
        ))

    logger.debug(
        "[ContextBuilder] session=%s history_items=%d (preamble=%s, recent_turns=%d)",
        session_id,
        len(history),
        bool(preamble_parts),
        len(recent_turns),
    )
    return history
