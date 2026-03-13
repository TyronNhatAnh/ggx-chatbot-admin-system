import json
import logging

import google.generativeai as genai

from app.llm.gemini_client import create_gemini_model
from app.tools import ALL_TOOL_FUNCTIONS, TOOL_REGISTRY

logger = logging.getLogger(__name__)


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
        self._model = create_gemini_model(ALL_TOOL_FUNCTIONS)

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
        # A fresh session per request keeps state isolated between users.
        chat_session = self._model.start_chat(enable_automatic_function_calling=False)

        # Step 1 & 2 — send the user message to Gemini
        response = chat_session.send_message(message)

        tools_called: list[str] = []

        # Steps 3-5 — tool-calling loop
        # Gemini may request one or more tools before producing a final answer.
        while True:
            # Collect every function_call part from the current response turn
            function_calls = [
                part.function_call
                for part in response.parts
                if getattr(part, "function_call", None) and part.function_call.name
            ]

            # No tool calls → Gemini is done; break out with the final answer
            if not function_calls:
                break

            # Step 4 — execute each requested tool and collect the results
            tool_response_parts = []
            for fc in function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args)

                logger.info("[Tool Call]   %s(%s)", tool_name, tool_args)

                tool_fn = TOOL_REGISTRY.get(tool_name)
                if tool_fn is None:
                    raise ValueError(
                        f"LLM requested unknown tool: '{tool_name}'. "
                        "This should not happen — check that all tools are registered."
                    )

                result = tool_fn(**tool_args)
                logger.info("[Tool Result] %s", result)

                tools_called.append(tool_name)

                # Wrap the result in the format Gemini's API expects
                tool_response_parts.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=tool_name,
                            response={"result": json.dumps(result, default=str)},
                        )
                    )
                )

            # Step 5 — send all tool results back to Gemini in one message
            response = chat_session.send_message(tool_response_parts)

        return response.text, tools_called
