"""Global output limits for list/search payloads sent to the LLM layer."""

from __future__ import annotations

MAX_LIST_RESULTS = 5


def clamp_list_limit(value: object, default: int = MAX_LIST_RESULTS) -> int:
    """Clamp requested list size to a safe range [1, MAX_LIST_RESULTS]."""
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(MAX_LIST_RESULTS, parsed))


def truncate_list(items: object, limit: int = MAX_LIST_RESULTS) -> list:
    """Return at most ``limit`` items from list-like payloads."""
    if not isinstance(items, list):
        return []
    return items[: clamp_list_limit(limit)]
