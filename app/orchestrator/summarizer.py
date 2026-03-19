"""
Conversation summarizer.

Compresses older conversation turns into a compact running summary that
preserves user intent, entities (IDs), decisions, and constraints while
discarding filler text.
"""

import logging
import threading
from typing import TYPE_CHECKING

from google import genai
from google.genai import types

from app.config import settings

if TYPE_CHECKING:
    from app.orchestrator.memory_service import Turn

logger = logging.getLogger(__name__)

# Module-level cached client — avoid creating a new HTTP connection on every call.
_client_lock = threading.Lock()
_cached_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _cached_client
    with _client_lock:
        if _cached_client is None:
            _cached_client = genai.Client(api_key=settings.gemini_api_key)
        return _cached_client

# The summarization prompt — aggressive compression, factual only.
_SUMMARIZE_SYSTEM = (
    "You are a conversation summarizer for a logistics admin assistant.\n"
    "Rules:\n"
    "1. Compress aggressively — output ≤ 200 words.\n"
    "2. Preserve ALL entity IDs (order IDs, user IDs, driver IDs, organization names).\n"
    "3. Preserve decisions made and constraints stated.\n"
    "4. Preserve the user's original intent and any unresolved questions.\n"
    "5. Remove pleasantries, filler, and redundant detail.\n"
    "6. Use bullet points for clarity.\n"
    "7. If a tool was called, note the tool name and key result (one line).\n"
    "8. Do NOT invent information.\n"
    "Output ONLY the summary — no preamble."
)


def summarize_conversation(
    turns: list["Turn"],
    existing_summary: str = "",
) -> str:
    """Produce a compact summary of the given turns.

    If an ``existing_summary`` is provided, it is prepended so the new summary
    is a *running* accumulation of the full conversation history.

    Uses a lightweight Gemini call (no tools, low temperature) to keep latency
    and cost minimal.
    """
    if not turns:
        return existing_summary

    # Build the text block to summarize
    parts: list[str] = []
    if existing_summary:
        parts.append(f"Previous summary:\n{existing_summary}\n")
    parts.append("New turns to incorporate:")
    for t in turns:
        prefix = t.role.upper()
        parts.append(f"[{prefix}] {t.content}")
        if t.tools_called:
            parts.append(f"  Tools: {', '.join(t.tools_called)}")
        if t.tool_results:
            for tool_name, result in t.tool_results.items():
                snippet = str(result)[:200].replace("\n", " ")
                parts.append(f"  Result({tool_name}): {snippet}")

    user_content = "\n".join(parts)

    try:
        client = _get_client()
        response = client.models.generate_content(
            model=settings.model_name,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=_SUMMARIZE_SYSTEM,
                temperature=0.2,
                max_output_tokens=280,  # ≤200 words × ~1.4 tokens/word
            ),
        )
        summary = (response.text or "").strip()
        if summary:
            logger.info(
                "[Summarizer] Compressed %d turns → %d chars",
                len(turns), len(summary),
            )
            return summary
    except Exception:
        logger.exception("[Summarizer] Gemini summarization failed — falling back to rule-based")

    # Fallback: simple extractive summary (no LLM needed)
    return _fallback_summary(turns, existing_summary)


_FALLBACK_SUMMARY_MAX_CHARS = 800


def _fallback_summary(turns: list["Turn"], existing_summary: str) -> str:
    """Deterministic fallback when LLM is unavailable."""
    lines: list[str] = []
    if existing_summary:
        # Cap prior summary to keep total size bounded
        lines.append(existing_summary[:400])
    for t in turns:
        prefix = "U" if t.role == "user" else "A"
        snippet = t.content[:150].replace("\n", " ")
        line = f"- [{prefix}] {snippet}"
        if t.tools_called:
            line += f" (tools: {', '.join(t.tools_called)})"
        lines.append(line)
    return "\n".join(lines)
