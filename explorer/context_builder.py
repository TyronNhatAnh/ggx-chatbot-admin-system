"""Code context builder — extracts Go handler source code for each discovered endpoint.

For every entry in ``be_endpoint_map.json``, locates the handler function in the
Go source tree, extracts its body, detects service calls, and writes a Markdown
context file to ``docs/discovery/code_context/``.

Output file naming: ``{FunctionName}.context.md``

Usage (from project root)::

    from explorer.context_builder import build_code_context
    build_code_context(be_repo_path="/path/to/go-backend")
"""

import json
import logging
import os
import re
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_IGNORE_DIRS = frozenset({
    ".git", "vendor", "testdata", "test", "mocks", "__pycache__",
})

_ENDPOINT_MAP_FILE = "be_endpoint_map.json"
_OUTPUT_SUBDIR = "code_context"

# Truncate extracted bodies beyond this many lines to keep context files readable.
_MAX_BODY_LINES = 120

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches Go method definitions on named receiver types:
#   func (h *OrderHandler) SubmitOrder(c *gin.Context) {
# Groups: (1) receiver type, (2) method name
_FUNC_DEF_RE = re.compile(
    r"func\s*\(\s*\w+\s+\*?(\w+)\s*\)\s*(\w+)\s*\("
)

# Matches two-level dot-access calls that indicate service/repo dependencies:
#   h.orderService.CreateOrder(   →  dep="orderService"  method="CreateOrder"
_SERVICE_CALL_RE = re.compile(r"\b\w+\.(\w+)\.(\w+)\s*\(")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_function_body(content: str, def_start: int) -> str:
    """Return the full balanced-brace body of the function starting at *def_start*.

    Handles Go string literals (double-quoted and backtick raw strings) so that
    brace characters inside strings are not counted towards the depth.
    """
    open_idx = content.find("{", def_start)
    if open_idx == -1:
        return ""

    depth = 0
    i = open_idx

    while i < len(content):
        ch = content[i]

        if ch == "`":
            # Raw string literal — skip everything until the closing backtick.
            i += 1
            while i < len(content) and content[i] != "`":
                i += 1
        elif ch == '"':
            # Interpreted string literal — respect escape sequences.
            i += 1
            while i < len(content) and content[i] != '"':
                if content[i] == "\\":
                    i += 1  # Skip escaped character.
                i += 1
        elif ch == "/":
            # Line comment — skip to end of line.
            if i + 1 < len(content) and content[i + 1] == "/":
                i = content.find("\n", i)
                if i == -1:
                    break
            # Block comment.
            elif i + 1 < len(content) and content[i + 1] == "*":
                i = content.find("*/", i + 2)
                if i == -1:
                    break
                i += 1  # Skip past '*'.
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return content[open_idx : i + 1]

        i += 1

    # Unterminated — return whatever we collected so far.
    return content[open_idx:]


def _truncate_body(body: str, max_lines: int = _MAX_BODY_LINES) -> tuple[str, bool]:
    """Return the body limited to *max_lines* lines and a flag indicating truncation."""
    lines = body.splitlines()
    if len(lines) <= max_lines:
        return body, False
    return "\n".join(lines[:max_lines]) + "\n// ... (truncated)", True


def _detect_service_calls(body: str) -> list[str]:
    """Return unique service/repository call strings found in a function body.

    Detects the pattern ``receiver.dependency.Method()`` which indicates the
    handler delegating to an injected service or repository field.
    """
    seen: set[str] = set()
    calls: list[str] = []
    for m in _SERVICE_CALL_RE.finditer(body):
        dep = m.group(1)    # e.g. "orderService"
        method = m.group(2)  # e.g. "CreateOrder"
        key = f"{dep}.{method}()"
        if key not in seen:
            seen.add(key)
            calls.append(key)
    return calls


def _build_function_index(repo_root: Path) -> dict[str, list[tuple[str, str, str]]]:
    """Walk *repo_root* once and index Go methods by name.

    Returns:
        ``{method_name: [(relative_file_path, receiver_type, body), ...]}``
    """
    index: dict[str, list[tuple[str, str, str]]] = {}

    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Prune ignored directories in-place.
        dirnames[:] = sorted(d for d in dirnames if d not in _IGNORE_DIRS)

        for filename in filenames:
            if not filename.endswith(".go"):
                continue

            file_path = Path(dirpath) / filename
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                logger.warning("[ContextBuilder] Cannot read %s: %s", file_path, exc)
                continue

            relative = str(file_path.relative_to(repo_root))

            for m in _FUNC_DEF_RE.finditer(content):
                receiver_type = m.group(1)
                method_name = m.group(2)
                body = _extract_function_body(content, m.start())

                index.setdefault(method_name, []).append(
                    (relative, receiver_type, body)
                )

    logger.info(
        "[ContextBuilder] Function index built: %d unique method names.", len(index)
    )
    return index


def _sanitize_filename(name: str) -> str:
    """Replace characters that are unsafe for filenames with underscores."""
    return re.sub(r"[^\w\-]", "_", name)


def _render_context_md(
    endpoint: dict,
    file_path: str,
    receiver_type: str,
    body: str,
    service_calls: list[str],
    truncated: bool,
) -> str:
    """Render a Markdown context document for a single endpoint."""
    method = endpoint.get("method", "")
    path = endpoint.get("path", "")
    handler = endpoint.get("handler", "")
    function = endpoint.get("function", "")

    if service_calls:
        calls_section = "\n".join(f"- `{c}`" for c in service_calls)
    else:
        calls_section = "_No service calls detected._"

    truncation_note = "\n> **Note:** Body truncated to first 120 lines.\n" if truncated else ""

    return (
        f"# {function}\n\n"
        f"## Endpoint\n`{method} {path}`\n\n"
        f"## Handler\n"
        f"- **Variable:** `{handler}`\n"
        f"- **Receiver type:** `{receiver_type}`\n"
        f"- **Method:** `{function}`\n\n"
        f"## File\n`{file_path}`\n\n"
        f"## Handler Code\n"
        f"{truncation_note}"
        f"```go\n{body}\n```\n\n"
        f"## Detected Service Calls\n\n"
        f"{calls_section}\n"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_code_context(
    be_repo_path: str,
    index_path: str | None = None,
    output_dir: str | None = None,
) -> list[Path]:
    """Build Markdown context files for all endpoints in the backend index.

    For each endpoint in ``be_endpoint_map.json``, locates its handler function
    in the Go source tree, extracts the body, detects service dependencies, and
    writes a ``{FunctionName}.context.md`` file.

    Args:
        be_repo_path: Absolute or relative path to the Go backend repository root.
        index_path:   Path to ``be_endpoint_map.json``.  Defaults to
                      ``{settings.discovery_output_dir}/be_endpoint_map.json``.
        output_dir:   Destination directory for the generated context files.
                      Defaults to ``{settings.discovery_output_dir}/code_context/``.

    Returns:
        List of Paths to the written ``.context.md`` files.
    """
    repo_root = Path(be_repo_path).resolve()
    if not repo_root.is_dir():
        logger.error("[ContextBuilder] Repo path not found or not a directory: %s", repo_root)
        return []

    # Resolve the endpoint index file.
    resolved_index = (
        Path(index_path)
        if index_path
        else Path(settings.discovery_output_dir) / _ENDPOINT_MAP_FILE
    )
    if not resolved_index.exists():
        logger.error(
            "[ContextBuilder] Endpoint index not found: %s — run scan-be first.", resolved_index
        )
        return []

    with resolved_index.open(encoding="utf-8") as f:
        endpoints: list[dict] = json.load(f)

    # Resolve and create the output directory.
    resolved_output = (
        Path(output_dir)
        if output_dir
        else Path(settings.discovery_output_dir) / _OUTPUT_SUBDIR
    )
    resolved_output.mkdir(parents=True, exist_ok=True)

    logger.info(
        "[ContextBuilder] %d endpoints loaded. Scanning repo: %s",
        len(endpoints),
        repo_root,
    )

    # Build the function index once — O(n) walk of the entire repo.
    func_index = _build_function_index(repo_root)

    written: list[Path] = []
    skipped = 0

    for ep in endpoints:
        func_name = ep.get("function", "").strip()
        if not func_name:
            continue

        matches = func_index.get(func_name)
        if not matches:
            logger.debug("[ContextBuilder] Handler not found in source: %s", func_name)
            skipped += 1
            continue

        # Prefer non-test files when multiple definitions exist.
        match = next(
            (m for m in matches if not m[0].endswith("_test.go")),
            matches[0],
        )
        file_path, receiver_type, raw_body = match

        body, truncated = _truncate_body(raw_body)
        service_calls = _detect_service_calls(body)

        md_content = _render_context_md(
            endpoint=ep,
            file_path=file_path,
            receiver_type=receiver_type,
            body=body,
            service_calls=service_calls,
            truncated=truncated,
        )

        out_file = resolved_output / f"{_sanitize_filename(func_name)}.context.md"
        out_file.write_text(md_content, encoding="utf-8")
        written.append(out_file)
        logger.debug("[ContextBuilder] Written: %s", out_file.name)

    logger.info(
        "[ContextBuilder] Done: %d context file(s) written, %d skipped (handler not found in source).",
        len(written),
        skipped,
    )
    return written
