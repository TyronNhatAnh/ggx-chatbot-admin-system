"""Extracts Spring Boot service flows from Java source code.

Handles both REST-exposed and non-REST (internal/admin) services:

  REST controllers:
    @RestController + @RequestMapping → endpoint detection
    @GetMapping / @PostMapping → method-level routes

  Non-REST services (web-admin, batch jobs, etc.):
    @Service classes with @Autowired dependencies
    @Scheduled methods
    @Component / @Configuration beans
    @EventListener / @TransactionalEventListener

Traces: Controller/Service → Service → Repository/Mapper
by following Spring DI (@Autowired, constructor injection).
"""

import logging
import re
from pathlib import Path

from indexer.models import CodeChunk, ServiceCall, ServiceFlow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns — class-level
# ---------------------------------------------------------------------------

# @RestController or @Controller class
_CONTROLLER_CLASS_RE = re.compile(
    r"@(?:Rest)?Controller\b"
)

# @Service / @Component / @Configuration class
_SERVICE_CLASS_RE = re.compile(
    r"@(?:Service|Component|Configuration)\b"
)

# @Repository / @Mapper class/interface
_REPO_CLASS_RE = re.compile(
    r"@(?:Repository|Mapper)\b"
)

# Class declaration (captures class name)
_CLASS_DEF_RE = re.compile(
    r"(?:public\s+)?(?:abstract\s+)?"
    r"(?:class|interface)\s+(\w+)"
    r"(?:<[^>]+>)?"
    r"(?:\s+extends\s+[\w.<>,\s]+?)?"
    r"(?:\s+implements\s+[\w.<>,\s]+?)?"
    r"\s*\{",
)

# @RequestMapping on class: @RequestMapping("/api/v1/orders")
_CLASS_MAPPING_RE = re.compile(
    r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?(?:\{[^}]*\}|["\']([^"\']+)["\'])',
)

# Method-level route annotations
_METHOD_MAPPING_RE = re.compile(
    r"@(Get|Post|Put|Delete|Patch)Mapping"
    r"(?:\s*\(\s*(?:value\s*=\s*)?[\"']([^\"']*)[\"'])?"
    r"(?:\s*\(\s*\))?"
)

# General @RequestMapping on method
_METHOD_REQUEST_MAPPING_RE = re.compile(
    r"@RequestMapping\s*\("
    r"[^)]*?(?:method\s*=\s*RequestMethod\.(\w+))?"
    r"[^)]*?(?:value\s*=\s*[\"']([^\"']+)[\"'])?"
    r"[^)]*\)",
    re.DOTALL,
)

# @Scheduled annotation
_SCHEDULED_RE = re.compile(
    r"@Scheduled\s*\([^)]*\)",
)

# @EventListener
_EVENT_LISTENER_RE = re.compile(
    r"@(?:TransactionalEventListener|EventListener)\b",
)

# ---------------------------------------------------------------------------
# Regex patterns — DI injection
# ---------------------------------------------------------------------------

# @Autowired field injection:
#   @Autowired private OrderService orderService;
_AUTOWIRED_FIELD_RE = re.compile(
    r"@(?:Autowired|Resource|Inject)\s+"
    r"(?:private|protected)?\s*"
    r"([\w<>]+)\s+"                           # (1) type
    r"(\w+)\s*;",                             # (2) field name
)

# Constructor parameter (for constructor injection):
#   private final OrderService orderService;
_FINAL_FIELD_RE = re.compile(
    r"(?:private|protected)\s+final\s+"
    r"([\w<>]+)\s+"                           # (1) type
    r"(\w+)\s*;",                             # (2) field name
)

# ---------------------------------------------------------------------------
# Regex patterns — method detection
# ---------------------------------------------------------------------------

# Java method definition:
#   public ResponseEntity<OrderDTO> getOrder(@PathVariable Long id) {
#   public void processExpiredOrders() {
_METHOD_DEF_RE = re.compile(
    r"(?:public|protected|private)\s+"
    r"(?:static\s+)?"
    r"(?:(?:synchronized|final)\s+)?"
    r"([\w<>\[\]?,\s]+?)\s+"                  # (1) return type
    r"(\w+)\s*\("                             # (2) method name
    r"([^)]*)\)\s*"                           # (3) parameters
    r"(?:throws\s+[\w,\s]+)?\s*\{",          # optional throws
)

# Calls to injected dependencies:
#   orderService.getOrderById(id)
#   orderRepo.findById(id)
#   orderMapper.selectByPrimaryKey(id)
_DEP_CALL_RE = re.compile(
    r"\b(\w+)\s*\.\s*(\w+)\s*\(",
)

# Noise methods to ignore
_NOISE_METHODS = frozenset({
    "toString", "equals", "hashCode", "valueOf", "format",
    "getMessage", "getClass", "getLogger", "getName",
    "info", "warn", "error", "debug", "trace",
    "get", "set", "put", "add", "remove", "size", "isEmpty",
    "stream", "filter", "map", "collect", "forEach", "of",
    "orElse", "orElseThrow", "isPresent", "ifPresent",
    "ok", "status", "body", "build", "builder",
    "parseInt", "parseLong", "parseDouble",
    "currentTimeMillis", "nanoTime", "now",
    "getBean", "getProperty",
})

# Noise field names to ignore
_NOISE_FIELDS = frozenset({
    "log", "logger", "LOG", "LOGGER",
    "objectMapper", "modelMapper", "conversionService",
    "messageSource", "applicationContext",
    "jdbcTemplate", "namedParameterJdbcTemplate",
    "restTemplate", "webClient",
    "transactionTemplate", "entityManager",
})

# Heuristic classification by type name suffix
_SERVICE_SUFFIXES = ("Service", "Svc", "Client", "Gateway", "Provider", "Facade", "Manager")
_REPO_SUFFIXES = ("Repository", "Repo", "Mapper", "Dao", "DAO", "Store", "Cache")

_IGNORE_DIRS = frozenset({
    ".git", "target", "build", ".gradle", ".idea", ".mvn",
    "test", "tests", "node_modules", "__pycache__",
})

_MAX_METHOD_BODY_LINES = 120


def _classify_dependency(field_name: str, field_type: str) -> str:
    """Classify a dependency as 'service', 'repository', or 'unknown'."""
    for s in _REPO_SUFFIXES:
        if field_type.endswith(s) or field_name.lower().endswith(s.lower()):
            return "repository"
    for s in _SERVICE_SUFFIXES:
        if field_type.endswith(s) or field_name.lower().endswith(s.lower()):
            return "service"
    return "unknown"


def _extract_balanced_brace(content: str, open_pos: int) -> tuple[str, int, int]:
    """Extract balanced-brace body. Returns (body, start_line, end_line)."""
    idx = content.find("{", open_pos)
    if idx == -1:
        return "", 0, 0

    depth = 0
    i = idx
    in_string = False
    string_char = ""
    while i < len(content):
        ch = content[i]
        if in_string:
            if ch == "\\" :
                i += 2
                continue
            if ch == string_char:
                in_string = False
        else:
            if ch in ('"', "'"):
                in_string = True
                string_char = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    body = content[idx:i + 1]
                    start_line = content[:idx].count("\n") + 1
                    end_line = content[:i + 1].count("\n") + 1
                    return body, start_line, end_line
        i += 1
    return "", 0, 0


def _extract_injected_deps(class_body: str) -> dict[str, str]:
    """Build {field_name: field_type} map for injected dependencies."""
    deps: dict[str, str] = {}

    for m in _AUTOWIRED_FIELD_RE.finditer(class_body):
        field_type, field_name = m.group(1), m.group(2)
        if field_name not in _NOISE_FIELDS:
            deps[field_name] = field_type

    for m in _FINAL_FIELD_RE.finditer(class_body):
        field_type, field_name = m.group(1), m.group(2)
        if field_name not in _NOISE_FIELDS:
            # Only count as DI if the type looks like a service/repo
            dep_class = _classify_dependency(field_name, field_type)
            if dep_class != "unknown":
                deps[field_name] = field_type

    return deps


def _extract_calls_from_body(body: str, injected_deps: dict[str, str],
                               file_path: str) -> tuple[list[ServiceCall], list[ServiceCall]]:
    """Parse a method body for service and repository calls."""
    service_calls: list[ServiceCall] = []
    repo_calls: list[ServiceCall] = []

    for m in _DEP_CALL_RE.finditer(body):
        field_name, method_name = m.group(1), m.group(2)

        if method_name in _NOISE_METHODS:
            continue
        if field_name in _NOISE_FIELDS:
            continue
        if field_name == "this" or field_name == "super":
            continue

        # Only follow calls on known injected dependencies
        if field_name not in injected_deps:
            continue

        field_type = injected_deps[field_name]
        call = ServiceCall(
            receiver=field_name,
            method=method_name,
            file=file_path,
        )

        dep_class = _classify_dependency(field_name, field_type)
        if dep_class == "repository":
            repo_calls.append(call)
        else:
            service_calls.append(call)

    return service_calls, repo_calls


def _resolve_method_endpoint(
    method_name: str,
    method_start: int,
    content: str,
    base_path: str,
) -> str:
    """Resolve the HTTP endpoint for a controller method."""
    # Find the annotation block directly above this method.
    # Walk backwards from method_start, collecting annotation and blank lines,
    # stop at the first non-annotation, non-blank, non-comment line.
    prefix = content[:method_start]
    lines = prefix.rstrip().split("\n")
    ann_lines: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("@") or stripped == "" or stripped.startswith("//"):
            ann_lines.append(stripped)
        else:
            break
    search_window = "\n".join(reversed(ann_lines))

    # Try @GetMapping, @PostMapping, etc.
    for mm in _METHOD_MAPPING_RE.finditer(search_window):
        http_method = mm.group(1).upper()
        path = mm.group(2) or ""
        full = base_path.rstrip("/")
        if path:
            full = full + "/" + path.lstrip("/")
        return f"{http_method} {full}" if full else f"{http_method} /"

    # Try @RequestMapping(method=RequestMethod.GET, value="/path")
    for mm in _METHOD_REQUEST_MAPPING_RE.finditer(search_window):
        http_method = (mm.group(1) or "GET").upper()
        path = mm.group(2) or ""
        full = base_path.rstrip("/")
        if path:
            full = full + "/" + path.lstrip("/")
        return f"{http_method} {full}" if full else f"{http_method} /"

    return ""


def _is_scheduled_method(content: str, method_start: int) -> bool:
    """Check if a method has @Scheduled annotation."""
    prefix = content[max(0, method_start - 300):method_start]
    return bool(_SCHEDULED_RE.search(prefix))


def _is_event_listener(content: str, method_start: int) -> bool:
    """Check if a method has @EventListener annotation."""
    prefix = content[max(0, method_start - 300):method_start]
    return bool(_EVENT_LISTENER_RE.search(prefix))


def extract_flows_from_file(file_path: Path, repo_root: Path,
                            service: str) -> list[ServiceFlow]:
    """Extract service flows from a single Java file.

    Handles:
    - REST controller methods (with endpoint resolution)
    - @Service methods that call other services/repos
    - @Scheduled methods
    - @EventListener methods
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(file_path.relative_to(repo_root))
    flows: list[ServiceFlow] = []

    # Determine class type and base path
    is_controller = bool(_CONTROLLER_CLASS_RE.search(content))
    is_service = bool(_SERVICE_CLASS_RE.search(content))
    is_repo = bool(_REPO_CLASS_RE.search(content))

    # Skip pure repository/mapper files — no flows to trace
    if is_repo and not is_service and not is_controller:
        return []

    # Get class name
    class_m = _CLASS_DEF_RE.search(content)
    if not class_m:
        return []
    class_name = class_m.group(1)

    # Get base request mapping path (controllers only)
    base_path = ""
    if is_controller:
        bp = _CLASS_MAPPING_RE.search(content)
        if bp:
            base_path = bp.group(1) or ""

    # Build injected dependency map
    injected_deps = _extract_injected_deps(content)
    if not injected_deps and not is_controller:
        return []  # No dependencies to trace, no endpoints

    # Find all methods and extract flows
    for m in _METHOD_DEF_RE.finditer(content):
        return_type = m.group(1).strip()
        method_name = m.group(2)

        # Skip constructors, getters, setters
        if method_name == class_name:
            continue
        if method_name.startswith("get") and len(m.group(3).strip()) == 0:
            continue
        if method_name.startswith("set") and return_type == "void":
            param_count = len([p for p in m.group(3).split(",") if p.strip()])
            if param_count == 1:
                continue

        body, start_line, end_line = _extract_balanced_brace(content, m.start())
        if not body:
            continue

        svc_calls, repo_calls = _extract_calls_from_body(
            body, injected_deps, rel_path,
        )

        # Skip methods with no dependency calls (unless controller endpoint or scheduled)
        is_scheduled = _is_scheduled_method(content, m.start())
        is_listener = _is_event_listener(content, m.start())

        endpoint = ""
        if is_controller:
            endpoint = _resolve_method_endpoint(
                method_name, m.start(), content, base_path,
            )

        if not svc_calls and not repo_calls:
            if not endpoint and not is_scheduled and not is_listener:
                continue

        # Build description for non-REST entry points
        description = ""
        if is_scheduled:
            description = "[scheduled]"
            endpoint = f"SCHEDULED {class_name}.{method_name}"
        elif is_listener:
            description = "[event-listener]"
            endpoint = f"EVENT {class_name}.{method_name}"
        elif not endpoint and is_service:
            endpoint = f"INTERNAL {class_name}.{method_name}"

        handler_name = f"{class_name}.{method_name}"

        flows.append(ServiceFlow(
            handler_name=handler_name,
            handler_file=rel_path,
            endpoint=endpoint,
            service_calls=svc_calls,
            repository_calls=repo_calls,
            service=service,
            description=description,
        ))

    return flows


def _truncate_body(body: str) -> tuple[str, bool]:
    """Limit method body to _MAX_METHOD_BODY_LINES lines."""
    lines = body.splitlines()
    if len(lines) <= _MAX_METHOD_BODY_LINES:
        return body, False
    return "\n".join(lines[:_MAX_METHOD_BODY_LINES]) + "\n// ... (truncated)", True


def extract_handler_chunks_from_file(
    file_path: Path, repo_root: Path, service: str,
) -> list[CodeChunk]:
    """Extract method source-code chunks for controllers and services."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(file_path.relative_to(repo_root))
    chunks: list[CodeChunk] = []

    is_controller = bool(_CONTROLLER_CLASS_RE.search(content))
    is_service = bool(_SERVICE_CLASS_RE.search(content))

    if not is_controller and not is_service:
        return []

    class_m = _CLASS_DEF_RE.search(content)
    if not class_m:
        return []
    class_name = class_m.group(1)

    base_path = ""
    if is_controller:
        bp = _CLASS_MAPPING_RE.search(content)
        if bp:
            base_path = bp.group(1) or ""

    injected_deps = _extract_injected_deps(content)

    for m in _METHOD_DEF_RE.finditer(content):
        method_name = m.group(2)

        # Skip constructors
        if method_name == class_name:
            continue

        body, start_line, end_line = _extract_balanced_brace(content, m.start())
        if not body:
            continue

        svc_calls, repo_calls = _extract_calls_from_body(body, injected_deps, rel_path)

        # Only chunk methods that do real work
        if not svc_calls and not repo_calls:
            is_scheduled = _is_scheduled_method(content, m.start())
            has_endpoint = False
            if is_controller:
                has_endpoint = bool(_resolve_method_endpoint(
                    method_name, m.start(), content, base_path,
                ))
            if not is_scheduled and not has_endpoint:
                continue

        truncated_body, was_truncated = _truncate_body(body)
        calls_list = [f"{c.receiver}.{c.method}()" for c in svc_calls]
        calls_list += [f"{c.receiver}.{c.method}()" for c in repo_calls]

        endpoint = ""
        if is_controller:
            endpoint = _resolve_method_endpoint(
                method_name, m.start(), content, base_path,
            )

        chunk_type = "handler" if is_controller else "service_method"

        chunks.append(CodeChunk(
            qualified_name=f"{service}.{class_name}.{method_name}",
            content=truncated_body,
            chunk_type=chunk_type,
            file=rel_path,
            service=service,
            start_line=start_line,
            end_line=end_line,
            metadata={
                "class_name": class_name,
                "endpoint": endpoint,
                "service_calls": calls_list,
                "truncated": was_truncated,
                "is_controller": is_controller,
            },
        ))

    return chunks


def extract_flows_from_repo(repo_path: str, service: str) -> list[ServiceFlow]:
    """Walk a Java repository and extract all service flows."""
    root = Path(repo_path).resolve()
    all_flows: list[ServiceFlow] = []

    for java_file in root.rglob("*.java"):
        if any(part in _IGNORE_DIRS for part in java_file.parts):
            continue
        if java_file.name.endswith("Test.java") or java_file.name.endswith("Tests.java"):
            continue
        file_flows = extract_flows_from_file(java_file, root, service)
        all_flows.extend(file_flows)

    logger.info(
        "[Java FlowExtractor] Found %d service flows across %s",
        len(all_flows), service,
    )
    return all_flows


def extract_handler_chunks_from_repo(repo_path: str, service: str) -> list[CodeChunk]:
    """Walk a Java repository and extract method source-code chunks."""
    root = Path(repo_path).resolve()
    all_chunks: list[CodeChunk] = []

    for java_file in root.rglob("*.java"):
        if any(part in _IGNORE_DIRS for part in java_file.parts):
            continue
        if java_file.name.endswith("Test.java") or java_file.name.endswith("Tests.java"):
            continue
        file_chunks = extract_handler_chunks_from_file(java_file, root, service)
        all_chunks.extend(file_chunks)

    logger.info(
        "[Java FlowExtractor] Extracted %d method source-code chunks across %s",
        len(all_chunks), service,
    )
    return all_chunks
