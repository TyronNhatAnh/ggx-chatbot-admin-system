"""Extracts Gin HTTP route definitions from Go source code.

Replaces the functionality of explorer/be_scanner_go.py — parses Gin
router.Group() / router.GET() / router.POST() patterns and returns
a list of (method, path, handler_var, handler_func, file) tuples that
the flow extractor uses to populate the `endpoint` field on ServiceFlow
and to generate `handles` edges directly (no be_endpoints.json needed).

Supported patterns::

    router.GET("/api/v1/orders/:id", handler.GetOrder)
    v1    := router.Group("/api/v1")
    order := v1.Group("/orders")
    order.POST("/estimate", handler.Estimate)   # → /api/v1/orders/estimate
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_IGNORE_DIRS = frozenset({
    ".git", "vendor", "testdata", "test", "mocks", "__pycache__",
})

_HTTP_METHODS = frozenset({"GET", "POST", "PUT", "DELETE", "PATCH"})

# Gin group assignments:
#   v1 := router.Group("/api/v1")
_GROUP_RE = re.compile(
    r'(\w+)\s*:?=\s*(\w+)\.Group\s*\(\s*"([^"]+)"\s*\)'
)

# Gin route registrations:
#   order.POST("/estimate", orderHandler.Estimate)
_ROUTE_RE = re.compile(
    r'(\w+)\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*"([^"]+)"\s*,\s*(\w+)\.(\w+)'
)


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


def _build_group_map(content: str) -> dict[str, str]:
    """Return {variable_name: resolved_full_prefix} for every Group() call."""
    raw: dict[str, tuple[str, str]] = {}
    for m in _GROUP_RE.finditer(content):
        var_name, parent_var, segment = m.group(1), m.group(2), m.group(3)
        raw[var_name] = (parent_var, segment)
    return {var: _resolve_prefix(var, raw) for var in raw}


def _join_paths(prefix: str, path: str) -> str:
    if not prefix:
        return path
    return prefix.rstrip("/") + "/" + path.lstrip("/")


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
    group_map = _build_group_map(content)
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
        routes.append((method, full_path, handler_var, handler_func, relative))

    return routes


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
        if go_file.name.endswith("_test.go"):
            continue

        routes = extract_routes_from_file(go_file, root)
        for method, path, _handler_var, handler_func, _file in routes:
            endpoint_map[handler_func] = f"{method} {path}"

    logger.info(
        "[RouteExtractor] Found %d endpoint definitions", len(endpoint_map),
    )
    return endpoint_map
