"""Extracts service flow chains from Go handler code.

Traces: HTTP handler → service layer → repository layer
by following the dependency injection pattern common in Go Gin apps:

    func (h *OrderHandler) GetOrder(c *gin.Context) {
        order, err := h.orderService.GetOrderByID(ctx, id)
                        ^^^^^^^^^^^  ^^^^^^^^^^^^^
                        receiver     method
    }

Builds ServiceFlow objects that describe the full execution path
for each endpoint, giving the chatbot deep understanding of what
each API call actually does under the hood.
"""

import logging
import re
from pathlib import Path

from indexer.models import ServiceCall, ServiceFlow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Go method definition on a named receiver:
#   func (h *OrderHandler) SubmitOrder(c *gin.Context) {
# Groups: (1) receiver var, (2) receiver type, (3) method name
_FUNC_DEF_RE = re.compile(
    r"func\s*\(\s*(\w+)\s+\*?(\w+)\s*\)\s*(\w+)\s*\("
)

# Two-level dot-access calls: h.orderService.CreateOrder(...)
# Groups: (1) root var, (2) dependency name, (3) method name
_DEP_CALL_RE = re.compile(
    r"\b(\w+)\.(\w+)\.(\w+)\s*\("
)

# Noise receivers that aren't real service dependencies
_NOISE_DEPS = frozenset({
    "Request", "Header", "Error", "Context", "Body", "URL",
    "Param", "Query", "PostForm", "Form", "Writer",
})

_NOISE_METHODS = frozenset({
    "UnixMilli", "Format", "String", "Error", "Sprintf", "Printf",
    "Println", "Errorf", "Wrapf", "New", "Background", "TODO",
})

# Heuristic: receivers whose name ends with these are service-layer
_SERVICE_SUFFIXES = ("Service", "Svc", "Client", "Gateway", "Provider")
_REPO_SUFFIXES = ("Repo", "Repository", "Store", "DAO", "Cache")

_IGNORE_DIRS = frozenset({
    ".git", "vendor", "testdata", "test", "mocks", "__pycache__",
})


def _classify_dependency(dep_name: str) -> str:
    """Classify a dependency name as 'service', 'repository', or 'unknown'."""
    lower = dep_name.lower()
    if any(lower.endswith(s.lower()) for s in _REPO_SUFFIXES):
        return "repository"
    if any(lower.endswith(s.lower()) for s in _SERVICE_SUFFIXES):
        return "service"
    return "unknown"


def _extract_function_body(content: str, def_start: int) -> tuple[str, int, int]:
    """Extract the balanced-brace body of a function starting at def_start.
    Returns (body_text, start_line, end_line).
    """
    open_idx = content.find("{", def_start)
    if open_idx == -1:
        return "", 0, 0

    depth = 0
    i = open_idx

    while i < len(content):
        ch = content[i]
        if ch == "`":
            i += 1
            while i < len(content) and content[i] != "`":
                i += 1
        elif ch == '"':
            i += 1
            while i < len(content) and content[i] != '"':
                if content[i] == "\\":
                    i += 1
                i += 1
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                body = content[open_idx:i + 1]
                start_line = content[:open_idx].count("\n") + 1
                end_line = content[:i + 1].count("\n") + 1
                return body, start_line, end_line
        i += 1

    return "", 0, 0


def _extract_calls_from_body(body: str, receiver_var: str,
                               file_path: str) -> tuple[list[ServiceCall], list[ServiceCall]]:
    """Parse a function body for service and repository calls."""
    service_calls: list[ServiceCall] = []
    repo_calls: list[ServiceCall] = []

    for m in _DEP_CALL_RE.finditer(body):
        root_var, dep_name, method_name = m.groups()

        if dep_name in _NOISE_DEPS or method_name in _NOISE_METHODS:
            continue

        # Only follow calls on the handler's own receiver (h.service.Method)
        if root_var != receiver_var:
            continue

        call = ServiceCall(
            receiver=dep_name,
            method=method_name,
            file=file_path,
        )

        dep_type = _classify_dependency(dep_name)
        if dep_type == "repository":
            repo_calls.append(call)
        else:
            service_calls.append(call)

    return service_calls, repo_calls


def extract_flows_from_file(file_path: Path, repo_root: Path,
                            service: str) -> list[ServiceFlow]:
    """Extract all service flows from a single Go file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(file_path.relative_to(repo_root))
    flows: list[ServiceFlow] = []

    for m in _FUNC_DEF_RE.finditer(content):
        receiver_var = m.group(1)
        receiver_type = m.group(2)
        method_name = m.group(3)

        # Only extract from handler types (convention: *XxxHandler)
        if not receiver_type.endswith("Handler"):
            continue

        body, start_line, end_line = _extract_function_body(content, m.start())
        if not body:
            continue

        svc_calls, repo_calls = _extract_calls_from_body(
            body, receiver_var, rel_path
        )

        flows.append(ServiceFlow(
            handler_name=method_name,
            handler_file=rel_path,
            service_calls=svc_calls,
            repository_calls=repo_calls,
            service=service,
        ))

    return flows


def extract_flows_from_repo(repo_path: str, service: str) -> list[ServiceFlow]:
    """Walk a Go repository and extract all handler service flows.

    Args:
        repo_path: Path to the Go repository root.
        service: Service name (e.g. "order-service").

    Returns:
        List of ServiceFlow, one per handler function found.
    """
    root = Path(repo_path).resolve()
    all_flows: list[ServiceFlow] = []

    for go_file in root.rglob("*.go"):
        if any(part in _IGNORE_DIRS for part in go_file.parts):
            continue
        if go_file.name.endswith("_test.go"):
            continue
        file_flows = extract_flows_from_file(go_file, root, service)
        all_flows.extend(file_flows)

    logger.info(
        "[FlowExtractor] Found %d service flows across %s",
        len(all_flows), service,
    )
    return all_flows
