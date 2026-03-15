import json
import logging
import time

from google.genai import types

from app.llm.gemini_client import create_gemini_model
from app.orchestrator.context_store import ConversationState, InMemoryConversationStore
from app.tools import ALL_TOOL_FUNCTIONS, TOOL_REGISTRY

logger = logging.getLogger(__name__)
MAX_TOOL_LOOPS = 2      # max Gemini round-trips in tool loop → caps total Gemini calls at MAX_TOOL_LOOPS+1
CONTEXT_HISTORY_TURNS = 2
CONTEXT_TEXT_BUDGET = 900


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

    return (
        f"{context_text}\n\n"
        "Current user message (highest priority):\n"
        f"{message}"
    )


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
        effective_message = _build_contextual_message(message, state)

        # A fresh session per request keeps state isolated between users.
        chat_session = self._model.start_chat(enable_automatic_function_calling=False)

        # Step 1 — send the user message to Gemini
        logger.info("[Step 1/N] Sending user message to Gemini...")
        t = time.perf_counter()
        response = chat_session.send_message(effective_message)
        logger.info("[Step 1/N] Gemini responded  elapsed=%.3fs", time.perf_counter() - t)

        tools_called: list[str] = []
        loop = 0
        gemini_calls = 1  # already made the initial call above
        seen_calls: set[tuple[str, str]] = set()
        # Per-turn cache: orderId → slim order dict populated by search_orders results.
        # Prevents redundant get_order HTTP calls when data is already available.
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
                    cached_order = order_cache.get(str(tool_args.get("order_id", "")))
                    if cached_order is not None:
                        logger.info(
                            "[Tool     ] → get_order(%s)  CACHE HIT — skipping HTTP call",
                            tool_args.get("order_id"),
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
                logger.info(
                    "[Tool     ] ← %s  elapsed=%.3fs  result_keys=%s",
                    tool_name,
                    time.perf_counter() - t,
                    list(result.keys()) if isinstance(result, dict) else type(result).__name__,
                )

                # Populate per-turn cache from search_orders results.
                # Also annotate the result so Gemini knows driverFee + location
                # are already included — no get_order call is needed.
                if tool_name == "search_orders" and isinstance(result, dict):
                    for order in result.get("orders", []):
                        if isinstance(order, dict):
                            oid = str(order.get("orderId") or "")
                            if oid:
                                order_cache[oid] = order
                    result = {
                        **result,
                        "_note": (
                            "Each order already contains price, driverFee, fromPlace, toPlace, driver, vehicle, goods (when available), and payment summary (when available). "
                            "Use these fields directly for location/driver fee/vehicle/goods/payment questions. "
                            "If any requested field is missing or empty for the target order, call get_order(order_id) to fetch full detail."
                        ),
                    }

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
            logger.info("[Step %d  ] Gemini responded  elapsed=%.3fs", loop, time.perf_counter() - t)

        reply = _response_text(response)
        self._context_store.append_turn(
            state.conversation_id,
            user_message=message,
            assistant_reply=reply,
            tools_called=tools_called,
        )
        return (reply, tools_called, state.conversation_id)
