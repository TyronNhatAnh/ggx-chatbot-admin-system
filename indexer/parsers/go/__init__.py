"""Go language parser — extracts enums, structs, and handler flows from Go repos."""

from indexer.parsers.go.parser import GoParser
from indexer.parsers.registry import register

register(GoParser)

__all__ = ["GoParser"]
