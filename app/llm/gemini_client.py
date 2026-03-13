import google.generativeai as genai

from app.config import settings
from app.orchestrator.prompt_builder import build_system_prompt


def create_gemini_model(tools: list) -> genai.GenerativeModel:
    """
    Configure and return a Gemini GenerativeModel with the given tools.

    Passing Python functions directly lets the SDK auto-generate the JSON
    schema from each function's type hints and docstring — no manual schema
    declaration needed.

    Args:
        tools: List of Python callables to register as tools for the model.

    Returns:
        A configured GenerativeModel instance ready to start chat sessions.
    """
    genai.configure(api_key=settings.gemini_api_key)

    return genai.GenerativeModel(
        model_name=settings.model_name,
        tools=tools,
        system_instruction=build_system_prompt(),
    )
