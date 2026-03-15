import logging
import re
from pathlib import Path

from models.discovery_models import BackendEndpoint, FlowMapping, FrontendApiCall

logger = logging.getLogger(__name__)

# Matches /api/vN prefix at the start of a BE path.
_API_PREFIX_RE = re.compile(r"^/api/v\d+")


def _normalize_be_path(path: str) -> str:
    """Strip /api/vN prefix and convert :param placeholders to {param}."""
    path = _API_PREFIX_RE.sub("", path)
    path = re.sub(r":\w+", "{param}", path)
    return path


def _normalize_fe_url(url: str) -> str:
    """Strip query string and ensure a leading slash."""
    path = url.split("?")[0]
    if not path.startswith("/"):
        path = "/" + path
    return path


def _infer_feature(fe_file: str, url_path: str) -> str:
    """Derive a human-readable feature name from the source file or URL segments."""
    stem = Path(fe_file).stem
    if stem not in ("common", "index", "api", "client", "helpers"):
        return stem.replace("-", "_")
    # Fall back to first meaningful URL segment.
    for seg in url_path.strip("/").split("/"):
        if seg and seg not in ("api", "v1", "v2", "guest", "admin"):
            return seg.replace("-", "_")
    return "unknown"


def map_flows(
    fe_calls: list[FrontendApiCall],
    be_endpoints: list[BackendEndpoint],
) -> list[FlowMapping]:
    """Map frontend API calls to backend endpoints to produce end-to-end flow descriptions.

    Matching strategy:
      - Strip the /api/vN prefix from BE paths and normalise :param → {param}.
      - Ensure FE URLs have a leading slash and strip any query string.
      - Match by (HTTP method, normalised path).

    Args:
        fe_calls:     API calls extracted from the frontend repo.
        be_endpoints: Endpoints extracted from the backend repo.

    Returns:
        List of FlowMapping instances, one per matched FE → BE pair.
    """
    logger.info(
        "[FlowMapper] map_flows called: %d fe_calls  %d be_endpoints",
        len(fe_calls),
        len(be_endpoints),
    )

    # Build a (method, normalised_path) → BackendEndpoint lookup.
    be_lookup: dict[tuple[str, str], BackendEndpoint] = {}
    for ep in be_endpoints:
        key = (ep.method.upper(), _normalize_be_path(ep.path))
        be_lookup[key] = ep

    flows: list[FlowMapping] = []
    for fe in fe_calls:
        norm_url = _normalize_fe_url(fe.url)
        key = (fe.method.upper(), norm_url)
        ep = be_lookup.get(key)
        if ep is None:
            logger.debug("[FlowMapper] No match: %s %s", fe.method.upper(), fe.url)
            continue

        feature = _infer_feature(fe.file, norm_url)
        # Use first service call if available, otherwise fall back to controller.
        backend_service = (
            ep.service_calls[0]
            if ep.service_calls
            else f"{ep.controller}.{ep.controller_method}"
        )
        flows.append(FlowMapping(
            feature=feature,
            frontend_file=fe.file,
            api=f"{fe.method.upper()} {fe.url}",
            backend_controller=f"{ep.controller}.{ep.controller_method}",
            backend_service=backend_service,
        ))

    logger.info(
        "[FlowMapper] map_flows complete: %d/%d FE calls matched to BE endpoints.",
        len(flows),
        len(fe_calls),
    )
    return flows
