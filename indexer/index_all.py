"""index_all — index every configured service then run the cross-service linker.

Usage:
    python -m indexer.index_all            # reads repo paths from .env
    python -m indexer.index_all --dry-run  # print plan, skip actual indexing

All *_REPO_PATH variables are loaded from the .env file at the project root.
Services whose path is missing or empty are skipped with a warning.
The cross-service linker runs automatically after all services are indexed.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service registry — order matters: backends first, then frontend (web2)
# ---------------------------------------------------------------------------
_SERVICES = [
    {"env_var": "ORDER_SERVICE_REPO_PATH",  "service": "order-service",  "lang": "go"},
    {"env_var": "USER_SERVICE_REPO_PATH",   "service": "user-service",   "lang": "go"},
    {"env_var": "DRIVER_SERVICE_REPO_PATH", "service": "driver-service", "lang": "go"},
    {"env_var": "COMMON_SERVICE_REPO_PATH", "service": "common-service", "lang": "go"},
    {"env_var": "WEB_LIBRARY_REPO_PATH",    "service": "web-library",    "lang": "java"},
    {"env_var": "ADMIN_SERVICE_REPO_PATH",  "service": "admin-service",  "lang": "java"},
    {"env_var": "WEB_API_REPO_PATH",        "service": "web-api",        "lang": "java"},
    {"env_var": "WEB2_REPO_PATH",           "service": "web2",           "lang": "react"},
]


def _load_dotenv(env_file: Path) -> None:
    """Minimal .env loader — sets os.environ for keys not already set."""
    if not env_file.is_file():
        return
    with env_file.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def main() -> None:
    ap = argparse.ArgumentParser(description="Index all services and run the linker.")
    ap.add_argument("--no-vectors", action="store_true", help="Skip vector embedding generation.")
    ap.add_argument("--no-link", action="store_true", help="Skip cross-service linker step.")
    ap.add_argument("--dry-run", action="store_true", help="Print plan without indexing.")
    ap.add_argument("--force", action="store_true", help="Bypass incremental hash check and re-index all services.")
    args = ap.parse_args()

    project_root = Path(__file__).parents[1]
    _load_dotenv(project_root / ".env")

    enable_vectors = not args.no_vectors

    # Resolve which services are configured
    plan: list[dict] = []
    for svc_def in _SERVICES:
        repo_path = os.environ.get(svc_def["env_var"], "").strip()
        if not repo_path:
            logger.warning("Skipping %s — %s not set in .env", svc_def["service"], svc_def["env_var"])
            continue
        if not Path(repo_path).is_dir():
            logger.warning("Skipping %s — path does not exist: %s", svc_def["service"], repo_path)
            continue
        plan.append({
            "repo_path": repo_path,
            "service": svc_def["service"],
            "lang": svc_def["lang"],
        })

    if not plan:
        logger.error("No services configured. Set *_REPO_PATH variables in .env")
        sys.exit(1)

    logger.info("Index plan (%d services):", len(plan))
    for i, svc in enumerate(plan, 1):
        logger.info("  %d. %s  [%s]  %s", i, svc["service"], svc["lang"], svc["repo_path"])

    if args.dry_run:
        logger.info("Dry run — exiting.")
        return

    # Import here so the module is only needed at index time
    from indexer.runner import index_service
    from indexer.store import get_knowledge_store

    summaries = []
    for svc in plan:
        logger.info("")
        logger.info("=" * 60)
        logger.info("Indexing: %s", svc["service"])
        logger.info("=" * 60)
        summary = index_service(
            repo_path=svc["repo_path"],
            service=svc["service"],
            enable_vectors=enable_vectors,
            lang=svc["lang"],
            force=args.force,
        )
        summaries.append(summary)

    # Cross-service linker
    if not args.no_link and len(plan) > 1:
        logger.info("")
        logger.info("=" * 60)
        logger.info("Running cross-service linker...")
        logger.info("=" * 60)
        try:
            from indexer.linker import link_services
            link_summary = link_services()
            summaries.append({"step": "linker", **link_summary})
            logger.info("Linker: %s", json.dumps(link_summary))
        except Exception as e:
            logger.warning("Cross-service linking failed: %s", e)

    # Export JSON sidecars once from the final accumulated SQLite state
    store = get_knowledge_store()
    store.export_json_sidecars()

    logger.info("")
    logger.info("=" * 60)
    logger.info("All done. Summary:")
    for s in summaries:
        logger.info("  %s", json.dumps(s))
    logger.info("=" * 60)

    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
