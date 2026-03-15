"""Gin (Go) backend scanner — extracts REST endpoints from Gin router definitions.

Supported patterns
------------------
Direct registrations on the router or engine variable:
    router.GET("/api/v1/orders/:id", handler.GetOrder)
    router.POST("/api/v1/orders/estimate", orderHandler.Estimate)

Group-prefixed registrations:
    v1    := router.Group("/api/v1")
    order := v1.Group("/orders")
    order.POST("/estimate", handler.Estimate)   # → /api/v1/orders/estimate
"""

import logging
import os
import re
from pathlib import Path

from models.discovery_models import BackendEndpoint

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_IGNORE_DIRS = frozenset({
    ".git", "vendor", "testdata", "test", "mocks", "__pycache__",
})

_HTTP_METHODS = frozenset({"GET", "POST", "PUT", "DELETE"})

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches Gin group assignments (both := and = forms):
#   v1    := router.Group("/api/v1")
#   order  = v1.Group("/orders")
# Groups: (1) new var, (2) parent var, (3) path segment
_GROUP_RE = re.compile(
    r'(\w+)\s*:?=\s*(\w+)\.Group\s*\(\s*"([^"]+)"\s*\)'
)

# Matches Gin route registrations:
#   router.GET("/api/v1/orders/:id", handler.GetOrder)
#   order.POST("/estimate", orderHandler.Estimate)
# Groups: (1) receiver var, (2) HTTP method, (3) path, (4) handler var, (5) handler func
_ROUTE_RE = re.compile(
    r'(\w+)\.(GET|POST|PUT|DELETE)\s*\(\s*"([^"]+)"\s*,\s*(\w+)\.(\w+)'
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_prefix(var: str, raw: dict[str, tuple[str, str]]) -> str:
    """Walk the parent chain to build the full path prefix for a group variable.

    raw maps variable_name → (parent_variable_name, own_path_segment).
    Chain resolution stops when we reach a variable not in raw (i.e., the
    top-level router/engine variable).
    """
    segments: list[str] = []
    current = var
    seen: set[str] = set()
    while current in raw:
        if current in seen:
            break  # Cycle guard — should not happen in valid code.
        seen.add(current)
        parent, segment = raw[current]
        segments.append(segment)
        current = parent
    segments.reverse()
    return "".join(segments)


def _build_group_map(content: str) -> dict[str, str]:
    """Return {variable_name: resolved_full_prefix} for every Group() call in content."""
    raw: dict[str, tuple[str, str]] = {}
    for m in _GROUP_RE.finditer(content):
        var_name, parent_var, segment = m.group(1), m.group(2), m.group(3)
        raw[var_name] = (parent_var, segment)
    return {var: _resolve_prefix(var, raw) for var in raw}


def _join_paths(prefix: str, path: str) -> str:
    """Concatenate a group prefix and a route path, normalising duplicate slashes."""
    if not prefix:
        return path
    return prefix.rstrip("/") + "/" + path.lstrip("/")


def _scan_go_file(file_path: Path, repo_root: Path) -> list[BackendEndpoint]:
    """Extract Gin route registrations from a single .go source file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("[Scanner/BE/Go] Cannot read %s: %s", file_path, exc)
        return []

    relative = str(file_path.relative_to(repo_root))
    group_map = _build_group_map(content)

    endpoints: list[BackendEndpoint] = []
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

        endpoints.append(BackendEndpoint(
            method=method,
            path=full_path,
            controller=handler_var,
            controller_method=handler_func,
            file=relative,
        ))

    if endpoints:
        logger.debug(
            "[Scanner/BE/Go] %s → %d endpoint(s)", relative, len(endpoints)
        )
    return endpoints


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_go_repo(repo_path: str) -> list[BackendEndpoint]:
    """Scan all .go files in *repo_path* for Gin route definitions.

    Args:
        repo_path: Absolute or relative path to the Go repository root.

    Returns:
        List of BackendEndpoint instances, one per discovered route.
    """
    root = Path(repo_path).resolve()
    if not root.is_dir():
        logger.error(
            "[Scanner/BE/Go] Path does not exist or is not a directory: %s", root
        )
        return []

    all_endpoints: list[BackendEndpoint] = []
    file_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place so os.walk never descends into them.
        dirnames[:] = sorted(d for d in dirnames if d not in _IGNORE_DIRS)
        for filename in filenames:
            if not filename.endswith(".go"):
                continue
            file_path = Path(dirpath) / filename
            file_count += 1
            all_endpoints.extend(_scan_go_file(file_path, root))

    logger.info(
        "[Scanner/BE/Go] Scan complete: %d file(s) scanned, %d endpoint(s) found.",
        file_count,
        len(all_endpoints),
    )
    return all_endpoints
