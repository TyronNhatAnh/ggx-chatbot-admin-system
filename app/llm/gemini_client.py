import logging

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from google import genai
from google.genai import types

from app.config import settings
from app.llm.vertex_credentials import create_vertex_client
from app.orchestrator.prompt_builder import build_system_prompt

if TYPE_CHECKING:
    from app.llm.context_cache import ContextCacheManager

logger = logging.getLogger(__name__)

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
    cache_manager: "ContextCacheManager | None" = field(default=None, compare=False)

    def start_chat(
        self,
        enable_automatic_function_calling: bool = False,
        system_instruction: str | None = None,
        feature_key: str | None = None,
    ):
        """Create a new chat session with deterministic function-calling behavior.

        Args:
            enable_automatic_function_calling: Let the SDK auto-call tools.
            system_instruction: Override the factory default system prompt.
                                Pass a per-request prompt built by PromptBuilder.
            feature_key: Feature key used to look up the right context cache entry.
        """
        effective_instruction = system_instruction or self.system_instruction
        afc = types.AutomaticFunctionCallingConfig(disable=not enable_automatic_function_calling)

        if self.cache_manager is not None:
            cache_name = self.cache_manager.get_cache_name(effective_instruction, feature_key)
            if cache_name:
                # When using cached content, system_instruction and tools are already
                # stored in the cache — do not pass them again.
                config = types.GenerateContentConfig(
                    cached_content=cache_name,
                    automatic_function_calling=afc,
                )
                return self.client.chats.create(model=self.model_name, config=config)

        # Uncached path (default, or when cache creation failed)
        config = types.GenerateContentConfig(
            system_instruction=effective_instruction,
            tools=self.tools,
            automatic_function_calling=afc,
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
    client = create_vertex_client()

    logger.info("[GeminiClient] Configured model: %s", settings.model_name)
    try:
        available = [m.name for m in client.models.list()]
        gemini_models = [m for m in available if "gemini" in m.lower()]
        if gemini_models:
            logger.info("[GeminiClient] Gemini models available (%d): %s", len(gemini_models), gemini_models)
        else:
            logger.info(
                "[GeminiClient] No Gemini models returned by list API "
                "(normal on Vertex AI — Gemini is accessed via publisher endpoint). "
                "All listed models (%d): %s", len(available), available,
            )
    except Exception as exc:
        logger.warning("[GeminiClient] Could not list models: %s", exc)

    cache_manager = None
    if settings.context_caching_enabled:
        from app.llm.context_cache import ContextCacheManager
        cache_manager = ContextCacheManager(client, settings.model_name, tools)
        logger.info(
            "[GeminiClient] Context caching enabled — caches created lazily per feature key."
        )

    return GeminiChatFactory(
        client=client,
        model_name=settings.model_name,
        tools=tools,
        system_instruction=build_system_prompt(),
        cache_manager=cache_manager,
    )
