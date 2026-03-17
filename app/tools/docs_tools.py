"""Tools for reading logistics system documentation.

Two-tier knowledge structure — always use the lightest tier that answers the question:

  Tier 1  search_endpoints(keyword)
          Searches the endpoint index (handles edges + service flows).
          Use for "what API/path does X use?", method/route lookups.

  Tier 2  get_handler_context(handler_name)
          Reads the handler source code from indexed code chunks.
          Use for "how does handler Y work?", service call chains.

All data is served from the indexer's SQLite knowledge store.
All paths are validated to prevent traversal attacks.
"""

from indexer.store import get_knowledge_store


# ---------------------------------------------------------------------------
# Tier 0: lightweight index / discovery
# ---------------------------------------------------------------------------

def list_available_docs() -> dict:
    """List all available documentation assets without loading their content.
    Returns feature requirement docs, handler names, and indexed service stats.
    Call this first to discover what is available before loading heavy content.
    """
    store = get_knowledge_store()
    stats = store.get_stats()
    handlers = store.list_handlers()

    return {
        "handler_contexts": handlers,
        "indexed_services": stats.get("services", []),
        "stats": {
            "endpoints": stats.get("edge_types", {}).get("handles", 0),
            "handlers": len(handlers),
            "flows": stats.get("flows", 0),
            "enums": stats.get("enums", 0),
            "structs": stats.get("structs", 0),
        },
        "tip": "Use search_endpoints(keyword) to query endpoints, "
               "get_handler_context(name) for handler source code.",
    }


# ---------------------------------------------------------------------------
# Tier 1: endpoint search
# ---------------------------------------------------------------------------

def search_endpoints(keyword: str) -> dict:
    """Search the backend endpoint index for routes matching a keyword.
    Searches across HTTP method, path, handler name, and service name.
    Use when the user asks which API path or handler is responsible for an action.
    Returns matching endpoint entries (method, path, handler, service, service_calls).
    """
    if not keyword or not keyword.strip():
        return {"error": "MISSING_KEYWORD", "message": "Provide a non-empty search keyword."}

    store = get_knowledge_store()
    results = store.search_endpoints(keyword)

    if not results:
        return {
            "keyword": keyword,
            "total_matches": 0,
            "results": [],
            "message": "No endpoints matched. Try a different keyword.",
        }

    return {
        "keyword": keyword,
        "total_matches": len(results),
        "results": results,
    }


# ---------------------------------------------------------------------------
# Tier 2: handler context
# ---------------------------------------------------------------------------

def get_handler_context(handler_name: str) -> dict:
    """Read the handler source code for a specific backend handler function.
    Contains: endpoint path, handler Go code, detected service calls.
    Use for technical questions about how a specific handler or endpoint works.
    Call list_available_docs() first to see valid handler names.
    handler_name examples: EstimateGuest, GetOrderDetail, CancelOrderB2C
    """
    safe = handler_name.strip() if handler_name else ""
    if not safe or "/" in safe or "\\" in safe or ".." in safe:
        store = get_knowledge_store()
        return {
            "error": "INVALID_HANDLER_NAME",
            "message": "Handler name must be a plain name (no slashes or '..').",
            "available_handlers": store.list_handlers(),
        }

    store = get_knowledge_store()
    result = store.get_handler_context(safe)

    if not result:
        return {
            "error": "HANDLER_NOT_FOUND",
            "message": f"No handler found for '{safe}'.",
            "available_handlers": store.list_handlers(),
        }

    return result



