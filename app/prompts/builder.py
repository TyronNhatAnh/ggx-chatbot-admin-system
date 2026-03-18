from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def _load(relative_path: str) -> str:
    """Load and cache a prompt file. Reads once at startup, never re-reads."""
    return (_PROMPT_DIR / relative_path).read_text(encoding="utf-8")


@lru_cache(maxsize=32)
def build_system_prompt(feature_key: str | None = None) -> str:
    """
    Compose system prompt from modular files.

    Always includes base/ layer.
    Conditionally includes features/{feature_key}.md and few-shots/{feature_key}.md
    if the files exist.

    Args:
        feature_key: e.g. "order-lookup", "driver-tracking", "report-summary"
                     Pass None for a generic prompt with no domain context.

    Returns:
        Full system prompt string ready for Gemini API call.
    """
    parts: list[str] = [
        _load("base/persona.md"),
        _load("base/safety.md"),
        _load("base/output-format.md"),
    ]

    if feature_key:
        feature_path = f"features/{feature_key}.md"
        if (_PROMPT_DIR / feature_path).exists():
            parts.append(_load(feature_path))

        few_shot_path = f"few-shots/{feature_key}.md"
        if (_PROMPT_DIR / few_shot_path).exists():
            parts.append(_load(few_shot_path))

    return "\n\n---\n\n".join(parts)
