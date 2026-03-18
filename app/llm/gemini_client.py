import logging

from dataclasses import dataclass

from google import genai
from google.genai import types

from app.config import settings
from app.orchestrator.prompt_builder import build_system_prompt

# Suppress noisy SDK info log about JSON Schema conversion.
# This is an informational message from google-genai when auto-generating
# tool schemas from Python functions — not an error.
logging.getLogger("google_genai.types").setLevel(logging.WARNING)


@dataclass
class GeminiChatFactory:
    """Build fresh chat sessions with shared model configuration."""

    client: genai.Client
    model_name: str
    tools: list
    system_instruction: str

    def start_chat(
        self,
        enable_automatic_function_calling: bool = False,
        system_instruction: str | None = None,
    ):
        """Create a new chat session with deterministic function-calling behavior.

        Args:
            enable_automatic_function_calling: Let the SDK auto-call tools.
            system_instruction: Override the factory default system prompt.
                                Pass a per-request prompt built by PromptBuilder.
        """
        config = types.GenerateContentConfig(
            system_instruction=system_instruction or self.system_instruction,
            tools=self.tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=not enable_automatic_function_calling
            ),
        )
        return self.client.chats.create(model=self.model_name, config=config)


def create_gemini_model(tools: list) -> GeminiChatFactory:
    """
    Configure and return a Gemini chat factory with the given tools.

    Passing Python functions directly lets the SDK auto-generate the JSON
    schema from each function's type hints and docstring — no manual schema
    declaration needed.

    Args:
        tools: List of Python callables to register as tools for the model.

    Returns:
        A configured GeminiChatFactory ready to start chat sessions.
    """
    client = genai.Client(api_key=settings.gemini_api_key)

    return GeminiChatFactory(
        client=client,
        model_name=settings.model_name,
        tools=tools,
        system_instruction=build_system_prompt(),
    )
