import logging
from pathlib import Path

from models.discovery_models import BackendEndpoint
from explorer.be_scanner_go import scan_go_repo
from explorer.context_builder import _build_function_index, _detect_service_calls

logger = logging.getLogger(__name__)


def _enrich_service_calls(endpoints: list[BackendEndpoint], repo_path: str) -> None:
    """Populate service_calls on each endpoint by scanning handler implementations.

    Reuses the function index and service-call detection logic from context_builder
    so that be_endpoints.json includes the service layer each handler delegates to.
    """
    func_index = _build_function_index(Path(repo_path).resolve())
    enriched = 0
    for ep in endpoints:
        matches = func_index.get(ep.controller_method, [])
        if not matches:
            continue
        # Prefer HTTP handler files over gRPC/other; then any non-test file.
        file_path, _, body = next(
            (m for m in matches if not m[0].endswith("_test.go") and "/api/http/" in m[0]),
            next(
                (m for m in matches if not m[0].endswith("_test.go")),
                matches[0],
            ),
        )
        calls = _detect_service_calls(body)
        if calls:
            ep.service_calls = calls
            enriched += 1
    logger.info(
        "[Scanner/BE] service_calls enriched for %d/%d endpoints.",
        enriched,
        len(endpoints),
    )


def scan_be_repo(repo_path: str, branch: str = "main") -> list[BackendEndpoint]:
    """Scan a backend repository and extract all API endpoint definitions.

    Args:
        repo_path: Absolute or relative path to the backend repo root.
        branch:    Git branch to scan (informational; assumes the working tree
                   is already checked out at the correct branch).

    Returns:
        List of BackendEndpoint instances, one per discovered endpoint.
    """
    logger.info("[Scanner/BE] scan_be_repo called: path=%s  branch=%s", repo_path, branch)
    endpoints = scan_go_repo(repo_path=repo_path)
    _enrich_service_calls(endpoints, repo_path)
    return endpoints
