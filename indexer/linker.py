"""Cross-service endpoint linker — Phase 3 of the graph evolution.

After all services are indexed, this module matches React API endpoints to
Go handler endpoints and creates cross-service edges that enable full-stack
graph traversal:

    React component ──calls_api──▶ API endpoint
                                        │
                                   (linker matches)
                                        │
    React component ──x_calls──▶ Go handler ──calls──▶ service ──delegates_to──▶ repo

The Go parser now generates ``handles`` edges directly from Gin route
definitions, so the linker no longer needs ``be_endpoints.json``.

Usage:
    # After indexing all services:
    from indexer.linker import link_services
    link_services()

    # Or standalone:
    python -m indexer.linker
"""

import logging
import re

from indexer.models import Edge
from indexer.store import KnowledgeStore, get_knowledge_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_DISCOVERY_DIR = None  # No longer read discovery files

# Service route prefix in React → backend service name.
_ROUTE_PREFIX_TO_SERVICE: dict[str, str] = {
    "/order":        "order-service",
    "/user":         "user-service",
    "/common":       "common-service",
    "/notification": "notification-service",
    "/driver":       "driver-service",
    "/admin":        "admin-service",
    "/report":       "report-service",
}

# ---------------------------------------------------------------------------
# Core linking logic
# ---------------------------------------------------------------------------

_PARAM_RE = re.compile(r":[a-zA-Z_]\w*|\{[^}]+\}")


def _strip_service_prefix(path: str) -> tuple[str, str]:
    """Strip the /order, /user, … service prefix from a frontend endpoint path.

    Returns (service_name_or_empty, stripped_path).
    """
    for prefix, service in _ROUTE_PREFIX_TO_SERVICE.items():
        if path.startswith(prefix + "/") or path == prefix:
            return service, path[len(prefix):]
    return "", path


def _normalize_path(path: str) -> str:
    """Normalise a URL path for matching: lowercase, strip trailing slash,
    replace all named parameters with a single placeholder ``{p}``.
    """
    path = path.rstrip("/")
    path = _PARAM_RE.sub("{p}", path)
    return path.lower()


def _parse_endpoint(endpoint: str) -> tuple[str, str]:
    """Split ``'GET /order/api/v1/orders/:id'`` into ``('GET', '/order/api/v1/orders/:id')``."""
    parts = endpoint.split(None, 1)
    if len(parts) == 2:
        return parts[0].upper(), parts[1]
    return "", endpoint


# ---------------------------------------------------------------------------
# Core linking logic
# ---------------------------------------------------------------------------


def link_services(
    store: KnowledgeStore | None = None,
) -> dict:
    """Match React API calls to Go handler endpoints, creating cross-service edges.

    Steps:
      1. Build normalised lookup of backend endpoints → handlers (from handles edges).
      2. For each React ``calls_api`` edge, normalise the target endpoint and
         look up matching backend handlers.
      3. Create ``x_calls`` (cross-service call) edges linking React components
         directly to Go handler functions.

    Returns:
        Summary dict with counts.
    """
    store = store or get_knowledge_store()

    logger.info("[Linker] Starting cross-service endpoint linking...")

    conn = store._get_conn()

    # Step 1: Build normalised BE endpoint → handler lookup
    be_lookup: dict[tuple[str, str], list[dict]] = {}

    for row in conn.execute(
        "SELECT from_name, to_name, to_service, file "
        "FROM edges WHERE edge_type = 'handles'"
    ).fetchall():
        method, path = _parse_endpoint(row["from_name"])
        if not method:
            continue
        norm = _normalize_path(path)
        key = (method, norm)
        be_lookup.setdefault(key, []).append({
            "endpoint": row["from_name"],
            "handler": row["to_name"],
            "service": row["to_service"],
            "file": row["file"],
        })

    if not be_lookup:
        logger.warning("[Linker] No backend handles edges found — cannot link.")
        return {
            "x_calls_created": 0,
            "be_endpoints": 0,
        }

    logger.info(
        "[Linker] Backend lookup: %d normalised endpoints from %d handles edges",
        len(be_lookup),
        sum(len(v) for v in be_lookup.values()),
    )

    # Step 2: Collect React calls_api edges → api_endpoint
    fe_edges = conn.execute(
        "SELECT from_name, from_type, from_service, to_name, file "
        "FROM edges WHERE edge_type = 'calls_api' AND to_type = 'api_endpoint'"
    ).fetchall()

    # Step 3: Match and create cross-service edges
    new_edges: list[Edge] = []
    seen: set[str] = set()
    matched_count = 0
    unmatched: set[str] = set()

    existing_xcalls = {
        f"{row['from_name']}|x_calls|{row['to_name']}"
        for row in conn.execute(
            "SELECT from_name, to_name FROM edges WHERE edge_type = 'x_calls'"
        ).fetchall()
    }

    for row in fe_edges:
        fe_endpoint = row["to_name"]
        method, full_path = _parse_endpoint(fe_endpoint)
        if not method:
            continue

        _target_svc, stripped_path = _strip_service_prefix(full_path)
        norm = _normalize_path(stripped_path)
        key = (method, norm)

        matches = be_lookup.get(key, [])
        if not matches:
            unmatched.add(fe_endpoint)
            continue

        matched_count += 1
        for be in matches:
            dedup_key = f"{row['from_name']}|x_calls|{be['handler']}"
            if dedup_key in seen or dedup_key in existing_xcalls:
                continue
            seen.add(dedup_key)

            new_edges.append(Edge(
                from_type=row["from_type"],
                from_name=row["from_name"],
                from_service=row["from_service"],
                edge_type="x_calls",
                to_type="function",
                to_name=be["handler"],
                to_service=be["service"],
                file=row["file"],
                metadata={
                    "fe_endpoint": fe_endpoint,
                    "be_endpoint": be["endpoint"],
                },
            ))

    # Step 4: Store new edges
    x_calls_created = 0
    if new_edges:
        x_calls_created = store.store_edges(new_edges)

    if unmatched:
        logger.info(
            "[Linker] %d frontend endpoints had no backend match. Samples: %s",
            len(unmatched),
            list(unmatched)[:5],
        )

    summary = {
        "x_calls_created": x_calls_created,
        "fe_api_edges": len(fe_edges),
        "fe_matched": matched_count,
        "fe_unmatched": len(unmatched),
        "be_endpoints": len(be_lookup),
    }
    logger.info("[Linker] Linking complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse
    import logging as _logging

    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Cross-service endpoint linker — creates x_calls edges between React and Go."
    )
    parser.parse_args()

    import json
    summary = link_services()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
