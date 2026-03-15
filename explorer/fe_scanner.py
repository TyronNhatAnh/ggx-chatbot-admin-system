import logging
import os
import re
from pathlib import Path

from models.discovery_models import FrontendApiCall

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCAN_EXTENSIONS = frozenset({".ts", ".tsx", ".js", ".jsx"})

_IGNORE_DIRS = frozenset({
    "node_modules", ".git", ".next", "dist", "build", "out",
    ".turbo", "coverage", ".cache", "__pycache__",
})

# Known relative-path prefixes used without a leading slash in this codebase,
# e.g. "guest/home-moving/goods", "guest/orders/route/${id}".
_RELATIVE_PREFIXES = ("guest/", "api/", "v1/", "v2/")

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Strips single-line // comments while preserving https:// inside strings.
_COMMENT_RE = re.compile(r"(?<![:/])//.*$", re.MULTILINE)

# Detects the start + opening paren of a named axios client call.
# Handles optional TypeScript generic type arg: client.get<ResponseType>(...)
# Groups: (1) HTTP method
_CLIENT_CALL_RE = re.compile(
    r"\b(?:\w+ApiClient|axiosClient|axios)\s*\.\s*(get|post|put|delete|patch)"
    r"(?:<[^>]*>)?\s*\(",
    re.IGNORECASE,
)

# Detects start of a server-side fetch() call.
_FETCH_CALL_RE = re.compile(r"\bfetch\s*\(", re.IGNORECASE)

# Detects `method: 'VERB'` option inside a fetch block.
_FETCH_METHOD_RE = re.compile(r"\bmethod\s*:\s*['\"]([A-Za-z]+)['\"]", re.IGNORECASE)

# Matches any JS/TS string literal content.
# Groups: (1) backtick, (2) single-quote, (3) double-quote content.
_STRING_RE = re.compile(r'`([^`]*)`|\'([^\']*)\'|"([^"]*)"')

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_url(raw: str) -> str:
    """Strip leading env-var prefix and collapse template expressions to {param}.

    Examples:
      `/orders/${orderId}/route`                 → /orders/{param}/route
      `${process.env.BACKEND_API_URL}/api/v1/x`  → /api/v1/x
    """
    cleaned = re.sub(r"^\$\{[^}]+\}", "", raw.strip())
    cleaned = re.sub(r"\$\{[^}]+\}", "{param}", cleaned)
    return cleaned.strip()


def _is_api_path(s: str) -> bool:
    """Return True if *s* looks like a backend API endpoint path."""
    if not s or len(s) < 3:
        return False
    if re.search(r"\s", s):
        return False
    # Absolute path: /something
    if s.startswith("/"):
        return bool(re.match(r"^/[a-zA-Z0-9\-_/{}.?=&@:]+$", s))
    # Relative path with a known FE codebase prefix, e.g. "guest/home-moving/goods"
    if any(s.startswith(p) for p in _RELATIVE_PREFIXES):
        return bool(re.match(r"^[a-z][a-zA-Z0-9\-_/{}.?=&@:]+$", s))
    return False


def _extract_call_block(content: str, open_paren_pos: int) -> str:
    """Return the slice of *content* from the opening '(' through its matching ')'.

    Respects nesting and skips string literals so brace characters inside
    strings are not counted.  Falls back to 800 chars on parse failure.
    """
    depth = 0
    i = open_paren_pos
    while i < len(content):
        ch = content[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return content[open_paren_pos: i + 1]
        elif ch == "`":
            i += 1
            while i < len(content) and content[i] != "`":
                if content[i] == "\\":
                    i += 1
                i += 1
        elif ch in ('"', "'"):
            quote = ch
            i += 1
            while i < len(content) and content[i] != quote:
                if content[i] == "\\":
                    i += 1
                i += 1
        i += 1
    return content[open_paren_pos: open_paren_pos + 800]


def _collect_paths(block: str) -> list[str]:
    """Extract all API-path-like string literals from a code block.

    Scanning the full argument block (rather than just the first argument)
    correctly handles conditional expressions like:
        axiosClient.post(
            condition ? "/path/a" : "/path/b",
            payload,
        )
    Both paths are returned.
    """
    seen: set[str] = set()
    paths: list[str] = []
    for m in _STRING_RE.finditer(block):
        raw = next(g for g in m.groups() if g is not None)
        url = _normalize_url(raw)
        if _is_api_path(url) and url not in seen:
            seen.add(url)
            paths.append(url)
    return paths


def _strip_comments(content: str) -> str:
    return _COMMENT_RE.sub("", content)


def _line_number(content: str, pos: int) -> int:
    return content.count("\n", 0, pos) + 1


def _scan_file(file_path: Path, repo_root: Path) -> list[FrontendApiCall]:
    """Extract all API calls from a single source file.

    For each axios / fetch call found, the complete parenthesised argument
    block is extracted and all endpoint-path string literals within it are
    collected.  This correctly handles:
      - Conditional expressions   (condition ? "/a" : "/b")
      - Template literals          (`/orders/${id}/route`)
      - TypeScript generics        (client.get<Type>("/path"))
      - Multi-line call arguments
    """
    calls: list[FrontendApiCall] = []
    try:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("[Scanner/FE] Cannot read %s: %s", file_path, exc)
        return calls

    relative = str(file_path.relative_to(repo_root))
    content = _strip_comments(raw)
    seen: set[tuple] = set()
    # Tracks every URL emitted (direct or fallback). Prevents a later fallback
    # scan from re-emitting the same URL under a different HTTP method when the
    # backward context window crosses a function boundary.
    confirmed: set[str] = set()

    # --- Named axios client calls -------------------------------------------
    for match in _CLIENT_CALL_RE.finditer(content):
        method = match.group(1).upper()
        # Pattern ends with \( — match.end()-1 is the position of '('.
        open_pos = match.end() - 1
        block = _extract_call_block(content, open_pos)
        lineno = _line_number(content, match.start())

        paths = _collect_paths(block)

        if paths:
            # Direct scan succeeded — method is authoritative.
            for url in paths:
                confirmed.add(url)
                key = (relative, method, url)
                if key not in seen:
                    seen.add(key)
                    calls.append(FrontendApiCall(
                        file=relative, method=method, url=url, line_number=lineno,
                    ))
        else:
            # The argument is a variable or constant; scan 600 chars before the
            # call to capture:
            #   let endpoint = "/auth/login";        (default ~400 chars away)
            #   if (...) endpoint = "/auth/login-by-kakao";  (reassignment)
            #   fn(path: "/orders/statistics") { axiosClient.get(path) }
            window_start = max(0, match.start() - 600)
            for url in _collect_paths(content[window_start: match.start()]):
                if url in confirmed:
                    # Already emitted with its correct method — skip to prevent
                    # re-emitting with a wrong method via window bleed.
                    continue
                confirmed.add(url)
                key = (relative, method, url)
                if key not in seen:
                    seen.add(key)
                    calls.append(FrontendApiCall(
                        file=relative, method=method, url=url, line_number=lineno,
                    ))

    # --- Server-side fetch() calls ------------------------------------------
    for match in _FETCH_CALL_RE.finditer(content):
        open_pos = match.end() - 1
        block = _extract_call_block(content, open_pos)
        lineno = _line_number(content, match.start())

        method_m = _FETCH_METHOD_RE.search(block)
        method = method_m.group(1).upper() if method_m else "GET"

        for url in _collect_paths(block):
            key = (relative, method, url)
            if key not in seen:
                seen.add(key)
                calls.append(FrontendApiCall(
                    file=relative, method=method, url=url, line_number=lineno,
                ))

    return calls


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_fe_repo(repo_path: str, branch: str = "main") -> list[FrontendApiCall]:
    """Scan a frontend repository and extract all outgoing API calls.

    Args:
        repo_path: Absolute or relative path to the frontend repo root.
        branch:    Git branch to scan (informational; assumes the working tree
                   is already checked out at the correct branch).

    Returns:
        List of FrontendApiCall instances, one per discovered API call.
    """
    logger.info("[Scanner/FE] scan_fe_repo called: path=%s  branch=%s", repo_path, branch)

    root = Path(repo_path).resolve()
    if not root.is_dir():
        logger.error("[Scanner/FE] Path does not exist or is not a directory: %s", root)
        return []

    all_calls: list[FrontendApiCall] = []
    file_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place so os.walk never descends into them.
        dirnames[:] = sorted(d for d in dirnames if d not in _IGNORE_DIRS)

        for filename in filenames:
            if Path(filename).suffix not in _SCAN_EXTENSIONS:
                continue

            file_path = Path(dirpath) / filename
            file_count += 1
            found = _scan_file(file_path, root)
            if found:
                logger.debug(
                    "[Scanner/FE] %s → %d call(s)",
                    file_path.relative_to(root),
                    len(found),
                )
            all_calls.extend(found)

    logger.info(
        "[Scanner/FE] Scan complete: %d file(s) scanned, %d API call(s) found.",
        file_count,
        len(all_calls),
    )
    return all_calls
