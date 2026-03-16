"""Cross-service endpoint linker — Phase 3 of the graph evolution.

After all services are indexed, this module matches React API endpoints to
Go handler endpoints and creates cross-service edges that enable full-stack
graph traversal:

    React component ──calls_api──▶ API endpoint
                                        │
                                   (linker matches)
                                        │
    React component ──x_calls──▶ Go handler ──calls──▶ service ──delegates_to──▶ repo

The linker also injects missing ``handles`` edges for Go services when those
edges were not generated during indexing (e.g. because the Go flow extractor
doesn't extract HTTP endpoints).  It reads ``be_endpoints.json`` as a
supplementary data source.

Usage:
    # After indexing all services:
    from indexer.linker import link_services
    link_services()

    # Or standalone:
    python -m indexer.linker
"""

import json
import logging
import re
from pathlib import Path

from indexer.models import Edge
from indexer.store import KnowledgeStore, get_knowledge_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_DISCOVERY_DIR = Path(__file__).parents[1] / "docs" / "discovery"

# Service route prefix in React → backend service name.
# Matches _CLIENT_BASE_MAP in indexer/parsers/react/parser.py.
_ROUTE_PREFIX_TO_SERVICE: dict[str, str] = {
    "/order":        "order-service",
    "/user":         "user-service",
    "/common":       "common-service",
    "/notification": "notification-service",
    "/driver":       "driver-service",
    "/admin":        "admin-service",
    "/report":       "report-service",
}

# Backend service name → discovery subdirectory name
_SERVICE_DISCOVERY_DIR: dict[str, str] = {
    "order-service": "order-services",
    # Add other services here when their discovery dirs differ from service name
}

# ---------------------------------------------------------------------------
# Endpoint normalisation
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
# Discovery-data helpers
# ---------------------------------------------------------------------------


def _load_be_endpoints(discovery_dir: Path, service: str) -> list[dict]:
    """Load ``be_endpoints.json`` for a given backend service."""
    subdir = _SERVICE_DISCOVERY_DIR.get(service, service)
    path = discovery_dir / subdir / "be_endpoints.json"
    if not path.exists():
        logger.debug("[Linker] No be_endpoints.json at %s", path)
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("[Linker] Failed to read %s: %s", path, exc)
    return []


# ---------------------------------------------------------------------------
# Core linking logic
# ---------------------------------------------------------------------------


def _ensure_handles_edges(
    store: KnowledgeStore,
    discovery_dir: Path,
) -> int:
    """Inject ``handles`` edges for Go services using discovery data.

    If the indexer already generated ``handles`` edges (because the Go parser
    populated the ``endpoint`` field on ServiceFlow), this is a no-op for
    those endpoints.  For any endpoint in ``be_endpoints.json`` that does NOT
    yet have a ``handles`` edge, a new one is created.

    Returns:
        Number of new ``handles`` edges inserted.
    """
    conn = store._get_conn()

    # Collect existing handles edges (endpoint → handler already in DB)
    existing = {
        row["from_name"]
        for row in conn.execute(
            "SELECT DISTINCT from_name FROM edges WHERE edge_type = 'handles'"
        ).fetchall()
    }

    # Determine which backend services are indexed
    be_services = {
        row["service"]
        for row in conn.execute(
            "SELECT DISTINCT service FROM service_flows"
        ).fetchall()
    }

    new_edges: list[Edge] = []
    seen: set[str] = set()

    for service in be_services:
        endpoints = _load_be_endpoints(discovery_dir, service)
        if not endpoints:
            continue

        # Build handler_name → qualified_name lookup from existing flows
        handler_lookup: dict[str, str] = {}
        for row in conn.execute(
            "SELECT handler_name, handler_file FROM service_flows WHERE service = ?",
            (service,),
        ).fetchall():
            handler_lookup[row["handler_name"]] = f"{service}.{row['handler_name']}"

        for ep in endpoints:
            method = ep.get("method", "").upper()
            path = ep.get("path", "")
            controller_method = ep.get("controller_method", "")
            ep_file = ep.get("file", "")

            if not method or not path or not controller_method:
                continue

            endpoint_str = f"{method} {path}"
            if endpoint_str in existing:
                continue

            # Resolve handler qualified name
            handler_qn = handler_lookup.get(
                controller_method,
                f"{service}.{controller_method}",
            )

            key = f"{endpoint_str}|handles|{handler_qn}"
            if key in seen:
                continue
            seen.add(key)

            new_edges.append(Edge(
                from_type="api_endpoint",
                from_name=endpoint_str,
                from_service=service,
                edge_type="handles",
                to_type="function",
                to_name=handler_qn,
                to_service=service,
                file=ep_file,
            ))

    if new_edges:
        count = store.store_edges(new_edges)
        logger.info(
            "[Linker] Injected %d handles edges from discovery data", count
        )
        return count
    return 0


def link_services(
    store: KnowledgeStore | None = None,
    discovery_dir: Path | None = None,
) -> dict:
    """Match React API calls to Go handler endpoints, creating cross-service edges.

    Steps:
      1. Ensure Go ``handles`` edges exist (inject from be_endpoints.json if needed).
      2. Build normalised lookup of backend endpoints → handlers.
      3. For each React ``calls_api`` edge, normalise the target endpoint and
         look up matching backend handlers.
      4. Create ``x_calls`` (cross-service call) edges linking React components
         directly to Go handler functions.

    Returns:
        Summary dict with counts.
    """
    store = store or get_knowledge_store()
    discovery_dir = discovery_dir or _DEFAULT_DISCOVERY_DIR

    logger.info("[Linker] Starting cross-service endpoint linking...")

    # Step 1: Ensure handles edges exist for Go services
    handles_injected = _ensure_handles_edges(store, discovery_dir)

    conn = store._get_conn()

    # Step 2: Build normalised BE endpoint → handler lookup
    #   key = (METHOD, normalised_path_without_service_prefix)
    #   value = list of {handler, service, endpoint, file}
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
            "handles_injected": handles_injected,
            "x_calls_created": 0,
            "unmatched_endpoints": 0,
        }

    logger.info(
        "[Linker] Backend lookup: %d normalised endpoints from %d handles edges",
        len(be_lookup),
        sum(len(v) for v in be_lookup.values()),
    )

    # Step 3: Collect React calls_api edges → api_endpoint
    fe_edges = conn.execute(
        "SELECT from_name, from_type, from_service, to_name, file "
        "FROM edges WHERE edge_type = 'calls_api' AND to_type = 'api_endpoint'"
    ).fetchall()

    # Step 4: Match and create cross-service edges
    new_edges: list[Edge] = []
    seen: set[str] = set()
    matched_count = 0
    unmatched: set[str] = set()

    # Also check existing x_calls edges to avoid duplicates
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

        # Strip service prefix from React endpoint path
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

    # Step 5: Store new edges
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
        "handles_injected": handles_injected,
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
    parser.add_argument(
        "--discovery-dir",
        default=str(_DEFAULT_DISCOVERY_DIR),
        help="Path to docs/discovery/ directory.",
    )
    args = parser.parse_args()

    summary = link_services(discovery_dir=Path(args.discovery_dir))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
