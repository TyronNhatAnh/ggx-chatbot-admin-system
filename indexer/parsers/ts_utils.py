"""Shared tree-sitter utilities for AST-based code parsing.

Provides lazy-loaded Language objects and Parser factories for Go and Java.
Falls back gracefully if tree-sitter is not installed — callers must check
``is_available()`` before using parsed trees.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Language, Node, Parser, Tree

logger = logging.getLogger(__name__)

_go_lang: "Language | None" = None
_java_lang: "Language | None" = None
_available: bool | None = None


def is_available() -> bool:
    """Return True if tree-sitter + language grammars are installed."""
    global _available
    if _available is not None:
        return _available
    try:
        import tree_sitter  # noqa: F401
        import tree_sitter_go  # noqa: F401
        _available = True
    except ImportError:
        _available = False
        logger.info("[tree-sitter] Not installed — falling back to regex parsing")
    return _available


def go_language() -> "Language":
    """Return the Go Language object (cached)."""
    global _go_lang
    if _go_lang is None:
        import tree_sitter_go as tsgo
        from tree_sitter import Language
        _go_lang = Language(tsgo.language())
    return _go_lang


def java_language() -> "Language":
    """Return the Java Language object (cached)."""
    global _java_lang
    if _java_lang is None:
        import tree_sitter_java as tsjava
        from tree_sitter import Language
        _java_lang = Language(tsjava.language())
    return _java_lang


def parse_go(source: bytes) -> "Tree":
    """Parse Go source bytes and return the tree."""
    from tree_sitter import Parser
    p = Parser(go_language())
    return p.parse(source)


def parse_java(source: bytes) -> "Tree":
    """Parse Java source bytes and return the tree."""
    from tree_sitter import Parser
    p = Parser(java_language())
    return p.parse(source)


def node_text(node: "Node") -> str:
    """Get the UTF-8 text of a tree-sitter node."""
    return node.text.decode("utf-8", errors="replace")


def find_children(node: "Node", type_name: str) -> list["Node"]:
    """Return all direct children of a given type."""
    return [c for c in node.children if c.type == type_name]


def find_child(node: "Node", type_name: str) -> "Node | None":
    """Return the first direct child of a given type, or None."""
    for c in node.children:
        if c.type == type_name:
            return c
    return None


def walk_descendants(node: "Node", type_name: str) -> list["Node"]:
    """Recursively find all descendant nodes of a given type."""
    results: list["Node"] = []
    stack = list(node.children)
    while stack:
        n = stack.pop()
        if n.type == type_name:
            results.append(n)
        stack.extend(n.children)
    return results


def node_start_line(node: "Node") -> int:
    """1-based start line of a node."""
    return node.start_point.row + 1


def node_end_line(node: "Node") -> int:
    """1-based end line of a node."""
    return node.end_point.row + 1


def preceding_comments(node: "Node", source: bytes) -> str:
    """Extract // comment lines immediately preceding a node."""
    lines = source[:node.start_byte].decode("utf-8", errors="replace").rstrip().split("\n")
    comment_lines: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("//"):
            comment_lines.append(stripped.lstrip("/ "))
        else:
            break
    comment_lines.reverse()
    return " ".join(comment_lines)
