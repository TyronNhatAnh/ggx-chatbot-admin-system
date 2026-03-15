import json
import logging
import time

from google.genai import types

from app.llm.gemini_client import create_gemini_model
from app.tools import ALL_TOOL_FUNCTIONS, TOOL_REGISTRY

logger = logging.getLogger(__name__)
MAX_TOOL_LOOPS = 3


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
        logger.info("[Orchestrator] Gemini model ready.")

    def chat(self, message: str) -> tuple[str, list[str]]:
        """
        Send a user message and return the AI's reply with a list of tools used.

        Each call starts a fresh, stateless chat session so requests do not
        bleed into each other.

        Args:
            message: The user's natural-language query.

        Returns:
            A tuple of (reply_text, tools_called) where tools_called is a list
            of function names that were invoked during this turn.

        Raises:
            ValueError: If Gemini requests a tool that is not in the registry.
        """
        total_start = time.perf_counter()

        # A fresh session per request keeps state isolated between users.
        chat_session = self._model.start_chat(enable_automatic_function_calling=False)

        # Step 1 — send the user message to Gemini
        logger.info("[Step 1/N] Sending user message to Gemini...")
        t = time.perf_counter()
        response = chat_session.send_message(message)
        logger.info("[Step 1/N] Gemini responded  elapsed=%.3fs", time.perf_counter() - t)

        tools_called: list[str] = []
        loop = 0
        seen_calls: set[tuple[str, str]] = set()

        # Tool-calling loop — Gemini may request tools before producing a final answer.
        while True:
            loop += 1

            if loop > MAX_TOOL_LOOPS:
                logger.warning(
                    "[Step %d  ] Max tool loop reached (%d). Returning early.",
                    loop,
                    MAX_TOOL_LOOPS,
                )
                return (
                    "I have enough partial data, but the tool-calling cycle became too long. "
                    "Please retry with a more specific query (for example: order ID or status only).",
                    tools_called,
                )

            # Collect every function_call part from the current response turn
            function_calls = [
                part.function_call
                for part in _response_parts(response)
                if getattr(part, "function_call", None) and part.function_call.name
            ]

            # No tool calls → Gemini produced the final answer
            if not function_calls:
                elapsed = time.perf_counter() - total_start
                logger.info(
                    "[Step %d  ] Gemini returned final answer  tools_called=%s  total_elapsed=%.3fs",
                    loop, tools_called, elapsed,
                )
                break

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

                tools_called.append(tool_name)

                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": json.dumps(result, default=str)},
                    )
                )

            if not tool_response_parts:
                logger.warning("[Step %d  ] No new tool results to send. Returning early.", loop)
                return (
                    "I could not complete the answer because tool calls became repetitive. "
                    "Please retry with a narrower question.",
                    tools_called,
                )

            # Send all tool results back to Gemini in one message
            logger.info("[Step %d  ] Sending %d tool result(s) back to Gemini...", loop, len(tool_response_parts))
            t = time.perf_counter()
            response = chat_session.send_message(tool_response_parts)
            logger.info("[Step %d  ] Gemini responded  elapsed=%.3fs", loop, time.perf_counter() - t)

        return _response_text(response), tools_called
