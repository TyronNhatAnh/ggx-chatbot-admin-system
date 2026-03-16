"""React/TypeScript LanguageParser — indexes a Next.js frontend repository.

Extracts:
  - Routes from Next.js Pages Router file structure
  - React components (function/const exports)
  - API calls via axios clients, API modules, SWR hooks, Redux thunks
  - Component → API mappings as ServiceFlow objects

Designed for the web2 (ggx-kr-consumer-web) codebase structure:
  src/lib/apis/*.ts        — API service modules (OrderAPIs, UserAPIs, …)
  src/lib/common/helpers/   — axios client factory + interceptors
  src/pages/**/*.tsx        — Next.js Pages Router
  src/lib/containers/       — feature containers (call APIs + dispatch thunks)
  src/lib/ducks/            — Redux slices + thunks
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from indexer.models import Edge, EnumGroup, EnumValue, ServiceCall, ServiceFlow, StructDefinition, StructField
from indexer.parsers.base import LanguageParser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns — API calls
# ---------------------------------------------------------------------------

# Named axios client calls: orderServiceApiClient.get("/orders/123")
_AXIOS_CLIENT_RE = re.compile(
    r"(\w+(?:Service|DA)?\w*(?:Api|api)Client)\s*\.\s*(get|post|put|patch|delete)\s*"
    r"[<(]\s*[^)]*?[`\"']([^`\"']+)[`\"']",
    re.IGNORECASE,
)

# API module method calls: OrderAPIs.getOrder(id)
_API_MODULE_CALL_RE = re.compile(
    r"(\w+APIs?)\s*\.\s*(\w+)\s*\(",
)

# Direct axios/fetch calls: axios.get("/api/..."), fetch("/api/...")
_DIRECT_AXIOS_RE = re.compile(
    r"(?:axios|axiosClient)\s*\.\s*(get|post|put|patch|delete)\s*"
    r"[<(]\s*[^)]*?[`\"']([^`\"']+)[`\"']",
    re.IGNORECASE,
)

_FETCH_RE = re.compile(
    r"fetch\s*\(\s*[`\"']([^`\"']+)[`\"']",
)

# SWR pattern: useSWR(key, () => OrderAPIs.getOrder(...))
_SWR_API_RE = re.compile(
    r"useSWR(?:Infinite|Immutable|Mutation)?\s*\([^)]*?(\w+APIs?)\s*\.\s*(\w+)",
    re.DOTALL,
)

# Redux thunk: createAppAsyncThunk("auth/login", (...) => UserAPIs.login(...))
_THUNK_API_RE = re.compile(
    r"create(?:App)?AsyncThunk\s*\(\s*[\"']([^\"']+)[\"'][^)]*?(\w+APIs?)\s*\.\s*(\w+)",
    re.DOTALL,
)

# ---------------------------------------------------------------------------
# Regex patterns — components
# ---------------------------------------------------------------------------

# function ComponentName( or function ComponentName<
_FUNC_COMPONENT_RE = re.compile(
    r"(?:export\s+(?:default\s+)?)?function\s+([A-Z]\w+)\s*[<(]",
)

# const ComponentName = (...) => or const ComponentName: React.FC
_CONST_COMPONENT_RE = re.compile(
    r"(?:export\s+(?:default\s+)?)?const\s+([A-Z]\w+)\s*"
    r"(?::\s*\w[\w.<>,\s|]*\s*)?=\s*(?:\([^)]*\)\s*=>|React\.)",
)

# export default ComponentName (standalone)
_DEFAULT_EXPORT_RE = re.compile(
    r"export\s+default\s+([A-Z]\w+)\s*;?\s*$",
    re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Regex patterns — routes (React Router / Next.js config)
# ---------------------------------------------------------------------------

# <Route path="/orders/:id" ...>
_ROUTE_JSX_RE = re.compile(
    r"<Route\s+[^>]*path\s*=\s*[{\"']([^\"'}]+)[\"'}]",
)

# { path: "/orders/:id", ... }
_ROUTE_OBJ_RE = re.compile(
    r"path\s*:\s*[\"']([^\"']+)[\"']",
)

# ---------------------------------------------------------------------------
# Regex patterns — TypeScript types/interfaces
# ---------------------------------------------------------------------------

_INTERFACE_RE = re.compile(
    r"(?:export\s+)?interface\s+(\w+)\s*(?:extends\s+[\w,\s<>]+)?\s*\{",
)

_TYPE_ALIAS_RE = re.compile(
    r"(?:export\s+)?type\s+(\w+)\s*(?:<[^>]*>)?\s*=\s*\{",
)

_TS_FIELD_RE = re.compile(
    r"^\s+(\w+)(\??):\s*(.+?);?\s*$",
    re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Regex patterns — enums
# ---------------------------------------------------------------------------

_TS_ENUM_RE = re.compile(
    r"(?:export\s+)?(?:const\s+)?enum\s+(\w+)\s*\{([^}]+)\}",
)

_TS_ENUM_VALUE_RE = re.compile(
    r"(\w+)\s*=\s*([\"']?[\w\-. ]+[\"']?)",
)

# Constant object pattern: export const STATUS = { ACTIVE: 1, ... } as const
_CONST_OBJ_RE = re.compile(
    r"(?:export\s+)?const\s+([A-Z_][A-Z0-9_]+)\s*(?::\s*\w+\s*)?=\s*\{([^}]+)\}\s*(?:as\s+const)?",
)

_CONST_OBJ_ENTRY_RE = re.compile(
    r"(\w+)\s*:\s*([\"']?[\w\-. ]+[\"']?)",
)

# ---------------------------------------------------------------------------
# Axios client → base URL mapping (from web2 architecture)
# ---------------------------------------------------------------------------

_CLIENT_BASE_MAP: dict[str, str] = {
    "orderServiceApiClient":        "/order/api/v1",
    "userServiceApiClient":         "/user/api/v1",
    "commonServiceApiClient":       "/common/api/v1",
    "notifyServiceApiClient":       "/notification/api/v1",
    "notificationServiceApiClient": "/notification/api/v1",
    "driverServiceApiClient":       "/driver/api/v1",
    "driverDAServiceApiClient":     "/da-api/guest/driver",
}

# API module → typical HTTP client mapping
_API_MODULE_MAP: dict[str, str] = {
    "OrderAPIs":        "/order/api/v1",
    "UserAPIs":         "/user/api/v1",
    "CommonAPIs":       "/common/api/v1",
    "NotifyAPIs":       "/notification/api/v1",
    "NotificationAPIs": "/notification/api/v1",
    "DriverAPIs":       "/user/api/v1",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_endpoint(base: str, path: str) -> str:
    """Combine base URL and path, normalize slashes."""
    path = path.strip()
    # Handle template literals: ${id} → :id
    path = re.sub(r"\$\{(\w+)\}", r":\1", path)
    if base and not path.startswith("/"):
        path = "/" + path
    full = (base.rstrip("/") + "/" + path.lstrip("/")) if base else path
    # Collapse double slashes
    full = re.sub(r"(?<!:)//+", "/", full)
    return full


def _next_pages_route(file_path: Path, pages_root: Path) -> str | None:
    """Derive a Next.js route from a file path under src/pages/.

    e.g. src/pages/orders/[id].tsx → /orders/:id
    """
    try:
        rel = file_path.relative_to(pages_root)
    except ValueError:
        return None

    parts = list(rel.parts)
    # Remove extension from last part
    if parts:
        stem = parts[-1].rsplit(".", 1)[0]
        parts[-1] = stem

    # Skip _app, _document, _error, api routes
    if parts and parts[-1].startswith("_"):
        return None
    if parts and parts[0] == "api":
        return None

    route_parts = []
    for part in parts:
        # [id] → :id, [...slug] → :slug*
        if part.startswith("[...") and part.endswith("]"):
            route_parts.append(":" + part[4:-1] + "*")
        elif part.startswith("[") and part.endswith("]"):
            route_parts.append(":" + part[1:-1])
        elif part == "index":
            continue  # index maps to parent path
        else:
            route_parts.append(part)

    return "/" + "/".join(route_parts) if route_parts else "/"


def _extract_block(content: str, start_pos: int) -> str:
    """Extract balanced-brace block starting from start_pos (first '{')."""
    open_idx = content.find("{", start_pos)
    if open_idx == -1:
        return ""

    depth = 0
    i = open_idx
    in_string: str | None = None

    while i < len(content):
        ch = content[i]

        if in_string:
            if ch == "\\" and i + 1 < len(content):
                i += 2
                continue
            if ch == in_string:
                in_string = None
        elif ch in ("'", '"', "`"):
            in_string = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return content[open_idx:i + 1]
        i += 1

    return ""


def _extract_api_calls_from_content(content: str, rel_path: str) -> list[ServiceCall]:
    """Extract all API call patterns from file content."""
    calls: list[ServiceCall] = []
    seen: set[str] = set()

    def _add(receiver: str, method: str) -> None:
        key = f"{receiver}.{method}"
        if key not in seen:
            seen.add(key)
            calls.append(ServiceCall(receiver=receiver, method=method, file=rel_path))

    # 1. Named axios client calls → resolve to full endpoint
    for m in _AXIOS_CLIENT_RE.finditer(content):
        client, http_method, path = m.groups()
        base = _CLIENT_BASE_MAP.get(client, "")
        endpoint = f"{http_method.upper()} {_normalize_endpoint(base, path)}"
        _add(client, endpoint)

    # 2. Direct axios calls
    for m in _DIRECT_AXIOS_RE.finditer(content):
        http_method, path = m.groups()
        endpoint = f"{http_method.upper()} {path}"
        _add("axios", endpoint)

    # 3. fetch() calls
    for m in _FETCH_RE.finditer(content):
        url = m.group(1)
        _add("fetch", f"GET {url}")

    # 4. API module method calls
    for m in _API_MODULE_CALL_RE.finditer(content):
        module, method = m.groups()
        _add(module, method)

    # 5. SWR → API module
    for m in _SWR_API_RE.finditer(content):
        module, method = m.groups()
        _add(f"SWR→{module}", method)

    # 6. Redux thunks → API module
    for m in _THUNK_API_RE.finditer(content):
        thunk_name, module, method = m.groups()
        _add(f"Thunk({thunk_name})→{module}", method)

    return calls


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class ReactParser(LanguageParser):
    """Parser for React/Next.js/TypeScript frontend repositories."""

    @property
    def language(self) -> str:
        return "react"

    @property
    def file_extensions(self) -> tuple[str, ...]:
        return (".ts", ".tsx", ".js", ".jsx")

    @property
    def ignore_dirs(self) -> frozenset[str]:
        return frozenset({
            ".git", "node_modules", "dist", "build", ".next",
            "__pycache__", "coverage", ".turbo", ".cache",
            "__tests__", "__mocks__", "__snapshots__",
            "public",  # static assets
        })

    @property
    def ignore_file_patterns(self) -> tuple[str, ...]:
        return (
            ".test.", ".spec.", ".stories.", ".story.",
            ".d.ts",   # declaration files
            "jest.",    # jest config
        )

    # ---- Extraction: Enums ----

    def extract_enums(self, repo_path: str, service: str) -> list[EnumGroup]:
        """Extract TypeScript enums and const-object enumerations."""
        groups: list[EnumGroup] = []
        root = Path(repo_path).resolve()

        for file_path in self.iter_source_files(repo_path):
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            rel_path = str(file_path.relative_to(root))

            # TS enums: enum Status { Active = 1, ... }
            for m in _TS_ENUM_RE.finditer(content):
                name = m.group(1)
                body = m.group(2)
                values = []
                for vm in _TS_ENUM_VALUE_RE.finditer(body):
                    values.append(EnumValue(
                        name=vm.group(1),
                        value=vm.group(2).strip("\"'"),
                    ))
                if values:
                    groups.append(EnumGroup(
                        name=name,
                        type_name="enum",
                        values=values,
                        file=rel_path,
                        service=service,
                    ))

            # Const object enums: const STATUS = { ACTIVE: 1, ... } as const
            for m in _CONST_OBJ_RE.finditer(content):
                name = m.group(1)
                body = m.group(2)
                values = []
                for vm in _CONST_OBJ_ENTRY_RE.finditer(body):
                    values.append(EnumValue(
                        name=vm.group(1),
                        value=vm.group(2).strip("\"'"),
                    ))
                if values:
                    groups.append(EnumGroup(
                        name=name,
                        type_name="const",
                        values=values,
                        file=rel_path,
                        service=service,
                    ))

        logger.info("Extracted %d enum/const groups from %s", len(groups), service)
        return groups

    # ---- Extraction: Types ----

    def extract_types(self, repo_path: str, service: str) -> list[StructDefinition]:
        """Extract TypeScript interfaces and type aliases."""
        types: list[StructDefinition] = []
        root = Path(repo_path).resolve()

        for file_path in self.iter_source_files(repo_path):
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            rel_path = str(file_path.relative_to(root))

            for pattern in (_INTERFACE_RE, _TYPE_ALIAS_RE):
                for m in pattern.finditer(content):
                    name = m.group(1)
                    block = _extract_block(content, m.start())
                    if not block:
                        continue

                    fields: list[StructField] = []
                    for fm in _TS_FIELD_RE.finditer(block):
                        field_name = fm.group(1)
                        optional = fm.group(2) == "?"
                        field_type = fm.group(3).strip().rstrip(";")
                        fields.append(StructField(
                            name=field_name,
                            type=field_type,
                            is_pointer=optional,
                        ))

                    if fields:
                        types.append(StructDefinition(
                            name=name,
                            fields=fields,
                            file=rel_path,
                            service=service,
                        ))

        logger.info("Extracted %d type definitions from %s", len(types), service)
        return types

    # ---- Extraction: Flows ----

    def extract_flows(self, repo_path: str, service: str) -> list[ServiceFlow]:
        """Extract component → API call flows.

        Also extracts:
        - Next.js page routes from file structure
        - API module definitions (method → endpoint)
        - Component → API mappings
        """
        root = Path(repo_path).resolve()
        pages_root = root / "src" / "pages"

        # Phase 1: Build API module method → endpoint map from src/lib/apis/*.ts
        api_method_map = self._build_api_method_map(root, service)

        # Phase 2: Extract flows from all source files
        flows: list[ServiceFlow] = []
        seen_routes: set[str] = set()

        for file_path in self.iter_source_files(repo_path):
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            rel_path = str(file_path.relative_to(root))

            # Extract component names from this file
            components = self._extract_components(content)

            # Extract API calls from this file
            api_calls = _extract_api_calls_from_content(content, rel_path)

            # Derive Next.js route if under src/pages/
            route = None
            if pages_root.exists():
                route = _next_pages_route(file_path, pages_root)
                if route and route in seen_routes:
                    route = None  # avoid duplicates
                if route:
                    seen_routes.add(route)

            # Extract explicit routes (React Router patterns)
            for rm in _ROUTE_JSX_RE.finditer(content):
                r = rm.group(1)
                if r not in seen_routes:
                    seen_routes.add(r)

            for rm in _ROUTE_OBJ_RE.finditer(content):
                r = rm.group(1)
                if r not in seen_routes:
                    seen_routes.add(r)

            # Build flows: each component with API calls becomes a flow
            if components and api_calls:
                for comp_name in components:
                    # Resolve API module calls to endpoints where possible
                    resolved_calls: list[ServiceCall] = []
                    for call in api_calls:
                        resolved = self._resolve_api_call(call, api_method_map)
                        resolved_calls.append(resolved)

                    endpoint = ""
                    if route:
                        endpoint = f"PAGE {route}"

                    flows.append(ServiceFlow(
                        handler_name=comp_name,
                        handler_file=rel_path,
                        endpoint=endpoint,
                        service_calls=resolved_calls,
                        service=service,
                        description=f"React component with {len(resolved_calls)} API call(s)",
                    ))
            elif components and route:
                # Page component without direct API calls (still useful for routing)
                for comp_name in components:
                    flows.append(ServiceFlow(
                        handler_name=comp_name,
                        handler_file=rel_path,
                        endpoint=f"PAGE {route}",
                        service=service,
                        description="Next.js page component",
                    ))

        # Phase 3: Also create flows for API module definitions themselves
        for (module, method), endpoint in api_method_map.items():
            flows.append(ServiceFlow(
                handler_name=f"{module}.{method}",
                handler_file=f"src/lib/apis/",
                endpoint=endpoint,
                service=service,
                description=f"API module method → {endpoint}",
            ))

        logger.info("Extracted %d flows from %s", len(flows), service)
        return flows

    # ---- Extraction: Edges ----

    def extract_edges(self, repo_path: str, service: str) -> list[Edge]:
        """Extract graph edges for React/Next.js repositories.

        Edge types produced:
          - defines:     file → component
          - routes_to:   react_route → component (Next.js page mapping)
          - calls_api:   component → api_endpoint (resolved HTTP endpoint)
          - dispatches:  component → redux_thunk
          - thunk_calls: redux_thunk → api_module.method
          - exposes_api: api_module.method → api_endpoint
        """
        root = Path(repo_path).resolve()
        pages_root = root / "src" / "pages"
        api_method_map = self._build_api_method_map(root, service)

        edges: list[Edge] = []
        seen: set[str] = set()

        def _add(e: Edge) -> None:
            key = f"{e.from_name}|{e.edge_type}|{e.to_name}"
            if key not in seen:
                seen.add(key)
                edges.append(e)

        # --- Pass A: API module method → endpoint (exposes_api) ---
        for (module, method), endpoint in api_method_map.items():
            _add(Edge(
                from_type="api_module", from_name=f"{module}.{method}",
                from_service=service, edge_type="exposes_api",
                to_type="api_endpoint", to_name=endpoint,
                to_service=service, file="src/lib/apis/",
            ))

        # --- Pass B: Walk all source files ---
        for file_path in self.iter_source_files(repo_path):
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            rel_path = str(file_path.relative_to(root))
            components = self._extract_components(content)
            api_calls = _extract_api_calls_from_content(content, rel_path)

            # Next.js page route
            route = None
            if pages_root.exists():
                route = _next_pages_route(file_path, pages_root)

            for comp_name in components:
                comp_qn = f"{service}.{comp_name}"

                # file → component (defines)
                _add(Edge(
                    from_type="file", from_name=rel_path,
                    from_service=service, edge_type="defines",
                    to_type="react_component", to_name=comp_qn,
                    to_service=service, file=rel_path,
                ))

                # route → component (routes_to)
                if route:
                    _add(Edge(
                        from_type="react_route", from_name=route,
                        from_service=service, edge_type="routes_to",
                        to_type="react_component", to_name=comp_qn,
                        to_service=service, file=rel_path,
                    ))

                # component → API calls
                for call in api_calls:
                    resolved = self._resolve_api_call(call, api_method_map)

                    if resolved.method.startswith(("GET ", "POST ", "PUT ", "PATCH ", "DELETE ")):
                        # Resolved to endpoint → calls_api edge
                        _add(Edge(
                            from_type="react_component", from_name=comp_qn,
                            from_service=service, edge_type="calls_api",
                            to_type="api_endpoint", to_name=resolved.method,
                            to_service=service, file=rel_path,
                        ))
                    elif "→" not in call.receiver:
                        # Unresolved API module call
                        _add(Edge(
                            from_type="react_component", from_name=comp_qn,
                            from_service=service, edge_type="calls_api",
                            to_type="api_module", to_name=f"{call.receiver}.{call.method}",
                            to_service=service, file=rel_path,
                        ))

            # --- Redux thunks (dispatches + thunk_calls) ---
            for m in _THUNK_API_RE.finditer(content):
                thunk_name, module, method = m.groups()
                thunk_qn = f"{service}.thunk:{thunk_name}"

                # component → thunk (dispatches)
                for comp_name in components:
                    _add(Edge(
                        from_type="react_component", from_name=f"{service}.{comp_name}",
                        from_service=service, edge_type="dispatches",
                        to_type="redux_thunk", to_name=thunk_qn,
                        to_service=service, file=rel_path,
                    ))

                # thunk → API module method (thunk_calls)
                resolved_endpoint = api_method_map.get((module, method))
                if resolved_endpoint:
                    _add(Edge(
                        from_type="redux_thunk", from_name=thunk_qn,
                        from_service=service, edge_type="thunk_calls",
                        to_type="api_endpoint", to_name=resolved_endpoint,
                        to_service=service, file=rel_path,
                    ))
                else:
                    _add(Edge(
                        from_type="redux_thunk", from_name=thunk_qn,
                        from_service=service, edge_type="thunk_calls",
                        to_type="api_module", to_name=f"{module}.{method}",
                        to_service=service, file=rel_path,
                    ))

            # --- SWR hooks (calls_api via SWR) ---
            for m in _SWR_API_RE.finditer(content):
                module, method = m.groups()
                resolved_endpoint = api_method_map.get((module, method))
                for comp_name in components:
                    comp_qn = f"{service}.{comp_name}"
                    if resolved_endpoint:
                        _add(Edge(
                            from_type="react_component", from_name=comp_qn,
                            from_service=service, edge_type="calls_api",
                            to_type="api_endpoint", to_name=resolved_endpoint,
                            to_service=service, file=rel_path,
                        ))
                    else:
                        _add(Edge(
                            from_type="react_component", from_name=comp_qn,
                            from_service=service, edge_type="calls_api",
                            to_type="api_module", to_name=f"{module}.{method}",
                            to_service=service, file=rel_path,
                        ))

        logger.info("Extracted %d edges from %s", len(edges), service)
        return edges

    # ---- Internal helpers ----

    def _extract_components(self, content: str) -> list[str]:
        """Extract React component names from file content."""
        components: list[str] = []
        seen: set[str] = set()

        for pattern in (_FUNC_COMPONENT_RE, _CONST_COMPONENT_RE, _DEFAULT_EXPORT_RE):
            for m in pattern.finditer(content):
                name = m.group(1)
                if name not in seen and not self._is_utility_name(name):
                    seen.add(name)
                    components.append(name)

        return components

    @staticmethod
    def _is_utility_name(name: str) -> bool:
        """Filter out names that are likely utilities, not components."""
        _SKIP = {
            "React", "Component", "Fragment", "Suspense", "Provider",
            "Error", "String", "Number", "Boolean", "Array", "Object",
            "Map", "Set", "Promise", "Date", "JSON",
        }
        return name in _SKIP

    def _build_api_method_map(self, root: Path, service: str) -> dict[tuple[str, str], str]:
        """Parse src/lib/apis/*.ts to build (Module, method) → endpoint map.

        Reads the API module files and extracts which HTTP method+path each
        API function maps to.
        """
        api_dir = root / "src" / "lib" / "apis"
        method_map: dict[tuple[str, str], str] = {}

        if not api_dir.is_dir():
            return method_map

        for api_file in api_dir.iterdir():
            if not api_file.suffix in (".ts", ".tsx", ".js"):
                continue

            try:
                content = api_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            # Find the API module name: const OrderAPIs = { ... }
            module_match = re.search(
                r"(?:export\s+)?const\s+(\w+APIs?)\s*=\s*\{",
                content,
            )
            if not module_match:
                continue

            module_name = module_match.group(1)
            base = _API_MODULE_MAP.get(module_name, "")

            # Find method definitions with their axios calls
            # Pattern: methodName(params) { return client.get("/path") }
            # or: methodName: (params) => client.get("/path")
            method_defs = re.finditer(
                r"(\w+)\s*(?:\([^)]*\)|\s*:\s*\([^)]*\))\s*(?:=>|\{)"
                r"[^}]*?"
                r"(?:return\s+)?\w+\.\s*(get|post|put|patch|delete)\s*"
                r"[<(]\s*[^)]*?[`\"']([^`\"']+)[`\"']",
                content,
                re.DOTALL,
            )

            for mm in method_defs:
                method_name = mm.group(1)
                http_method = mm.group(2).upper()
                path = mm.group(3)
                path = re.sub(r"\$\{(\w+)\}", r":\1", path)
                full_path = _normalize_endpoint(base, path)
                endpoint = f"{http_method} {full_path}"
                method_map[(module_name, method_name)] = endpoint

        logger.info("Built API method map: %d entries", len(method_map))
        return method_map

    @staticmethod
    def _resolve_api_call(call: ServiceCall, api_method_map: dict[tuple[str, str], str]) -> ServiceCall:
        """Resolve an API module call to its actual endpoint if known."""
        # If call.method already contains an HTTP method (resolved endpoint), keep it
        if call.method.startswith(("GET ", "POST ", "PUT ", "PATCH ", "DELETE ")):
            return call

        # Try to resolve from API method map
        # call.receiver might be "OrderAPIs" or "SWR→OrderAPIs" or "Thunk(...)→UserAPIs"
        module = call.receiver
        # Strip SWR→ or Thunk(...)→ prefix
        if "→" in module:
            module = module.split("→", 1)[1]

        endpoint = api_method_map.get((module, call.method))
        if endpoint:
            return ServiceCall(
                receiver=call.receiver,
                method=endpoint,
                file=call.file,
                line=call.line,
            )

        return call
