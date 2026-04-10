"""Knowledge tools — expose indexed codebase knowledge to the AI chatbot.

These tools are registered alongside the existing order_tools and docs_tools.
They give Gemini access to:
  - Enum/status code lookups (what does statusCd=3 mean?)
  - Full-text + semantic code search
  - Graph traversal across indexed services

All reads go through the KnowledgeStore (SQLite knowledge.db — read-only, baked into image).
"""

import logging

from app.limits import MAX_LIST_RESULTS, truncate_list
from indexer.store import get_knowledge_store

logger = logging.getLogger(__name__)


def lookup_enum(enum_name: str) -> dict:
    """Look up an internal enum or constant group by name.
    Returns all matching enum definitions with their values and descriptions.
    Use when the user asks about status codes, type codes, payment codes,
    or any named constant group in the backend.
    Examples: lookup_enum("OrderStatus"), lookup_enum("PayCd"), lookup_enum("VehicleType")
    """
    if not enum_name or not enum_name.strip():
        return {"error": "MISSING_NAME", "message": "Provide an enum name to look up."}
    try:
        store = get_knowledge_store()
        result = store.lookup_enum(enum_name.strip())
        if result.get("matches", 0) == 0:
            result["message"] = (
                f"No enum found matching '{enum_name}'. "
                "Try a shorter keyword or call get_knowledge_stats() to verify what is indexed."
            )
        return result
    except Exception as e:
        logger.exception("[knowledge_tools] lookup_enum failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": str(e)}


def explain_status(code: str) -> dict:
    """Explain what a specific numeric status code means across all backend enums.
    Use when the user asks "what does status 3 mean?" or "what is statusCd=7?".
    Searches all indexed enum groups for the given value.
    If the result contains persona_ambiguous=true, the same code means different things
    for different perspectives (customer/driver/admin). Ask the user to clarify before answering.
    Examples: explain_status("1"), explain_status("7"), explain_status("3")
    """
    if not code or not str(code).strip():
        return {"error": "MISSING_CODE", "message": "Provide a status code value."}
    try:
        store = get_knowledge_store()
        result = store.explain_status_code(str(code).strip())
        if result.get("matches", 0) == 0:
            result["message"] = (
                f"No enum values found for code '{code}'. "
                "Try lookup_enum() with a related name, or get_knowledge_stats() to verify indexing."
            )
        return result
    except Exception as e:
        logger.exception("[knowledge_tools] explain_status failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": str(e)}


def search_codebase(keyword: str) -> dict:
    """Search the indexed codebase using keywords.
    Searches across functions, enums, structs, and service flows using full-text search (FTS5).
    Use for broad questions like "how is pricing calculated?" or "where is order validation?".
    """
    if not keyword or not keyword.strip():
        return {"error": "MISSING_QUERY", "message": "Provide a search keyword."}

    query = keyword.strip()
    try:
        store = get_knowledge_store()
        payload = store.search_code(query, limit=MAX_LIST_RESULTS)
        if isinstance(payload, dict) and isinstance(payload.get("results"), list):
            payload["results"] = truncate_list(payload.get("results"))
            payload["matches"] = len(payload["results"])
        return payload
    except Exception as e:
        logger.exception("[knowledge_tools] search_codebase failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": str(e)}


_KNOWN_EDGE_TYPES: frozenset[str] = frozenset({
    "calls", "delegates_to", "handles", "defines", "calls_api",
    "x_calls", "routes_to", "dispatches", "thunk_calls", "exposes_api",
})


def traverse_graph(name: str, edge_types: str = "", direction: str = "outgoing", max_depth: int = 3) -> dict:
    """Traverse the codebase graph from a starting node, following typed edges.
    Returns the connected subgraph (edges and nodes) reachable from the start.
    Use for tracing call chains, finding dependencies, or understanding code structure.
    Args:
        name: Name of the starting node (partial match). E.g. "GetOrderDetail", "OrderAPIs".
        edge_types: Comma-separated edge types to follow. Available types:
            calls, delegates_to, handles, defines, calls_api, x_calls,
            routes_to, dispatches, thunk_calls, exposes_api.
            Leave empty to follow all edge types.
        direction: "outgoing" (default), "incoming", or "both".
        max_depth: Maximum hops to traverse (1-5). Default 3.
    Examples:
        traverse_graph("GetOrderDetail", "calls,delegates_to")
        traverse_graph("OrderAPIs.getOrder", "exposes_api", direction="outgoing")
        traverse_graph("orderService.GetOrder", direction="incoming")
    """
    if not name or not name.strip():
        return {"error": "MISSING_NAME", "message": "Provide a node name to start traversal."}
    try:
        store = get_knowledge_store()
        type_list = [t.strip() for t in edge_types.split(",") if t.strip()] or None
        if type_list:
            unknown = [t for t in type_list if t not in _KNOWN_EDGE_TYPES]
            if unknown:
                return {
                    "error": "UNKNOWN_EDGE_TYPES",
                    "message": (
                        f"Unrecognized edge type(s): {unknown}. "
                        f"Valid types: {sorted(_KNOWN_EDGE_TYPES)}"
                    ),
                }
        depth = max(1, min(5, max_depth))
        if direction not in ("outgoing", "incoming", "both"):
            direction = "outgoing"
        return store.traverse(name.strip(), edge_types=type_list, direction=direction, max_depth=depth)
    except Exception as e:
        logger.exception("[knowledge_tools] traverse_graph failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": str(e)}


def find_api_consumers(endpoint: str) -> dict:
    """Find all frontend components and pages that call a specific backend API endpoint.
    Use when the user asks "which page calls this API?" or "who consumes this endpoint?".
    The endpoint can be a partial match, e.g. "/orders/:orderId" or "GET /api/v1/orders".
    Returns React components, their routes, and the edge chain connecting them.
    Note: searches only 'calls_api' edges. Components using indirect patterns
    (x_calls, thunk_calls) may not appear here — use traverse_graph for broader coverage.
    Examples: find_api_consumers("/orders/:orderId"), find_api_consumers("GetOrderDetail")
    """
    if not endpoint or not endpoint.strip():
        return {"error": "MISSING_ENDPOINT", "message": "Provide an API endpoint or handler name."}
    try:
        store = get_knowledge_store()
        result = store.find_edges(endpoint.strip(), edge_type="calls_api", direction="incoming")
        if result.get("matches", 0) == 0:
            result["message"] = (
                f"No frontend consumers found for '{endpoint}'. "
                "Try traverse_graph() with broader edge types, or search_endpoints() "
                "to confirm the endpoint path."
            )
        return result
    except Exception as e:
        logger.exception("[knowledge_tools] find_api_consumers failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": str(e)}


def get_knowledge_stats() -> dict:
    """Show summary statistics of the indexed codebase knowledge.
    Returns counts of enums, structs, service flows, code chunks, edges, and edge types.
    Call this to check what knowledge is available before using other knowledge tools.
    """
    try:
        store = get_knowledge_store()
        return store.get_stats()
    except Exception as e:
        logger.exception("[knowledge_tools] get_knowledge_stats failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": str(e)}
