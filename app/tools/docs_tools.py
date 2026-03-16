"""Tools for reading logistics system documentation.

Three-tier knowledge structure — always use the lightest tier that answers the question:

  Tier 1  search_endpoints(keyword)
          Searches the endpoint index (BE endpoints).
          Use for "what API/path does X use?", method/route lookups.

  Tier 2  get_handler_context(handler_name)
          Reads the raw handler snippet for one Go handler function.
          Use for "how does handler Y work?", service call chains.

  Tier 3  get_feature_requirement(feature_name)
          Reads the synthesized business requirement doc for a feature.
          Use for business rules, use-case flows, validation constraints.

Multi-service layout (future-proof):
  docs/features/<service>/<feature>/requirement.md   <- namespaced by service
  docs/features/<feature>/requirement.md             <- legacy flat (backward compat)

All paths are validated to prevent traversal attacks.
"""

import json
import pathlib

_DOCS_ROOT = pathlib.Path(__file__).parents[2] / "docs"
_FEATURES_ROOT = _DOCS_ROOT / "features"
_DISCOVERY_ROOT = _DOCS_ROOT / "discovery"
_ORDER_SERVICE_DIR = _DISCOVERY_ROOT / "order-services"
_WEB2_DIR = _DISCOVERY_ROOT / "web2"
_LEGACY_CONTEXT_DIR = _DISCOVERY_ROOT / "code_context"
_LEGACY_ENDPOINTS_FILE = _DISCOVERY_ROOT / "be_endpoints.json"
_FLOW_MAPPINGS_FILE = _DISCOVERY_ROOT / "flow_mappings.json"

# Directories not representing backend services
_NON_SERVICE_DIRS = frozenset({"web2"})


def _discover_service_dirs() -> list[pathlib.Path]:
    """Find all service discovery directories (each has be_endpoints.json or code_context/)."""
    if not _DISCOVERY_ROOT.is_dir():
        return []
    dirs = []
    for p in sorted(_DISCOVERY_ROOT.iterdir()):
        if not p.is_dir() or p.name in _NON_SERVICE_DIRS or p.name.startswith("."):
            continue
        if (p / "be_endpoints.json").exists() or (p / "code_context").is_dir():
            dirs.append(p)
    return dirs


def _all_context_dirs() -> list[pathlib.Path]:
    """Return all code_context directories across services."""
    dirs = []
    for svc_dir in _discover_service_dirs():
        ctx = svc_dir / "code_context"
        if ctx.is_dir():
            dirs.append(ctx)
    # Legacy fallback
    if not dirs and _LEGACY_CONTEXT_DIR.is_dir():
        dirs.append(_LEGACY_CONTEXT_DIR)
    return dirs


def _all_endpoint_files() -> list[pathlib.Path]:
    """Return all be_endpoints.json files across services."""
    files = []
    for svc_dir in _discover_service_dirs():
        ep = svc_dir / "be_endpoints.json"
        if ep.exists():
            files.append(ep)
    # Legacy fallback
    if not files and _LEGACY_ENDPOINTS_FILE.exists():
        files.append(_LEGACY_ENDPOINTS_FILE)
    return files


def _context_dir() -> pathlib.Path:
    """Primary context dir (backward compat — returns first available)."""
    preferred = _ORDER_SERVICE_DIR / "code_context"
    return preferred if preferred.is_dir() else _LEGACY_CONTEXT_DIR


def _endpoints_file() -> pathlib.Path:
    """Primary endpoints file (backward compat)."""
    preferred = _ORDER_SERVICE_DIR / "be_endpoints.json"
    return preferred if preferred.exists() else _LEGACY_ENDPOINTS_FILE


def _fe_active_apis() -> set[str]:
    """Return the set of normalized 'METHOD /path' strings called by the FE."""
    if not _FLOW_MAPPINGS_FILE.exists():
        return set()
    try:
        flows: list[dict] = json.loads(_FLOW_MAPPINGS_FILE.read_text(encoding="utf-8"))
        # api field is like "POST /guest/estimate" (no /api/v1 prefix)
        return {f["api"].split("?")[0].strip() for f in flows if "api" in f}
    except (OSError, json.JSONDecodeError):
        return set()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_safe_segment(name: str) -> bool:
    """True when name is a plain directory/file segment with no traversal chars."""
    return bool(name) and "/" not in name and "\\" not in name and ".." not in name


def _safe_resolve(path: pathlib.Path, base: pathlib.Path) -> pathlib.Path | None:
    """Return resolved path only if it stays inside base; else None."""
    try:
        resolved = path.resolve()
        if str(resolved).startswith(str(base.resolve())):
            return resolved
    except Exception:
        pass
    return None


def _list_features() -> list[str]:
    """Return all feature names that have a requirement.md (flat + service-namespaced)."""
    if not _FEATURES_ROOT.is_dir():
        return []
    results: list[str] = []
    for p in sorted(_FEATURES_ROOT.iterdir()):
        if not p.is_dir() or p.name == "__pycache__":
            continue
        if (p / "requirement.md").exists():
            results.append(p.name)
        else:
            # service-namespaced: docs/features/<service>/<feature>/requirement.md
            for sub in sorted(p.iterdir()):
                if sub.is_dir() and (sub / "requirement.md").exists():
                    results.append(f"{p.name}/{sub.name}")
    return results


def _list_handler_names() -> list[str]:
    names: set[str] = set()
    for ctx_dir in _all_context_dirs():
        for p in ctx_dir.glob("*.context.md"):
            names.add(p.stem.replace(".context", ""))
    return sorted(names)


# ---------------------------------------------------------------------------
# Tier 0: lightweight index / discovery
# ---------------------------------------------------------------------------

def list_available_docs() -> dict:
    """List all available documentation assets without loading their content.
    Returns feature requirement docs, handler context files, and endpoint count.
    Call this first to discover what is available before loading heavy content.
    """
    service_dirs = _discover_service_dirs()
    services_info = {}
    for svc_dir in service_dirs:
        svc_name = svc_dir.name
        ep_file = svc_dir / "be_endpoints.json"
        ctx_dir = svc_dir / "code_context"
        services_info[svc_name] = {
            "endpoints_available": ep_file.exists(),
            "handler_contexts_available": ctx_dir.is_dir(),
            "handler_count": len(list(ctx_dir.glob("*.context.md"))) if ctx_dir.is_dir() else 0,
        }

    return {
        "feature_requirements": _list_features(),
        "handler_contexts": _list_handler_names(),
        "services": services_info,
        "endpoints_index": {
            "tip": "Use search_endpoints(keyword) to query across all services.",
        },
        "sources": {
            "backend_services": [d.name for d in service_dirs],
            "frontend_app": "web2",
        },
    }


# ---------------------------------------------------------------------------
# Tier 1: endpoint search
# ---------------------------------------------------------------------------

def search_endpoints(keyword: str) -> dict:
    """Search the backend endpoint index for routes matching a keyword.
    Searches across HTTP method, path, controller name, and function name.
    Aggregates results from all indexed services.
    Use when the user asks which API path or handler is responsible for an action.
    Returns matching endpoint entries (method, path, controller, function, service_calls).
    """
    if not keyword or not keyword.strip():
        return {"error": "MISSING_KEYWORD", "message": "Provide a non-empty search keyword."}

    ep_files = _all_endpoint_files()
    if not ep_files:
        return {"error": "INDEX_NOT_FOUND", "message": "Endpoint index not built yet. Run discovery first."}

    term = keyword.strip().lower()
    fe_apis = _fe_active_apis()
    all_matches: list[dict] = []
    sources: list[str] = []

    for ep_file in ep_files:
        try:
            endpoints: list[dict] = json.loads(ep_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        source = ep_file.parent.name
        sources.append(source)

        matches = [
            ep for ep in endpoints
            if term in ep.get("path", "").lower()
            or term in ep.get("method", "").lower()
            or term in ep.get("controller", "").lower()
            or term in ep.get("controller_method", ep.get("function", "")).lower()
        ]

        for ep in matches:
            path_short = ep.get("path", "").replace("/api/v1", "", 1)
            key = f"{ep.get('method', '')} {path_short}"
            all_matches.append({**ep, "service": source, "fe_active": key in fe_apis})

    return {
        "keyword": keyword,
        "sources": sources,
        "total_matches": len(all_matches),
        "results": all_matches,
    }


# ---------------------------------------------------------------------------
# Tier 2: handler context
# ---------------------------------------------------------------------------

def get_handler_context(handler_name: str) -> dict:
    """Read the raw handler context doc for a specific backend handler function.
    Contains: endpoint path, handler code snippet, detected service calls.
    Searches across all indexed services.
    Use for technical questions about how a specific handler or endpoint works.
    Call list_available_docs() first to see valid handler names.
    handler_name examples: EstimateGuest, GetOrderDetail, CancelOrderB2C
    """
    safe = handler_name.strip() if handler_name else ""
    if not _is_safe_segment(safe):
        return {
            "error": "INVALID_HANDLER_NAME",
            "message": "Handler name must be a plain name (no slashes or '..').",
            "available_handlers": _list_handler_names(),
        }

    # Search all context directories for this handler
    for ctx_dir in _all_context_dirs():
        doc_path = ctx_dir / f"{safe}.context.md"
        if _safe_resolve(doc_path, ctx_dir) is None:
            continue
        if doc_path.exists():
            try:
                content = doc_path.read_text(encoding="utf-8")
            except OSError as exc:
                return {"error": "READ_ERROR", "message": str(exc)}
            return {
                "handler": safe,
                "source": ctx_dir.parent.name,
                "context_file": str(doc_path.relative_to(_DOCS_ROOT)).replace("\\", "/"),
                "content": content,
            }

    return {
        "error": "HANDLER_NOT_FOUND",
        "message": f"No context doc found for handler '{safe}'.",
        "available_handlers": _list_handler_names(),
    }


# ---------------------------------------------------------------------------
# Tier 3: synthesized feature requirements
# ---------------------------------------------------------------------------

def get_feature_requirement(feature_name: str) -> dict:
    """Read the synthesized business requirement document for a feature.
    Use when the user asks about feature business rules, use cases, validation constraints,
    or end-to-end API behaviour.

    feature_name formats:
      "check_price"          - flat feature (docs/features/check_price/requirement.md)
      "order/check_price"    - service-namespaced (docs/features/order/check_price/requirement.md)

    Call list_available_docs() or pass feature_name='' to discover available features.
    """
    raw = (feature_name or "").strip()

    if not raw:
        return {
            "error": "MISSING_FEATURE_NAME",
            "available_features": _list_features(),
        }

    # Support "service/feature" namespaced format for multi-service
    parts = raw.split("/", 1)
    if len(parts) == 2:
        service_seg, feature_seg = parts
        if not _is_safe_segment(service_seg) or not _is_safe_segment(feature_seg):
            return {"error": "INVALID_FEATURE_NAME", "message": "Path segments must not contain '..' or extra slashes."}
        doc_path = _FEATURES_ROOT / service_seg / feature_seg / "requirement.md"
    else:
        if not _is_safe_segment(raw):
            return {"error": "INVALID_FEATURE_NAME", "message": "Feature name must not contain '..' or slashes (use 'service/feature' for namespaced paths)."}
        doc_path = _FEATURES_ROOT / raw / "requirement.md"

    if _safe_resolve(doc_path, _FEATURES_ROOT) is None:
        return {
            "error": "INVALID_FEATURE_NAME",
            "message": "Feature path is out of bounds.",
            "available_features": _list_features(),
        }

    if not doc_path.exists():
        return {
            "error": "FEATURE_NOT_FOUND",
            "message": f"No requirement doc found for '{raw}'.",
            "available_features": _list_features(),
        }

    try:
        content = doc_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"error": "READ_ERROR", "message": str(exc)}

    return {"feature": raw, "content": content}
