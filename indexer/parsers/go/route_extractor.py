"""Extracts Gin HTTP route definitions from Go source code.

Uses tree-sitter for robust AST-based extraction when available,
falling back to regex for environments where tree-sitter is not installed.

Supported patterns::

    router.GET("/api/v1/orders/:id", handler.GetOrder)
    v1    := router.Group("/api/v1")
    order := v1.Group("/orders")
    order.POST("/estimate", handler.Estimate)   # → /api/v1/orders/estimate
"""

import logging
import re
from pathlib import Path

from indexer.parsers.ts_utils import (
    find_child,
    is_available as _ts_available,
    node_text,
    parse_go,
    walk_descendants,
)

logger = logging.getLogger(__name__)

_IGNORE_DIRS = frozenset({
    ".git", "vendor", "testdata", "test", "mocks", "__pycache__",
})

_HTTP_METHODS = frozenset({"GET", "POST", "PUT", "DELETE", "PATCH"})

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _join_paths(prefix: str, path: str) -> str:
    if not prefix:
        return path
    return prefix.rstrip("/") + "/" + path.lstrip("/")


def _resolve_prefix(var: str, raw: dict[str, tuple[str, str]]) -> str:
    """Walk the parent chain to build the full path prefix for a group variable."""
    segments: list[str] = []
    current = var
    seen: set[str] = set()
    while current in raw:
        if current in seen:
            break
        seen.add(current)
        parent, segment = raw[current]
        segments.append(segment)
        current = parent
    segments.reverse()
    return "".join(segments)


# ---------------------------------------------------------------------------
# Tree-sitter extraction
# ---------------------------------------------------------------------------


def _ts_unquote(node) -> str:
    """Strip surrounding quotes from a string literal node."""
    text = node_text(node)
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def _ts_selector_parts(node) -> tuple[str, str]:
    """Return (object, method) from a selector_expression."""
    operand = find_child(node, "identifier")
    field = find_child(node, "field_identifier")
    if operand and field:
        return node_text(operand), node_text(field)
    return "", ""


def _ts_extract_routes_from_file(source: bytes, rel_path: str,
                                 ) -> list[tuple[str, str, str, str, str]]:
    tree = parse_go(source)
    root = tree.root_node

    # Pass 1: collect Group() assignments → {var_name: (parent_var, segment)}
    raw_groups: dict[str, tuple[str, str]] = {}

    for call_node in walk_descendants(root, "call_expression"):
        func = call_node.children[0] if call_node.children else None
        if not func or func.type != "selector_expression":
            continue

        parent_var, method = _ts_selector_parts(func)
        if method != "Group":
            continue

        args = find_child(call_node, "argument_list")
        if not args:
            continue
        # First argument is the path string
        str_node = find_child(args, "interpreted_string_literal")
        if not str_node:
            continue
        segment = _ts_unquote(str_node)

        # Find the var_name from: var_name := parent.Group(...)
        # Walk up to short_var_declaration
        assign = call_node.parent
        if assign and assign.type == "short_var_declaration":
            lhs = assign.children[0] if assign.children else None
            if lhs and lhs.type == "expression_list":
                id_node = find_child(lhs, "identifier")
                if id_node:
                    raw_groups[node_text(id_node)] = (parent_var, segment)

    group_map = {var: _resolve_prefix(var, raw_groups) for var in raw_groups}

    # Pass 2: collect route registrations → receiver.GET("/path", handler.Func)
    routes: list[tuple[str, str, str, str, str]] = []

    for call_node in walk_descendants(root, "call_expression"):
        func = call_node.children[0] if call_node.children else None
        if not func or func.type != "selector_expression":
            continue

        receiver_var, method = _ts_selector_parts(func)
        if method not in _HTTP_METHODS:
            continue

        args = find_child(call_node, "argument_list")
        if not args:
            continue

        # First arg: path string
        str_node = find_child(args, "interpreted_string_literal")
        if not str_node:
            continue
        path = _ts_unquote(str_node)

        # Second arg: handler.Method (selector_expression)
        handler_sel = find_child(args, "selector_expression")
        if not handler_sel:
            continue
        handler_var_node = find_child(handler_sel, "identifier")
        handler_func_node = find_child(handler_sel, "field_identifier")
        if not handler_var_node or not handler_func_node:
            continue

        prefix = group_map.get(receiver_var, "")
        full_path = _join_paths(prefix, path)
        routes.append((
            method,
            full_path,
            node_text(handler_var_node),
            node_text(handler_func_node),
            rel_path,
        ))

    return routes


# ---------------------------------------------------------------------------
# Regex fallback (original implementation)
# ---------------------------------------------------------------------------

_GROUP_RE = re.compile(
    r'(\w+)\s*:?=\s*(\w+)\.Group\s*\(\s*"([^"]+)"\s*\)'
)

_ROUTE_RE = re.compile(
    r'(\w+)\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*"([^"]+)"\s*,\s*(\w+)\.(\w+)'
)


def _regex_build_group_map(content: str) -> dict[str, str]:
    raw: dict[str, tuple[str, str]] = {}
    for m in _GROUP_RE.finditer(content):
        var_name, parent_var, segment = m.group(1), m.group(2), m.group(3)
        raw[var_name] = (parent_var, segment)
    return {var: _resolve_prefix(var, raw) for var in raw}


def _regex_extract_routes_from_file(content: str, rel_path: str,
                                    ) -> list[tuple[str, str, str, str, str]]:
    group_map = _regex_build_group_map(content)
    routes: list[tuple[str, str, str, str, str]] = []

    for m in _ROUTE_RE.finditer(content):
        receiver = m.group(1)
        method = m.group(2).upper()
        path = m.group(3)
        handler_var = m.group(4)
        handler_func = m.group(5)

        if method not in _HTTP_METHODS:
            continue

        prefix = group_map.get(receiver, "")
        full_path = _join_paths(prefix, path)
        routes.append((method, full_path, handler_var, handler_func, rel_path))

    return routes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_routes_from_file(
    file_path: Path, repo_root: Path,
) -> list[tuple[str, str, str, str, str]]:
    """Extract Gin route registrations from a single Go file.

    Returns list of (http_method, full_path, handler_var, handler_func, relative_file).
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    relative = str(file_path.relative_to(repo_root))

    if _ts_available():
        return _ts_extract_routes_from_file(content.encode("utf-8"), relative)
    return _regex_extract_routes_from_file(content, relative)


def extract_routes_from_repo(repo_path: str) -> dict[str, str]:
    """Walk Go repo and build handler_func → 'METHOD /path' endpoint map.

    Returns:
        Dict mapping handler function name to endpoint string,
        e.g. {"GetOrderDetail": "GET /api/v1/orders/:id"}.
    """
    root = Path(repo_path).resolve()
    endpoint_map: dict[str, str] = {}

    for go_file in root.rglob("*.go"):
        if any(part in _IGNORE_DIRS for part in go_file.parts):
            continue
        if go_file.name.endswith("_test.go") or go_file.name.endswith(".pb.go"):
            continue

        routes = extract_routes_from_file(go_file, root)
        for method, path, _handler_var, handler_func, _file in routes:
            endpoint_map[handler_func] = f"{method} {path}"

    logger.info(
        "[RouteExtractor] Found %d endpoint definitions (tree-sitter=%s)",
        len(endpoint_map), _ts_available(),
    )
    return endpoint_map
