#!/usr/bin/env python3
"""CLI entry point for the system discovery module.

Commands:
    scan-fe   Scan the frontend repository for outgoing API calls.
    scan-be   Scan the backend repository for endpoint definitions and
              extract handler code context into docs/discovery/order-services/code_context/.
    map-flows Match FE calls to BE endpoints and write flow mappings.
    scan-all  Run scan-fe, scan-be and map-flows in sequence.

Usage:
    python scripts/run_discovery.py scan-fe
    python scripts/run_discovery.py scan-be --repo-path /path/to/backend
    python scripts/run_discovery.py map-flows
    python scripts/run_discovery.py scan-all
"""

import argparse
import dataclasses
import json
import logging
import sys
import types
from pathlib import Path

# ---------------------------------------------------------------------------
# Make the project root importable when the script is run directly.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from app.config import settings  # noqa: E402  (import after sys.path patch)
from explorer.be_scanner import scan_be_repo  # noqa: E402
from explorer.context_builder import build_code_context  # noqa: E402
from explorer.fe_scanner import scan_fe_repo  # noqa: E402
from explorer.flow_mapper import map_flows  # noqa: E402
from models.discovery_models import BackendEndpoint, FrontendApiCall  # noqa: E402

# ---------------------------------------------------------------------------
# Logging — same format used across the project.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_DISCOVERY_DIR = Path(settings.discovery_output_dir)
_ORDER_SERVICES_DIR = _DISCOVERY_DIR / "order-services"
_WEB2_DIR = _DISCOVERY_DIR / "web2"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve(arg_value: str, setting_value: str, label: str) -> str:
    """Return arg_value if provided, otherwise fall back to the settings value."""
    resolved = arg_value or setting_value
    if not resolved:
        logger.error(
            "[Discovery] %s is not set. Pass --%s or set the corresponding env var in .env",
            label.upper().replace("-", "_"),
            label,
        )
        sys.exit(1)
    return resolved


def _save_json(data: list, filename: str) -> Path:
    """Serialise a list of dataclass instances to JSON and write to the output directory."""
    output_dir = Path(settings.discovery_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename
    with out_path.open("w", encoding="utf-8") as f:
        json.dump([dataclasses.asdict(item) for item in data], f, indent=2, ensure_ascii=False)
    logger.info("[Discovery] Saved %d records → %s", len(data), out_path)
    return out_path


def _save_json_to(data: list, target_path: Path) -> Path:
    """Serialise dataclass list to a specific target path."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8") as f:
        json.dump([dataclasses.asdict(item) for item in data], f, indent=2, ensure_ascii=False)
    logger.info("[Discovery] Saved %d records → %s", len(data), target_path)
    return target_path


def _load_json_as(filename: str, cls: type) -> list:
    """Load a JSON file from the output directory and deserialise into dataclass instances."""
    path = Path(settings.discovery_output_dir) / filename
    if not path.exists():
        logger.error("[Discovery] Expected file not found: %s — run the relevant scan first.", path)
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return [cls(**item) for item in json.load(f)]


def _load_json_as_from(path: Path, cls: type) -> list:
    """Load JSON from an explicit path and deserialize into dataclasses."""
    if not path.exists():
        logger.error("[Discovery] Expected file not found: %s — run the relevant scan first.", path)
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return [cls(**item) for item in json.load(f)]


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_scan_fe(args: types.SimpleNamespace) -> None:
    repo_path = _resolve(args.repo_path, settings.fe_repo_path, "fe-repo-path")
    branch = args.branch or settings.fe_branch
    logger.info("[Discovery] Starting frontend scan: path=%s  branch=%s", repo_path, branch)
    results = scan_fe_repo(repo_path=repo_path, branch=branch)
    _save_json_to(results, _WEB2_DIR / "fe_api_inventory.json")
    logger.info("[Discovery] scan-fe complete: %d API calls found.", len(results))


def cmd_scan_be(args: types.SimpleNamespace) -> None:
    repo_path = _resolve(args.repo_path, settings.be_repo_path, "be-repo-path")
    branch = args.branch or settings.be_branch
    logger.info("[Discovery] Starting backend scan: path=%s  branch=%s", repo_path, branch)
    results = scan_be_repo(repo_path=repo_path, branch=branch)
    _save_json_to(results, _ORDER_SERVICES_DIR / "be_endpoints.json")
    logger.info("[Discovery] scan-be: %d endpoints found. Building code context...", len(results))
    written = build_code_context(
        be_repo_path=repo_path,
        index_path=str(_ORDER_SERVICES_DIR / "be_endpoints.json"),
        output_dir=str(_ORDER_SERVICES_DIR / "code_context"),
    )
    logger.info("[Discovery] scan-be complete: %d context file(s) written.", len(written))


def cmd_map_flows(args: types.SimpleNamespace) -> None:
    logger.info("[Discovery] Loading scan results for flow mapping...")
    fe_inventory_path = _WEB2_DIR / "fe_api_inventory.json"
    be_endpoints_path = _ORDER_SERVICES_DIR / "be_endpoints.json"
    # Backward compatibility with legacy flat structure.
    if not fe_inventory_path.exists():
        fe_inventory_path = _DISCOVERY_DIR / "fe_api_inventory.json"
    if not be_endpoints_path.exists():
        be_endpoints_path = _DISCOVERY_DIR / "be_endpoints.json"

    fe_calls: list[FrontendApiCall] = _load_json_as_from(fe_inventory_path, FrontendApiCall)
    be_endpoints: list[BackendEndpoint] = _load_json_as_from(be_endpoints_path, BackendEndpoint)
    flows = map_flows(fe_calls=fe_calls, be_endpoints=be_endpoints)
    _save_json(flows, "flow_mappings.json")
    logger.info("[Discovery] map-flows complete: %d flows mapped.", len(flows))


def cmd_scan_all(args: types.SimpleNamespace) -> None:
    logger.info("[Discovery] Starting full scan (scan-fe → scan-be → map-flows)...")
    cmd_scan_fe(types.SimpleNamespace(
        repo_path=getattr(args, "fe_repo_path", ""),
        branch=getattr(args, "fe_branch", ""),
    ))
    cmd_scan_be(types.SimpleNamespace(
        repo_path=getattr(args, "be_repo_path", ""),
        branch=getattr(args, "be_branch", ""),
    ))
    cmd_map_flows(args)
    logger.info("[Discovery] scan-all complete.")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_discovery",
        description="System discovery CLI — scan external repos and map logistics service flows.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/run_discovery.py scan-fe\n"
            "  python scripts/run_discovery.py scan-be --repo-path /path/to/backend\n"
            "  python scripts/run_discovery.py map-flows\n"
            "  python scripts/run_discovery.py scan-all\n"
            "  python scripts/run_discovery.py scan-all --fe-repo-path /fe --be-repo-path /be\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- scan-fe ---
    p_fe = subparsers.add_parser("scan-fe", help="Scan the frontend repository for API calls.")
    p_fe.add_argument(
        "--repo-path", default="", metavar="PATH",
        help="Path to the FE repo root. Overrides FE_REPO_PATH env var.",
    )
    p_fe.add_argument(
        "--branch", default="", metavar="BRANCH",
        help="Branch to scan. Overrides FE_BRANCH env var.",
    )
    p_fe.set_defaults(func=cmd_scan_fe)

    # --- scan-be ---
    p_be = subparsers.add_parser("scan-be", help="Scan the backend repository for API endpoints.")
    p_be.add_argument(
        "--repo-path", default="", metavar="PATH",
        help="Path to the BE repo root. Overrides BE_REPO_PATH env var.",
    )
    p_be.add_argument(
        "--branch", default="", metavar="BRANCH",
        help="Branch to scan. Overrides BE_BRANCH env var.",
    )
    p_be.set_defaults(func=cmd_scan_be)

    # --- map-flows ---
    p_map = subparsers.add_parser(
        "map-flows",
        help="Match FE API calls to BE endpoints (requires prior scan-fe and scan-be output).",
    )
    p_map.set_defaults(func=cmd_map_flows)

    # --- scan-all ---
    p_all = subparsers.add_parser("scan-all", help="Run scan-fe, scan-be, and map-flows in sequence.")
    p_all.add_argument(
        "--fe-repo-path", dest="fe_repo_path", default="", metavar="PATH",
        help="Path to the FE repo root. Overrides FE_REPO_PATH env var.",
    )
    p_all.add_argument(
        "--be-repo-path", dest="be_repo_path", default="", metavar="PATH",
        help="Path to the BE repo root. Overrides BE_REPO_PATH env var.",
    )
    p_all.add_argument(
        "--fe-branch", dest="fe_branch", default="", metavar="BRANCH",
        help="FE branch to scan. Overrides FE_BRANCH env var.",
    )
    p_all.add_argument(
        "--be-branch", dest="be_branch", default="", metavar="BRANCH",
        help="BE branch to scan. Overrides BE_BRANCH env var.",
    )
    p_all.set_defaults(func=cmd_scan_all)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
