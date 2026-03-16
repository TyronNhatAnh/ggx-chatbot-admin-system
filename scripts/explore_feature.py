#!/usr/bin/env python3
"""CLI for AI-powered feature exploration.

Runs a single-pass Gemini pipeline:
    Gemini reads source code and returns both a structured JSON index
    and a human-readable requirement doc.

Usage:
    python scripts/explore_feature.py --spec explorer/feature_specs/check_price.yaml
    python scripts/explore_feature.py --spec explorer/feature_specs/check_price.yaml \\
        --be-repo /path/to/be --fe-repo /path/to/fe
    python scripts/explore_feature.py --interactive
    python scripts/explore_feature.py --feature "check price for guest + home moving"
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

from google import genai
from google.genai import types
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_SPEC_DIR = _PROJECT_ROOT / "explorer" / "feature_specs"
_DISCOVERY_DIR = _PROJECT_ROOT / "docs" / "discovery"
_DISCOVERY_ORDER_DIR = _DISCOVERY_DIR / "order-services"
_DISCOVERY_WEB2_DIR = _DISCOVERY_DIR / "web2"


def _load_discovery_records(new_path: Path, legacy_path: Path) -> list[dict]:
    """Read discovery records from namespaced path first, then legacy fallback."""
    if new_path.exists():
        return _load_json_list(new_path)
    return _load_json_list(legacy_path)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "new_feature"


def _extract_tokens(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(tok) >= 3]


def _load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _run_discovery_scan_all(be_repo: str, fe_repo: str) -> None:
    """Run discovery scan-all so feature auto-spec has fresh FE/BE mappings."""
    cmd = [sys.executable, "scripts/run_discovery.py", "scan-all"]
    if fe_repo:
        cmd.extend(["--fe-repo-path", fe_repo])
    if be_repo:
        cmd.extend(["--be-repo-path", be_repo])

    logger.info("[Auto] Running discovery scan-all...")
    subprocess.run(cmd, cwd=_PROJECT_ROOT, check=True)


def _validate_spec_shape(spec: dict) -> bool:
    if not isinstance(spec, dict):
        return False
    feature = spec.get("feature")
    if not isinstance(feature, dict):
        return False
    required_keys = [
        "name",
        "description",
        "be_files",
        "fe_files",
        "api_scope",
        "go_types",
        "ts_types",
        "business_terms",
    ]
    return all(key in feature for key in required_keys)


def _gemini_enrich_spec(feature_input: str, draft_spec: dict) -> dict:
    """Use Gemini to enrich draft feature spec from current discovery artifacts."""
    from app.config import settings

    be_map = _load_discovery_records(
        _DISCOVERY_ORDER_DIR / "be_endpoints.json",
        _DISCOVERY_DIR / "be_endpoints.json",
    )
    fe_inventory = _load_discovery_records(
        _DISCOVERY_WEB2_DIR / "fe_api_inventory.json",
        _DISCOVERY_DIR / "fe_api_inventory.json",
    )
    flows = _load_json_list(_DISCOVERY_DIR / "flow_mappings.json")

    prompt = (
        "You are an expert software auditor. "
        "Given a draft feature spec and discovery artifacts, output ONLY valid YAML "
        "with exactly this shape:\n"
        "feature:\n"
        "  name: string\n"
        "  description: string\n"
        "  be_files: [string]\n"
        "  fe_files: [string]\n"
        "  api_scope: [\"METHOD /path\"]\n"
        "  go_types: [string]\n"
        "  ts_types: [string]\n"
        "  business_terms: [string]\n\n"
        "Rules:\n"
        "1) Use strict evidence only from provided artifacts.\n"
        "2) Keep be_files/fe_files specific but complete for this feature.\n"
        "3) api_scope must not be empty.\n"
        "4) Do not add markdown or explanations.\n\n"
        f"Feature text: {feature_input}\n\n"
        f"Draft spec YAML:\n{yaml.safe_dump(draft_spec, sort_keys=False, allow_unicode=False)}\n"
        f"BE endpoint map (truncated):\n{json.dumps(be_map[:120], ensure_ascii=False)}\n"
        f"FE API inventory (truncated):\n{json.dumps(fe_inventory[:220], ensure_ascii=False)}\n"
        f"Flow mappings (truncated):\n{json.dumps(flows[:180], ensure_ascii=False)}\n"
    )

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        response = client.models.generate_content(
            model=settings.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=8192,
                response_mime_type="text/plain",
            ),
        )
    except Exception as exc:
        logger.warning("[Spec] Gemini enrich skipped due to error: %s", exc)
        return draft_spec
    raw = (response.text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("yaml"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    parsed = yaml.safe_load(raw)
    if _validate_spec_shape(parsed):
        return parsed
    return draft_spec


def _normalize_api_path(path: str) -> str:
    normalized = path.strip()
    if normalized.startswith("/api/v1"):
        normalized = normalized[len("/api/v1"):]
    return normalized or "/"


def _auto_build_spec(feature_input: str, selected_api_scope: list[str] | None = None) -> tuple[str, dict]:
    tokens = set(_extract_tokens(feature_input))
    feature_name = _slugify(feature_input)

    be_map = _load_discovery_records(
        _DISCOVERY_ORDER_DIR / "be_endpoints.json",
        _DISCOVERY_DIR / "be_endpoints.json",
    )
    fe_inventory = _load_discovery_records(
        _DISCOVERY_WEB2_DIR / "fe_api_inventory.json",
        _DISCOVERY_DIR / "fe_api_inventory.json",
    )

    matched_endpoints: list[dict] = []
    for item in be_map:
        method = str(item.get("method", "")).upper()
        path = str(item.get("path", ""))
        function = str(item.get("controller_method", item.get("function", "")))
        haystack = f"{method} {path} {function}".lower()
        if not tokens or any(tok in haystack for tok in tokens):
            matched_endpoints.append(item)

    if selected_api_scope is None:
        api_scope = []
        for ep in matched_endpoints:
            method = str(ep.get("method", "")).upper().strip()
            path = _normalize_api_path(str(ep.get("path", "")).strip())
            if method and path:
                api_scope.append(f"{method} {path}")
        api_scope = sorted(set(api_scope))
    else:
        api_scope = selected_api_scope

    endpoint_paths = {scope.split(" ", 1)[1].lower() for scope in api_scope if " " in scope}

    be_files = {
        str(ep.get("file", "")).strip()
        for ep in matched_endpoints
        if str(ep.get("file", "")).strip()
    }
    be_files.add("internal/api/http/v1/routes.go")

    fe_files = set()
    for item in fe_inventory:
        file = str(item.get("file", "")).strip()
        url = str(item.get("url", "")).strip().lower()
        haystack = f"{file} {url}".lower()
        if endpoint_paths and any(p in url for p in endpoint_paths):
            if file:
                fe_files.add(file)
            continue
        if not tokens or any(tok in haystack for tok in tokens):
            if file:
                fe_files.add(file)

    if not fe_files:
        fe_files.add("src/lib/apis/order.ts")

    spec = {
        "feature": {
            "name": feature_name,
            "description": feature_input,
            "be_files": sorted(be_files),
            "fe_files": sorted(fe_files),
            "api_scope": api_scope,
            "go_types": [],
            "ts_types": [],
            "business_terms": [
                "actor",
                "trigger",
                "validation",
                "error code",
            ],
        }
    }
    return feature_name, spec


def _write_spec_file(feature_name: str, spec: dict, output_path: str = "") -> Path:
    _SPEC_DIR.mkdir(parents=True, exist_ok=True)
    target = Path(output_path) if output_path else (_SPEC_DIR / f"{feature_name}.yaml")
    if not target.is_absolute():
        target = _PROJECT_ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return target


def _interactive_select_api_scope(feature_input: str) -> list[str]:
    be_map = _load_discovery_records(
        _DISCOVERY_ORDER_DIR / "be_endpoints.json",
        _DISCOVERY_DIR / "be_endpoints.json",
    )
    tokens = set(_extract_tokens(feature_input))
    matched: list[str] = []

    for item in be_map:
        method = str(item.get("method", "")).upper().strip()
        path = _normalize_api_path(str(item.get("path", "")).strip())
        function = str(item.get("controller_method", item.get("function", "")))
        candidate = f"{method} {path}"
        haystack = f"{candidate} {function}".lower()
        if not method or not path:
            continue
        if not tokens or any(tok in haystack for tok in tokens):
            matched.append(candidate)

    matched = sorted(set(matched))
    if not matched:
        return []

    print("\nMatched APIs from discovery:")
    for i, api in enumerate(matched, 1):
        print(f"  {i}. {api}")
    raw = input("Select API numbers (comma-separated, Enter=all): ").strip()
    if not raw:
        return matched

    selected: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit():
            idx = int(token)
            if 1 <= idx <= len(matched):
                selected.append(matched[idx - 1])
    return sorted(set(selected))


def _interactive_choose_or_create_spec(args: argparse.Namespace) -> Path:
    _SPEC_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(p for p in _SPEC_DIR.glob("*.yaml") if p.name != "_template.yaml")

    print("\n=== Explore Feature Interactive ===")
    print("1) Run an existing feature spec")
    print("2) Describe feature, auto-create spec, then run")
    choice = input("Choose 1 or 2: ").strip() or "2"

    if choice == "1" and existing:
        print("\nAvailable specs:")
        for i, spec in enumerate(existing, 1):
            print(f"  {i}. {spec.relative_to(_PROJECT_ROOT)}")
        raw = input("Select number: ").strip()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(existing):
                return existing[idx - 1]
        raise ValueError("Invalid selection for existing spec")

    feature_input = input("\nDescribe the feature: ").strip()
    if not feature_input:
        raise ValueError("Feature description is required")

    selected_scope = _interactive_select_api_scope(feature_input)
    feature_name, spec = _auto_build_spec(feature_input, selected_scope)
    spec_path = _write_spec_file(feature_name, spec, output_path=args.output_spec)

    print(f"\nCreated spec: {spec_path.relative_to(_PROJECT_ROOT)}")
    return spec_path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="explore_feature",
        description="AI-powered feature exploration: single-pass Gemini index + requirement generation.",
    )
    parser.add_argument(
        "--spec", default="", metavar="PATH",
        help="Path to a feature YAML spec (e.g. explorer/feature_specs/check_price.yaml).",
    )
    parser.add_argument(
        "--feature", default="", metavar="TEXT",
        help="Feature description in plain language. Auto-builds a spec from discovery artifacts.",
    )
    parser.add_argument(
        "--interactive", action="store_true",
        help="Interactive mode: choose existing spec or describe feature to auto-create one.",
    )
    parser.add_argument(
        "--output-spec", default="", metavar="PATH",
        help="Optional output path for auto-created spec file.",
    )
    parser.add_argument(
        "--write-spec-only", action="store_true",
        help="Create/update spec only, do not run feature exploration.",
    )
    parser.add_argument(
        "--full-auto", action="store_true",
        help=(
            "One-shot mode: run discovery scan-all, auto-create spec, "
            "Gemini-enrich spec, then run feature exploration."
        ),
    )
    parser.add_argument(
        "--be-repo", default="", metavar="PATH",
        help="Path to the BE repo root. Overrides BE_REPO_PATH in .env.",
    )
    parser.add_argument(
        "--fe-repo", default="", metavar="PATH",
        help="Path to the FE repo root. Overrides FE_REPO_PATH in .env.",
    )
    args = parser.parse_args()

    if args.full_auto:
        if not args.feature:
            parser.error("--full-auto requires --feature TEXT.")

        _run_discovery_scan_all(be_repo=args.be_repo, fe_repo=args.fe_repo)
        feature_name, draft_spec = _auto_build_spec(args.feature)
        final_spec = _gemini_enrich_spec(args.feature, draft_spec)
        spec_path = _write_spec_file(feature_name, final_spec, output_path=args.output_spec)
        logger.info("[Spec] Full-auto generated: %s", spec_path)
    elif args.interactive:
        spec_path = _interactive_choose_or_create_spec(args)
    elif args.feature:
        feature_name, spec = _auto_build_spec(args.feature)
        spec_path = _write_spec_file(feature_name, spec, output_path=args.output_spec)
        logger.info("[Spec] Auto-created: %s", spec_path)
    elif args.spec:
        spec_path = Path(args.spec)
        if not spec_path.is_absolute():
            spec_path = (_PROJECT_ROOT / spec_path).resolve()
    else:
        parser.error("Provide --spec, or --feature, or use --interactive.")

    if args.write_spec_only:
        print(f"\n✓ Spec ready: {spec_path}")
        return

    from explorer.ai_explorer import explore_feature

    try:
        out_path = explore_feature(
            spec_path=str(spec_path),
            be_repo_path=args.be_repo,
            fe_repo_path=args.fe_repo,
        )
        logger.info("[Done] Requirement doc: %s", out_path)
        print(f"\n✓ Done: {out_path}")
    except Exception as exc:
        msg = str(exc)
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg or "quota" in msg.lower():
            print(
                "\n✗ Gemini quota exhausted. "
                f"Spec is already saved at: {spec_path}. "
                "Retry later with the same --spec file."
            )
            raise SystemExit(2)
        raise


if __name__ == "__main__":
    main()
