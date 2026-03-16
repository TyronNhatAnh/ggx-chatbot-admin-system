"""Parser registry — maps language keys to LanguageParser implementations.

Auto-imports all parser sub-packages so they can self-register on import.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Type

from indexer.parsers.base import LanguageParser

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, Type[LanguageParser]] = {}


def register(cls: Type[LanguageParser]) -> Type[LanguageParser]:
    """Class decorator — registers a parser by its .language key."""
    key = cls.language.fget(cls)  # type: ignore[attr-defined]
    _REGISTRY[key] = cls
    return cls


def get_parser(lang: str) -> LanguageParser:
    """Instantiate and return the parser for a given language key."""
    _ensure_loaded()
    cls = _REGISTRY.get(lang)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise ValueError(
            f"No parser registered for language '{lang}'. "
            f"Available: {available}"
        )
    return cls()


def list_languages() -> list[str]:
    """Return sorted list of registered language keys."""
    _ensure_loaded()
    return sorted(_REGISTRY)


# ---- auto-detection ----

# Extension → language key mapping (first match wins)
_EXT_LANG_MAP: dict[str, str] = {
    ".go":   "go",
    ".java": "java",
    ".tsx":  "react",
    ".ts":   "react",
    ".jsx":  "react",
    ".rb":   "ruby",
}


def detect_language(repo_path: str) -> str | None:
    """Heuristic: count source files per language, return the dominant one."""
    _ensure_loaded()
    counts: dict[str, int] = {}
    root = Path(repo_path).resolve()
    ignore = frozenset({".git", "vendor", "node_modules", "dist", "build", "__pycache__"})

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignore for part in path.parts):
            continue
        lang = _EXT_LANG_MAP.get(path.suffix)
        if lang and lang in _REGISTRY:
            counts[lang] = counts.get(lang, 0) + 1

    if not counts:
        return None
    return max(counts, key=lambda k: counts[k])


# ---- lazy loading ----

_loaded = False


def _ensure_loaded() -> None:
    """Import all parser sub-packages so they self-register."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    # Each sub-package should call @register on its parser class.
    # We import them here to trigger registration.
    try:
        import indexer.parsers.go  # noqa: F401
    except ImportError:
        pass
    try:
        import indexer.parsers.java  # noqa: F401
    except ImportError:
        pass
    try:
        import indexer.parsers.react  # noqa: F401
    except ImportError:
        pass
    try:
        import indexer.parsers.ruby  # noqa: F401
    except ImportError:
        pass
