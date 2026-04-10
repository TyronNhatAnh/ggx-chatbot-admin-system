"""Tools for reading logistics system documentation.

Two-tier knowledge structure — always use the lightest tier that answers the question:

  Tier 1  search_endpoints(keyword)
          Searches the endpoint index (handles edges + service flows).
          Use for "what API/path does X use?", method/route lookups.

  Tier 2  get_handler_context(handler_name)
          Reads the handler source code from indexed code chunks.
          Use for "how does handler Y work?", service call chains.

All data is served from the indexer's knowledge store (data/knowledge/knowledge.db — baked into image).
All paths are validated to prevent traversal attacks.
"""

import logging

from app.limits import truncate_list
from indexer.store import get_knowledge_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier 0: lightweight index / discovery
# ---------------------------------------------------------------------------

def list_available_docs() -> dict:
    """List all available documentation assets without loading their content.
    Returns feature requirement docs, handler names, and indexed service stats.
    Call this first to discover what is available before loading heavy content.
    """
    try:
        store = get_knowledge_store()
        stats = store.get_stats()
        all_handlers = store.list_handlers()
        handlers = truncate_list(all_handlers)
        return {
            "handler_contexts": handlers,
            "indexed_services": truncate_list(stats.get("services", [])),
            "stats": {
                "endpoints": stats.get("edge_types", {}).get("handles", 0),
                "handlers": len(all_handlers),
                "flows": stats.get("flows", 0),
                "enums": stats.get("enums", 0),
                "structs": stats.get("structs", 0),
            },
            "tip": "Use search_endpoints(keyword) to query endpoints, "
                   "get_handler_context(name) for handler source code.",
        }
    except Exception as e:
        logger.exception("[docs_tools] list_available_docs failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": "Failed to load documentation index."}


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

    try:
        store = get_knowledge_store()
        raw_results = store.search_endpoints(keyword)
        results = truncate_list(raw_results)
    except Exception as e:
        logger.exception("[docs_tools] search_endpoints failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": "Failed to search endpoints."}

    if not results:
        return {
            "keyword": keyword,
            "total_matches": 0,
            "results": [],
            "message": "No endpoints matched. Try a different keyword.",
        }

    return {
        "keyword": keyword,
        "total_matches": len(raw_results),
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
    handler_name examples: EstimateGuest, GetOrderDetail
    """
    safe = handler_name.strip().replace("\x00", "") if handler_name else ""
    if not safe or "/" in safe or "\\" in safe or ".." in safe:
        try:
            available = truncate_list(get_knowledge_store().list_handlers())
        except Exception:
            available = []
        return {
            "error": "INVALID_HANDLER_NAME",
            "message": "Handler name must be a plain name (no slashes or '..').",
            "available_handlers": available,
        }

    try:
        store = get_knowledge_store()
        result = store.get_handler_context(safe)
        if not result:
            return {
                "error": "HANDLER_NOT_FOUND",
                "message": f"No handler found for '{safe}'. Try list_available_docs() to see valid handler names.",
                "available_handlers": truncate_list(store.list_handlers()),
            }
        return result
    except Exception as e:
        logger.exception("[docs_tools] get_handler_context failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": "Failed to load handler context."}



