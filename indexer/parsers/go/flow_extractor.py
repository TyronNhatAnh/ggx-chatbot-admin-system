"""Extracts service flow chains from Go handler code.

Traces: HTTP handler → service layer → repository layer
by following the dependency injection pattern common in Go Gin apps:

    func (h *OrderHandler) GetOrder(c *gin.Context) {
        order, err := h.orderService.GetOrderByID(ctx, id)
                        ^^^^^^^^^^^  ^^^^^^^^^^^^^
                        receiver     method
    }

Uses tree-sitter for robust AST-based extraction when available,
falling back to regex for environments where tree-sitter is not installed.
"""

import logging
import re
from pathlib import Path

from indexer.models import CodeChunk, ServiceCall, ServiceFlow
from indexer.parsers.ts_utils import (
    find_child,
    find_children,
    is_available as _ts_available,
    node_end_line,
    node_start_line,
    node_text,
    parse_go,
    walk_descendants,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_NOISE_DEPS = frozenset({
    "Request", "Header", "Error", "Context", "Body", "URL",
    "Param", "Query", "PostForm", "Form", "Writer",
})

_NOISE_METHODS = frozenset({
    "UnixMilli", "Format", "String", "Error", "Sprintf", "Printf",
    "Println", "Errorf", "Wrapf", "New", "Background", "TODO",
})

_SERVICE_SUFFIXES = ("Service", "Svc", "Client", "Gateway", "Provider")
_REPO_SUFFIXES = ("Repo", "Repository", "Store", "DAO", "Cache")

_IGNORE_DIRS = frozenset({
    ".git", "vendor", "testdata", "test", "mocks", "__pycache__",
})

_MAX_HANDLER_BODY_LINES = 120


def _classify_dependency(dep_name: str) -> str:
    """Classify a dependency name as 'service', 'repository', or 'unknown'."""
    lower = dep_name.lower()
    if any(lower.endswith(s.lower()) for s in _REPO_SUFFIXES):
        return "repository"
    if any(lower.endswith(s.lower()) for s in _SERVICE_SUFFIXES):
        return "service"
    return "unknown"


def _truncate_body(body: str) -> tuple[str, bool]:
    """Limit handler body to _MAX_HANDLER_BODY_LINES lines."""
    lines = body.splitlines()
    if len(lines) <= _MAX_HANDLER_BODY_LINES:
        return body, False
    return "\n".join(lines[:_MAX_HANDLER_BODY_LINES]) + "\n// ... (truncated)", True


# ---------------------------------------------------------------------------
# Tree-sitter extraction
# ---------------------------------------------------------------------------


def _ts_resolve_selector_chain(node) -> list[str]:
    """Resolve a nested selector_expression into a list of identifiers.

    e.g. h.orderService.GetOrderByID → ["h", "orderService", "GetOrderByID"]
    """
    if node.type == "selector_expression":
        operand = find_child(node, "selector_expression") or find_child(node, "identifier")
        field = find_child(node, "field_identifier")
        if operand and field:
            return _ts_resolve_selector_chain(operand) + [node_text(field)]
    if node.type == "identifier":
        return [node_text(node)]
    return []


def _ts_extract_calls(body_node, receiver_var: str,
                      file_path: str) -> tuple[list[ServiceCall], list[ServiceCall]]:
    """Extract service/repository calls from a method body using AST."""
    service_calls: list[ServiceCall] = []
    repo_calls: list[ServiceCall] = []

    for call_node in walk_descendants(body_node, "call_expression"):
        func_node = call_node.children[0] if call_node.children else None
        if not func_node or func_node.type != "selector_expression":
            continue

        chain = _ts_resolve_selector_chain(func_node)
        # We want: receiver_var.depName.methodName (3 parts)
        if len(chain) != 3:
            continue

        root_var, dep_name, method_name = chain
        if root_var != receiver_var:
            continue
        if dep_name in _NOISE_DEPS or method_name in _NOISE_METHODS:
            continue

        call = ServiceCall(
            receiver=dep_name,
            method=method_name,
            file=file_path,
            line=node_start_line(call_node),
        )

        dep_type = _classify_dependency(dep_name)
        if dep_type == "repository":
            repo_calls.append(call)
        else:
            service_calls.append(call)

    return service_calls, repo_calls


def _ts_parse_method(node, source: bytes) -> tuple[str, str, str, str, int, int] | None:
    """Parse a method_declaration node.

    Returns (receiver_var, receiver_type, method_name, body_text, start_line, end_line)
    or None if not a method or receiver can't be parsed.
    """
    # receiver from parameter_list
    params = find_child(node, "parameter_list")
    if not params:
        return None
    param_decl = find_child(params, "parameter_declaration")
    if not param_decl:
        return None

    recv_id = find_child(param_decl, "identifier")
    if not recv_id:
        return None
    receiver_var = node_text(recv_id)

    # Receiver type: could be pointer_type → type_identifier, or just type_identifier
    ptr_node = find_child(param_decl, "pointer_type")
    if ptr_node:
        type_node = find_child(ptr_node, "type_identifier")
    else:
        type_node = find_child(param_decl, "type_identifier")
    if not type_node:
        return None
    receiver_type = node_text(type_node)

    # Method name: field_identifier after parameter_list
    method_node = find_child(node, "field_identifier")
    if not method_node:
        return None
    method_name = node_text(method_node)

    # Body block
    body_node = find_child(node, "block")
    if not body_node:
        return None

    body_text = node_text(body_node)
    start_line = node_start_line(body_node)
    end_line = node_end_line(body_node)

    return receiver_var, receiver_type, method_name, body_text, start_line, end_line


def _ts_extract_flows_from_file(source: bytes, rel_path: str, service: str,
                                endpoint_map: dict[str, str] | None = None,
                                ) -> list[ServiceFlow]:
    tree = parse_go(source)
    root = tree.root_node
    flows: list[ServiceFlow] = []

    for node in root.children:
        if node.type != "method_declaration":
            continue
        parsed = _ts_parse_method(node, source)
        if not parsed:
            continue

        receiver_var, receiver_type, method_name, _, _, _ = parsed
        if not receiver_type.endswith("Handler"):
            continue

        body_node = find_child(node, "block")
        if not body_node:
            continue

        svc_calls, repo_calls = _ts_extract_calls(body_node, receiver_var, rel_path)

        endpoint = ""
        if endpoint_map:
            endpoint = endpoint_map.get(method_name, "")

        flows.append(ServiceFlow(
            handler_name=method_name,
            handler_file=rel_path,
            endpoint=endpoint,
            service_calls=svc_calls,
            repository_calls=repo_calls,
            service=service,
        ))

    return flows


def _ts_extract_handler_chunks_from_file(
    source: bytes, rel_path: str, service: str,
    endpoint_map: dict[str, str] | None = None,
) -> list[CodeChunk]:
    tree = parse_go(source)
    root = tree.root_node
    chunks: list[CodeChunk] = []

    for node in root.children:
        if node.type != "method_declaration":
            continue
        parsed = _ts_parse_method(node, source)
        if not parsed:
            continue

        receiver_var, receiver_type, method_name, body_text, start_line, end_line = parsed
        if not receiver_type.endswith("Handler"):
            continue

        body_node = find_child(node, "block")
        if not body_node:
            continue

        truncated_body, was_truncated = _truncate_body(body_text)
        svc_calls, repo_calls = _ts_extract_calls(body_node, receiver_var, rel_path)

        calls_list = [f"{c.receiver}.{c.method}()" for c in svc_calls]
        calls_list += [f"{c.receiver}.{c.method}()" for c in repo_calls]

        endpoint = ""
        if endpoint_map:
            endpoint = endpoint_map.get(method_name, "")

        chunks.append(CodeChunk(
            qualified_name=f"{service}.{receiver_type}.{method_name}",
            content=truncated_body,
            chunk_type="handler",
            file=rel_path,
            service=service,
            start_line=start_line,
            end_line=end_line,
            metadata={
                "receiver_type": receiver_type,
                "endpoint": endpoint,
                "service_calls": calls_list,
                "truncated": was_truncated,
            },
        ))

    return chunks


# ---------------------------------------------------------------------------
# Regex fallback (original implementation)
# ---------------------------------------------------------------------------

_FUNC_DEF_RE = re.compile(
    r"func\s*\(\s*(\w+)\s+\*?(\w+)\s*\)\s*(\w+)\s*\("
)

_DEP_CALL_RE = re.compile(
    r"\b(\w+)\.(\w+)\.(\w+)\s*\("
)


def _regex_extract_function_body(content: str, def_start: int) -> tuple[str, int, int]:
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


def _regex_extract_calls_from_body(body: str, receiver_var: str,
                                   file_path: str) -> tuple[list[ServiceCall], list[ServiceCall]]:
    service_calls: list[ServiceCall] = []
    repo_calls: list[ServiceCall] = []

    for m in _DEP_CALL_RE.finditer(body):
        root_var, dep_name, method_name = m.groups()
        if dep_name in _NOISE_DEPS or method_name in _NOISE_METHODS:
            continue
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


def _regex_extract_flows_from_file(content: str, rel_path: str, service: str,
                                   endpoint_map: dict[str, str] | None = None,
                                   ) -> list[ServiceFlow]:
    flows: list[ServiceFlow] = []

    for m in _FUNC_DEF_RE.finditer(content):
        receiver_var = m.group(1)
        receiver_type = m.group(2)
        method_name = m.group(3)
        if not receiver_type.endswith("Handler"):
            continue

        body, start_line, end_line = _regex_extract_function_body(content, m.start())
        if not body:
            continue

        svc_calls, repo_calls = _regex_extract_calls_from_body(
            body, receiver_var, rel_path
        )

        endpoint = ""
        if endpoint_map:
            endpoint = endpoint_map.get(method_name, "")

        flows.append(ServiceFlow(
            handler_name=method_name,
            handler_file=rel_path,
            endpoint=endpoint,
            service_calls=svc_calls,
            repository_calls=repo_calls,
            service=service,
        ))

    return flows


def _regex_extract_handler_chunks_from_file(
    content: str, rel_path: str, service: str,
    endpoint_map: dict[str, str] | None = None,
) -> list[CodeChunk]:
    chunks: list[CodeChunk] = []

    for m in _FUNC_DEF_RE.finditer(content):
        receiver_var = m.group(1)
        receiver_type = m.group(2)
        method_name = m.group(3)
        if not receiver_type.endswith("Handler"):
            continue

        body, start_line, end_line = _regex_extract_function_body(content, m.start())
        if not body:
            continue

        truncated_body, was_truncated = _truncate_body(body)
        svc_calls, repo_calls = _regex_extract_calls_from_body(
            body, receiver_var, rel_path
        )

        calls_list = [f"{c.receiver}.{c.method}()" for c in svc_calls]
        calls_list += [f"{c.receiver}.{c.method}()" for c in repo_calls]

        endpoint = ""
        if endpoint_map:
            endpoint = endpoint_map.get(method_name, "")

        chunks.append(CodeChunk(
            qualified_name=f"{service}.{receiver_type}.{method_name}",
            content=truncated_body,
            chunk_type="handler",
            file=rel_path,
            service=service,
            start_line=start_line,
            end_line=end_line,
            metadata={
                "receiver_type": receiver_type,
                "endpoint": endpoint,
                "service_calls": calls_list,
                "truncated": was_truncated,
            },
        ))

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_flows_from_file(file_path: Path, repo_root: Path,
                            service: str,
                            endpoint_map: dict[str, str] | None = None,
                            ) -> list[ServiceFlow]:
    """Extract all service flows from a single Go file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(file_path.relative_to(repo_root))

    if _ts_available():
        return _ts_extract_flows_from_file(
            content.encode("utf-8"), rel_path, service, endpoint_map
        )
    return _regex_extract_flows_from_file(content, rel_path, service, endpoint_map)


def extract_handler_chunks_from_file(
    file_path: Path, repo_root: Path, service: str,
    endpoint_map: dict[str, str] | None = None,
) -> list[CodeChunk]:
    """Extract handler source-code chunks for each *Handler method."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(file_path.relative_to(repo_root))

    if _ts_available():
        return _ts_extract_handler_chunks_from_file(
            content.encode("utf-8"), rel_path, service, endpoint_map
        )
    return _regex_extract_handler_chunks_from_file(
        content, rel_path, service, endpoint_map
    )


def extract_flows_from_repo(repo_path: str, service: str) -> list[ServiceFlow]:
    """Walk a Go repository and extract all handler service flows."""
    from indexer.parsers.go.route_extractor import extract_routes_from_repo

    root = Path(repo_path).resolve()
    endpoint_map = extract_routes_from_repo(repo_path)

    all_flows: list[ServiceFlow] = []

    for go_file in root.rglob("*.go"):
        if any(part in _IGNORE_DIRS for part in go_file.parts):
            continue
        if go_file.name.endswith("_test.go") or go_file.name.endswith(".pb.go"):
            continue
        file_flows = extract_flows_from_file(go_file, root, service, endpoint_map)
        all_flows.extend(file_flows)

    logger.info(
        "[FlowExtractor] Found %d service flows across %s (tree-sitter=%s)",
        len(all_flows), service, _ts_available(),
    )
    return all_flows


def extract_handler_chunks_from_repo(repo_path: str, service: str) -> list[CodeChunk]:
    """Walk a Go repository and extract handler source-code chunks."""
    from indexer.parsers.go.route_extractor import extract_routes_from_repo

    root = Path(repo_path).resolve()
    endpoint_map = extract_routes_from_repo(repo_path)

    all_chunks: list[CodeChunk] = []

    for go_file in root.rglob("*.go"):
        if any(part in _IGNORE_DIRS for part in go_file.parts):
            continue
        if go_file.name.endswith("_test.go") or go_file.name.endswith(".pb.go"):
            continue
        chunks = extract_handler_chunks_from_file(go_file, root, service, endpoint_map)
        all_chunks.extend(chunks)

    logger.info(
        "[FlowExtractor] Extracted %d handler code chunks for %s (tree-sitter=%s)",
        len(all_chunks), service, _ts_available(),
    )
    return all_chunks
