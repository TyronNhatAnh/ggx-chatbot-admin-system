"""
Context builder — assembles the final LLM input from the three memory layers.

Returned message list:
  1. System prompt          (handled externally by GeminiChatFactory)
  2. Conversation summary   (if exists)
  3. Retrieved long-term memory (top 3, if relevant)
  4. Last 3-5 recent turns
  5. Current user message

Token-aware: the builder enforces a budget and truncates/drops gracefully.
"""

import logging
from dataclasses import dataclass

from app.orchestrator.memory_service import MemoryItem, MemoryService, Turn

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------
MAX_CONTEXT_TOKENS = 8000
# Use ~55% for input context (summary + memory + turns).
# Remaining 45% is reserved for system prompt, tool schemas, and output.
INPUT_TOKEN_BUDGET = int(MAX_CONTEXT_TOKENS * 0.55)       # ~4400

# Rough chars-per-token ratios.
# English/ASCII averages ~4 chars per token; CJK (Korean, Chinese, Japanese)
# averages ~1.5 chars per token due to multi-byte encoding and subword splits.
# We use conservative (lower) values so token estimates are higher — this means
# we drop context sooner rather than risk exceeding the actual token limit.
CHARS_PER_TOKEN_ASCII = 3.5
CHARS_PER_TOKEN_CJK = 1.2

# CJK Unicode ranges for detection
_CJK_RANGES = (
    (0x3000, 0x9FFF),    # CJK Unified, Hiragana, Katakana, Bopomofo, etc.
    (0xAC00, 0xD7AF),    # Hangul Syllables
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0x1100, 0x11FF),    # Hangul Jamo
)


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


# Safety: never drop the latest N turns regardless of budget.
MIN_PROTECTED_TURNS = 2


@dataclass
class ContextBlock:
    """One block injected into LLM context."""
    label: str        # for logging only
    text: str
    priority: int     # lower = more important; protected turns = 0


def estimate_tokens(text: str) -> int:
    """Estimate token count with CJK-aware heuristic."""
    cjk_chars = sum(1 for ch in text if _is_cjk(ch))
    ascii_chars = len(text) - cjk_chars
    tokens = ascii_chars / CHARS_PER_TOKEN_ASCII + cjk_chars / CHARS_PER_TOKEN_CJK
    return max(1, int(tokens))


def build_context(
    session_id: str,
    current_message: str,
    memory_service: MemoryService,
) -> str:
    """Assemble a single context string to prepend to the user's message.

    Returns a string that should be prepended (or used as system context)
    before the current user query when calling the LLM.
    """
    blocks: list[ContextBlock] = []

    # 1. Conversation summary
    summary = memory_service.get_summary(session_id)
    if summary:
        blocks.append(ContextBlock(
            label="summary",
            text=f"Conversation summary (prior context):\n{summary}",
            priority=2,
        ))

    # 2. Long-term memory retrieval
    retrieved = memory_service.retrieve_memory(session_id, current_message, limit=3)
    if retrieved:
        mem_text = _format_memory_items(retrieved)
        blocks.append(ContextBlock(
            label="long_term_memory",
            text=f"Remembered facts:\n{mem_text}",
            priority=3,
        ))

    # 3. Recent turns (short-term memory)
    recent_turns = memory_service.get_recent_turns(session_id)
    for i, turn in enumerate(recent_turns):
        is_protected = i >= len(recent_turns) - MIN_PROTECTED_TURNS
        blocks.append(ContextBlock(
            label=f"turn_{i}_{turn.role}",
            text=_format_turn(turn),
            priority=0 if is_protected else 1,
        ))

    # 4. Enforce token budget — drop lowest-priority blocks first
    blocks = _fit_budget(blocks, INPUT_TOKEN_BUDGET)

    if not blocks:
        return current_message

    context_parts = [b.text for b in blocks]
    context_str = "\n\n".join(context_parts)

    logger.debug(
        "[ContextBuilder] session=%s blocks=%d tokens≈%d",
        session_id, len(blocks), estimate_tokens(context_str),
    )

    return (
        f"{context_str}\n\n"
        "Current user message (highest priority):\n"
        f"{current_message}"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_REPORT_TOOL_NAMES = frozenset({
    "get_statement_of_use_summary",
    "get_statement_of_use_detail",
    "get_statement_of_use_driver_summary",
    "get_statement_of_use_driver_detail",
})


def _format_turn(turn: Turn) -> str:
    role_label = turn.role.capitalize()
    # For report turns: skip the assistant's formatted table body — only the tool name
    # and date range matter for continuity. The table can be hundreds of chars and just bloats context.
    is_report_turn = bool(turn.tools_called and any(t in _REPORT_TOOL_NAMES for t in turn.tools_called))
    if role_label == "Assistant" and is_report_turn:
        # Extract the date range used so the LLM can reuse it in follow-up queries.
        date_hint = ""
        for t_name in turn.tools_called:
            if t_name in _REPORT_TOOL_NAMES:
                params = turn.tool_params.get(t_name, {})
                from_d = params.get("from_date") or params.get("fromDate") or ""
                to_d = params.get("to_date") or params.get("toDate") or ""
                if from_d or to_d:
                    date_hint = f" [dates: {from_d} to {to_d}]"
                    break
        line = f"- {role_label}: [report result delivered{date_hint}]"
    else:
        line = f"- {role_label}: {turn.content[:500]}"
    if turn.tools_called:
        line += f"\n  Tools: {', '.join(turn.tools_called)}"
    return line


def _format_memory_items(items: list[MemoryItem]) -> str:
    return "\n".join(f"- [{item.type.value}] {item.content}" for item in items)


def _fit_budget(blocks: list[ContextBlock], token_budget: int) -> list[ContextBlock]:
    """Drop lowest-priority (highest number) blocks until within budget.

    Never drops blocks with priority == 0 (protected recent turns).
    """
    total = sum(estimate_tokens(b.text) for b in blocks)
    if total <= token_budget:
        return blocks

    # Sort by priority descending so we drop least-important first
    droppable = sorted(
        [(i, b) for i, b in enumerate(blocks) if b.priority > 0],
        key=lambda x: -x[1].priority,
    )

    dropped_indices: set[int] = set()
    for idx, block in droppable:
        if total <= token_budget:
            break
        total -= estimate_tokens(block.text)
        dropped_indices.add(idx)
        logger.debug("[ContextBuilder] Dropped block '%s' (priority=%d)", block.label, block.priority)

    return [b for i, b in enumerate(blocks) if i not in dropped_indices]
