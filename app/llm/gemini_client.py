import logging

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from google import genai
from google.genai import types

from app.config import settings
from app.llm.vertex_credentials import create_vertex_client

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
    temperature: float = 0.0
    max_output_tokens: int = 4096
    thinking_config: types.ThinkingConfig | None = None
    cache_manager: "ContextCacheManager | None" = field(default=None, compare=False)

    def start_chat(
        self,
        enable_automatic_function_calling: bool = False,
        system_instruction: str | None = None,
        feature_key: str | None = None,
        allowed_function_names: list[str] | None = None,
        history: list[types.Content] | None = None,
    ):
        """Create a new chat session with deterministic function-calling behavior.

        Args:
            enable_automatic_function_calling: Let the SDK auto-call tools.
            system_instruction: Override the factory default system prompt.
                                Pass a per-request prompt built by PromptBuilder.
            feature_key: Feature key used to look up the right context cache entry.
            allowed_function_names: When set, restricts the model to only call tools
                                    in this list for the session (ToolConfig scoping).
                                    None means all registered tools are available.
            history: Prior conversation turns to seed the chat session with.
                     Built by context_builder.build_history().
        """
        effective_instruction = system_instruction or self.system_instruction
        afc = types.AutomaticFunctionCallingConfig(disable=not enable_automatic_function_calling)

        # Scope tools by filtering the list rather than using ToolConfig.allowed_function_names.
        # The Gemini API only allows allowed_function_names with mode=ANY, but ANY forces a tool
        # call on every turn (including tool-result turns), causing an infinite loop.
        # Filtering the tools list achieves the same scoping without that risk.
        allowed_set = set(allowed_function_names) if allowed_function_names else None
        effective_tools = (
            [t for t in self.tools if getattr(t, "__name__", None) in allowed_set]
            if allowed_set else self.tools
        )

        if self.cache_manager is not None and not allowed_set:
            # Only use cached content when NO tool scoping is needed.
            # The cache stores all tools — there is no way to restrict which cached tools
            # the model may call without ToolConfig mode=ANY, which forces a tool call on
            # every turn (including tool-result turns) and causes an infinite loop.
            # When tool scoping is active (allowed_set is non-empty), fall through to the
            # uncached path so effective_tools filtering takes effect.
            cache_name = self.cache_manager.get_cache_name(effective_instruction, feature_key)
            if cache_name:
                # system_instruction and tools are already stored in the cache.
                config = types.GenerateContentConfig(
                    cached_content=cache_name,
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                    automatic_function_calling=afc,
                    thinking_config=self.thinking_config,
                )
                return self.client.chats.create(model=self.model_name, config=config, history=history)

        # Uncached path (default, or when cache creation failed)
        config = types.GenerateContentConfig(
            system_instruction=effective_instruction,
            tools=effective_tools if effective_tools else None,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            automatic_function_calling=afc,
            thinking_config=self.thinking_config,
        )
        return self.client.chats.create(model=self.model_name, config=config, history=history)


def create_gemini_model(
    tools: list,
    model_name: str | None = None,
    client: genai.Client | None = None,
    temperature: float = 0.0,
    max_output_tokens: int = 4096,
    thinking_config: types.ThinkingConfig | None = None,
) -> GeminiChatFactory:
    """
    Configure and return a Gemini chat factory with the given tools.

    Passing Python functions directly lets the SDK auto-generate the JSON
    schema from each function's type hints and docstring — no manual schema
    declaration needed.

    Args:
        tools: List of Python callables to register as tools for the model.
        model_name: Override the model name from settings (used for the Pro factory).
        client: Shared genai.Client instance. Created if not provided.
        temperature: Sampling temperature (0 = deterministic).
        max_output_tokens: Maximum tokens in the response.
        thinking_config: Optional thinking/reasoning config for the model.

    Returns:
        A configured GeminiChatFactory ready to start chat sessions.
    """
    resolved_model = model_name or settings.model_name
    if client is None:
        client = create_vertex_client()

    logger.info("[GeminiClient] Configured model: %s", resolved_model)

    cache_manager = None
    if settings.context_caching_enabled:
        from app.llm.context_cache import ContextCacheManager
        cache_manager = ContextCacheManager(client, resolved_model, tools)
        logger.info(
            "[GeminiClient] Context caching enabled — caches created lazily per feature key."
        )

    return GeminiChatFactory(
        client=client,
        model_name=resolved_model,
        tools=tools,
        system_instruction="",  # always overridden per-request via start_chat(system_instruction=...)
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        thinking_config=thinking_config,
        cache_manager=cache_manager,
    )
