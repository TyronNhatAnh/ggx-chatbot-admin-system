"""Knowledge tools — expose indexed codebase knowledge to the AI chatbot.

These tools are registered alongside the existing order_tools and docs_tools.
They give Gemini access to:
  - Enum/status code lookups (what does statusCd=3 mean?)
  - Service flow tracing (what happens when GetOrderDetail is called?)
  - Struct definitions (what fields does B2COrder have?)
  - Full-text + semantic code search

All reads go through the KnowledgeStore (SQLite) and optionally the VectorStore.
"""

import logging

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
        return store.lookup_enum(enum_name.strip())
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
        return store.explain_status_code(str(code).strip())
    except Exception as e:
        logger.exception("[knowledge_tools] explain_status failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": str(e)}


def trace_service_flow(handler_name: str) -> dict:
    """Trace the execution flow for a backend handler function.
    Shows the full chain: handler → service layer → repository layer.
    Use when the user asks "what happens when X is called?" or "how does Y endpoint work?".
    handler_name is the Go function name, e.g. GetOrderDetail, EstimateGuest, CancelOrderB2C.
    """
    if not handler_name or not handler_name.strip():
        return {"error": "MISSING_HANDLER", "message": "Provide a handler function name."}
    try:
        store = get_knowledge_store()
        return store.get_flow(handler_name.strip())
    except Exception as e:
        logger.exception("[knowledge_tools] trace_service_flow failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": str(e)}


def get_struct_definition(struct_name: str) -> dict:
    """Look up a Go struct definition including all fields, types, and JSON tags.
    Use when the user asks about request/response shapes, data models, or field names.
    The JSON tags show how Go fields map to API JSON field names.
    Examples: get_struct_definition("Order"), get_struct_definition("B2COrderDetail")
    """
    if not struct_name or not struct_name.strip():
        return {"error": "MISSING_NAME", "message": "Provide a struct name."}
    try:
        store = get_knowledge_store()
        return store.get_struct(struct_name.strip())
    except Exception as e:
        logger.exception("[knowledge_tools] get_struct_definition failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": str(e)}


def search_codebase(query: str) -> dict:
    """Search the indexed codebase using natural language or keywords.
    Searches across functions, enums, structs, and service flows.
    Use for broad questions like "how is pricing calculated?" or "where is order validation?".
    Falls back to full-text search if vector search is not available.
    """
    if not query or not query.strip():
        return {"error": "MISSING_QUERY", "message": "Provide a search query."}

    query = query.strip()

    # Try vector search first (semantic)
    try:
        from indexer.vector_store import get_vector_store
        vs = get_vector_store()
        if vs and vs.count() > 0:
            results = vs.search(query, top_k=5)
            if results:
                return {
                    "search_type": "semantic",
                    "query": query,
                    "results": results,
                }
    except Exception as e:
        logger.debug("[knowledge_tools] Vector search unavailable: %s", e)

    # Fallback to full-text search
    try:
        store = get_knowledge_store()
        return store.search_code(query)
    except Exception as e:
        logger.exception("[knowledge_tools] search_codebase failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": str(e)}


def get_knowledge_stats() -> dict:
    """Show summary statistics of the indexed codebase knowledge.
    Returns counts of enums, structs, service flows, and code chunks.
    Call this to check what knowledge is available before using other knowledge tools.
    """
    try:
        store = get_knowledge_store()
        return store.get_stats()
    except Exception as e:
        logger.exception("[knowledge_tools] get_knowledge_stats failed: %s", e)
        return {"error": "KNOWLEDGE_ERROR", "message": str(e)}
