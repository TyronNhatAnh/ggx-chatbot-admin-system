import json
import logging
import re
import threading
import time
from typing import Any

from google.genai import types

from app.config import settings
from app.llm.gemini_client import create_gemini_model
from app.orchestrator.context_store import CachedOrderRecord, ConversationState, InMemoryConversationStore
from app.tools import ALL_TOOL_FUNCTIONS, TOOL_REGISTRY

logger = logging.getLogger(__name__)
MAX_TOOL_LOOPS = 3      # max Gemini round-trips in tool loop → caps total Gemini calls at MAX_TOOL_LOOPS+1
CONTEXT_HISTORY_TURNS = 2
CONTEXT_TEXT_BUDGET = 900
ORDER_CACHE_MAX_ITEMS = 24
ORDER_CACHE_TTL_SECONDS = 60
ORDER_ID_PATTERN = re.compile(r"\b(?:ORD-)?[A-Za-z0-9-]{5,}\b")

_fallback_counters = {
    "max_tool_loop": 0,
    "repetitive_tool_calls": 0,
}
_fallback_counter_lock = threading.Lock()


def _response_parts(response: types.GenerateContentResponse) -> list[types.Part]:
    """Extract parts from the first candidate safely."""
    if not response.candidates:
        return []
    content = response.candidates[0].content
    if not content or not content.parts:
        return []
    return list(content.parts)


def _response_text(response: types.GenerateContentResponse) -> str:
    """Extract plain text response with a safe fallback."""
    if response.text:
        return response.text
    texts: list[str] = []
    for part in _response_parts(response):
        if part.text:
            texts.append(part.text)
    return "\n".join(texts).strip()


def _trim_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def _normalize_order_id(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.upper().startswith("ORD-"):
        return raw.upper()
    if raw.isdigit():
        return raw
    return raw


def _extract_order_id_candidates(message: str) -> list[str]:
    found = [_normalize_order_id(m.group(0)) for m in ORDER_ID_PATTERN.finditer(message)]
    unique: list[str] = []
    seen: set[str] = set()
    for oid in found:
        if not oid:
            continue
        if oid in seen:
            continue
        seen.add(oid)
        unique.append(oid)
    return unique


def _resolve_order_cache_ttl_seconds() -> int:
    configured = int(getattr(settings, "chat_order_cache_ttl_seconds", ORDER_CACHE_TTL_SECONDS))
    return max(30, configured)


def _evict_expired_order_cache(state: ConversationState) -> None:
    if not state.order_cache:
        return
    cutoff = time.time() - _resolve_order_cache_ttl_seconds()
    expired_keys = [
        oid
        for oid, record in state.order_cache.items()
        if record.cached_at < cutoff
    ]
    for oid in expired_keys:
        state.order_cache.pop(oid, None)


def _put_order_cache(state: ConversationState, order_id: str, order: dict[str, Any]) -> None:
    oid = _normalize_order_id(order_id)
    if not oid or not isinstance(order, dict):
        return

    state.order_cache[oid] = CachedOrderRecord(order=order)

    while len(state.order_cache) > ORDER_CACHE_MAX_ITEMS:
        oldest_key = min(state.order_cache, key=lambda k: state.order_cache[k].cached_at)
        state.order_cache.pop(oldest_key, None)


def _get_cached_order(state: ConversationState, order_id: str) -> dict | None:
    oid = _normalize_order_id(order_id)
    if not oid:
        return None
    record = state.order_cache.get(oid)
    if record is None:
        return None

    if record.cached_at < (time.time() - _resolve_order_cache_ttl_seconds()):
        state.order_cache.pop(oid, None)
        return None
    return record.order


def _build_contextual_message(message: str, state: ConversationState) -> str:
    if not state.turns:
        return message

    recent_turns = state.turns[-CONTEXT_HISTORY_TURNS:]
    context_lines: list[str] = [
        "Recent conversation context (for continuity):",
    ]
    for turn in recent_turns:
        context_lines.append(f"- User: {_trim_text(turn.user_message.replace(chr(10), ' '), 220)}")
        context_lines.append(f"- Assistant: {_trim_text(turn.assistant_reply.replace(chr(10), ' '), 260)}")
        if turn.tools_called:
            context_lines.append(f"- Tools used: {', '.join(turn.tools_called)}")

    context_text = "\n".join(context_lines)
    if len(context_text) > CONTEXT_TEXT_BUDGET:
        context_text = context_text[-CONTEXT_TEXT_BUDGET:]

    focus_hint = ""
    if state.last_focus_order_id:
        focus_hint = (
            f"Conversation focus hint: current order_id is {state.last_focus_order_id}. "
            "For follow-up questions without explicit ID, use this order first."
        )

    return (
        f"{context_text}\n\n"
        f"{focus_hint}\n\n"
        "Current user message (highest priority):\n"
        f"{message}"
    )


def _increment_fallback_counter(counter_name: str) -> int:
    with _fallback_counter_lock:
        _fallback_counters[counter_name] = _fallback_counters.get(counter_name, 0) + 1
        return _fallback_counters[counter_name]


def _current_fallback_counters() -> dict[str, int]:
    with _fallback_counter_lock:
        return dict(_fallback_counters)


def _log_structured_metrics(
    *,
    conversation_id: str,
    tools_called: list[str],
    gemini_calls: int,
    gemini_latency_seconds: float,
    tool_latency_seconds: float,
    total_latency_seconds: float,
    fallback_reason: str | None,
) -> None:
    payload = {
        "event": "chat_metrics",
        "conversation_id": conversation_id,
        "gemini_calls": gemini_calls,
        "tool_call_count": len(tools_called),
        "tool_unique_count": len(set(tools_called)),
        "latency_seconds": {
            "gemini": round(gemini_latency_seconds, 3),
            "tools": round(tool_latency_seconds, 3),
            "total": round(total_latency_seconds, 3),
        },
        "fallback_reason": fallback_reason,
        "fallback_counters": _current_fallback_counters(),
    }
    logger.info("[Metrics  ] %s", json.dumps(payload, sort_keys=True))


class AIOrchestrator:
    """
    Manages the full conversation lifecycle with Gemini, including the
    tool-calling loop:

        send message
            → Gemini detects tool call needed
            → execute tool(s)
            → send results back to Gemini
            → get final plain-text answer
            → return to caller

    The loop repeats until Gemini produces a final text response with no
    further tool calls.
    """

    def __init__(self) -> None:
        # Build the model once at startup — it holds the tool schema and
        # system prompt, so it is safe to reuse across requests.
        logger.info("[Orchestrator] Loading Gemini model with %d tools...", len(ALL_TOOL_FUNCTIONS))
        self._model = create_gemini_model(ALL_TOOL_FUNCTIONS)
        self._context_store = InMemoryConversationStore(ttl_seconds=1800, max_turns=12)
        logger.info("[Orchestrator] Gemini model ready.")

    def chat(self, message: str, conversation_id: str | None = None) -> tuple[str, list[str], str]:
        """
        Send a user message and return the AI's reply with a list of tools used.

        Each call starts a fresh chat session. If ``conversation_id`` is
        provided, short context from recent turns is injected into the input
        to preserve continuity across requests.

        Args:
            message: The user's natural-language query.
            conversation_id: Optional conversation identifier from a previous
                             response.

        Returns:
            A tuple of (reply_text, tools_called, conversation_id) where
            tools_called is a list of function names that were invoked during
            this turn.

        Raises:
            ValueError: If Gemini requests a tool that is not in the registry.
        """
        total_start = time.perf_counter()
        state = self._context_store.get_or_create(conversation_id)
        _evict_expired_order_cache(state)

        current_message_order_ids = _extract_order_id_candidates(message)
        if current_message_order_ids:
            state.last_focus_order_id = current_message_order_ids[0]

        effective_message = _build_contextual_message(message, state)

        # A fresh session per request keeps state isolated between users.
        chat_session = self._model.start_chat(enable_automatic_function_calling=False)

        # Step 1 — send the user message to Gemini
        logger.info("[Step 1/N] Sending user message to Gemini...")
        t = time.perf_counter()
        response = chat_session.send_message(effective_message)
        first_gemini_elapsed = time.perf_counter() - t
        logger.info("[Step 1/N] Gemini responded  elapsed=%.3fs", first_gemini_elapsed)

        tools_called: list[str] = []
        loop = 0
        gemini_calls = 1  # already made the initial call above
        gemini_elapsed_total = first_gemini_elapsed
        tool_elapsed_total = 0.0
        seen_calls: set[tuple[str, str]] = set()
        # Per-turn cache: orderId -> order dict from search_orders results.
        # Combined with conversation cache to avoid redundant HTTP calls.
        order_cache: dict[str, dict] = {}

        # Tool-calling loop — Gemini may request tools before producing a final answer.
        while True:
            loop += 1

            # Collect every function_call part from the current response turn.
            # Must happen BEFORE the MAX_TOOL_LOOPS guard so that a final-text
            # response is never mistaken for a loop-overrun.
            function_calls = [
                part.function_call
                for part in _response_parts(response)
                if getattr(part, "function_call", None) and part.function_call.name
            ]

            # No tool calls → Gemini produced the final answer
            if not function_calls:
                elapsed = time.perf_counter() - total_start
                logger.info(
                    "[Step %d  ] Gemini returned final answer  tools_called=%s  gemini_calls=%d  total_elapsed=%.3fs",
                    loop, tools_called, gemini_calls, elapsed,
                )
                _log_structured_metrics(
                    conversation_id=state.conversation_id,
                    tools_called=tools_called,
                    gemini_calls=gemini_calls,
                    gemini_latency_seconds=gemini_elapsed_total,
                    tool_latency_seconds=tool_elapsed_total,
                    total_latency_seconds=elapsed,
                    fallback_reason=None,
                )
                break

            if loop > MAX_TOOL_LOOPS:
                logger.warning(
                    "[Step %d  ] Max tool loop reached (%d). gemini_calls=%d total_elapsed=%.3fs. Returning early.",
                    loop,
                    MAX_TOOL_LOOPS,
                    gemini_calls,
                    time.perf_counter() - total_start,
                )
                reply = (
                    "I have enough partial data, but the tool-calling cycle became too long. "
                    "Please retry with a more specific query (for example: order ID or status only)."
                )
                _increment_fallback_counter("max_tool_loop")
                total_elapsed = time.perf_counter() - total_start
                _log_structured_metrics(
                    conversation_id=state.conversation_id,
                    tools_called=tools_called,
                    gemini_calls=gemini_calls,
                    gemini_latency_seconds=gemini_elapsed_total,
                    tool_latency_seconds=tool_elapsed_total,
                    total_latency_seconds=total_elapsed,
                    fallback_reason="max_tool_loop",
                )
                self._context_store.append_turn(
                    state.conversation_id,
                    user_message=message,
                    assistant_reply=reply,
                    tools_called=tools_called,
                )
                return (reply, tools_called, state.conversation_id)

            logger.info(
                "[Step %d  ] Gemini requested %d tool(s): %s",
                loop, len(function_calls), [fc.name for fc in function_calls],
            )

            # Execute each requested tool and collect the results
            tool_response_parts = []
            for fc in function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args or {})
                call_key = (tool_name, json.dumps(tool_args, sort_keys=True, default=str))

                if call_key in seen_calls:
                    logger.warning("[Tool     ] skipping duplicate tool call %s(%s)", tool_name, tool_args)
                    continue

                seen_calls.add(call_key)

                # Serve get_order from per-turn cache if search_orders already
                # fetched this order — avoids a redundant HTTP round-trip.
                if tool_name == "get_order":
                    requested_order_id = _normalize_order_id(str(tool_args.get("order_id", "")))
                    if requested_order_id:
                        state.last_focus_order_id = requested_order_id

                    cached_order = order_cache.get(requested_order_id)
                    if cached_order is None and requested_order_id:
                        cached_order = _get_cached_order(state, requested_order_id)
                    if cached_order is not None:
                        logger.info(
                            "[Tool     ] → get_order(%s)  CACHE HIT — skipping HTTP call",
                            requested_order_id or tool_args.get("order_id"),
                        )
                        tools_called.append(tool_name)
                        # Wrap in a note so Gemini treats this as complete data
                        # and does not request the same order again.
                        enriched = {**cached_order, "_note": "full record from order service"}
                        tool_response_parts.append(
                            types.Part.from_function_response(
                                name=tool_name,
                                response={"result": json.dumps(enriched, default=str)},
                            )
                        )
                        continue

                logger.info("[Tool     ] → %s(%s)", tool_name, tool_args)
                t = time.perf_counter()

                tool_fn = TOOL_REGISTRY.get(tool_name)
                if tool_fn is None:
                    raise ValueError(
                        f"LLM requested unknown tool: '{tool_name}'. "
                        "This should not happen — check that all tools are registered."
                    )

                result = tool_fn(**tool_args)
                tool_elapsed = time.perf_counter() - t
                tool_elapsed_total += tool_elapsed
                logger.info(
                    "[Tool     ] ← %s  elapsed=%.3fs  result_keys=%s",
                    tool_name,
                    tool_elapsed,
                    list(result.keys()) if isinstance(result, dict) else type(result).__name__,
                )

                # Populate per-turn cache from search_orders results.
                # Also annotate the result so Gemini knows driverFee + location
                # are already included — no get_order call is needed.
                if tool_name == "search_orders" and isinstance(result, dict):
                    for order in result.get("orders", []):
                        if isinstance(order, dict):
                            oid = _normalize_order_id(str(order.get("orderId") or ""))
                            if oid:
                                order_cache[oid] = order
                                _put_order_cache(state, oid, order)
                    if current_message_order_ids:
                        state.last_focus_order_id = current_message_order_ids[0]
                    result = {
                        **result,
                        "_note": (
                            "Each order already contains price, driverFee, fromPlace, toPlace, driver, vehicle, goods (when available), and payment summary (when available). "
                            "Use these fields directly for location/driver fee/vehicle/goods/payment questions. "
                            "If any requested field is missing or empty for the target order, call get_order(order_id) to fetch full detail."
                        ),
                    }

                if tool_name == "get_order" and isinstance(result, dict):
                    requested_order_id = _normalize_order_id(str(tool_args.get("order_id", "")))
                    actual_order_id = _normalize_order_id(str(result.get("orderId") or requested_order_id))
                    if actual_order_id:
                        _put_order_cache(state, actual_order_id, result)
                        state.last_focus_order_id = actual_order_id

                tools_called.append(tool_name)

                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": json.dumps(result, default=str)},
                    )
                )

            if not tool_response_parts:
                logger.warning("[Step %d  ] No new tool results to send. Returning early.", loop)
                reply = (
                    "I could not complete the answer because tool calls became repetitive. "
                    "Please retry with a narrower question."
                )
                _increment_fallback_counter("repetitive_tool_calls")
                total_elapsed = time.perf_counter() - total_start
                _log_structured_metrics(
                    conversation_id=state.conversation_id,
                    tools_called=tools_called,
                    gemini_calls=gemini_calls,
                    gemini_latency_seconds=gemini_elapsed_total,
                    tool_latency_seconds=tool_elapsed_total,
                    total_latency_seconds=total_elapsed,
                    fallback_reason="repetitive_tool_calls",
                )
                self._context_store.append_turn(
                    state.conversation_id,
                    user_message=message,
                    assistant_reply=reply,
                    tools_called=tools_called,
                )
                return (reply, tools_called, state.conversation_id)

            # Send all tool results back to Gemini in one message
            gemini_calls += 1
            logger.info(
                "[Step %d  ] Sending %d tool result(s) back to Gemini...  (gemini_calls so far: %d/%d)",
                loop, len(tool_response_parts), gemini_calls, MAX_TOOL_LOOPS + 1,
            )
            t = time.perf_counter()
            response = chat_session.send_message(tool_response_parts)
            gemini_elapsed = time.perf_counter() - t
            gemini_elapsed_total += gemini_elapsed
            logger.info("[Step %d  ] Gemini responded  elapsed=%.3fs", loop, gemini_elapsed)

        reply = _response_text(response)
        self._context_store.append_turn(
            state.conversation_id,
            user_message=message,
            assistant_reply=reply,
            tools_called=tools_called,
        )
        return (reply, tools_called, state.conversation_id)
