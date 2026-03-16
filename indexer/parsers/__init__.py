# Language-specific code parsers.
# Each sub-package implements the LanguageParser interface for one language.

from indexer.parsers.base import LanguageParser
from indexer.parsers.registry import get_parser, detect_language, list_languages

__all__ = ["LanguageParser", "get_parser", "detect_language", "list_languages"]
