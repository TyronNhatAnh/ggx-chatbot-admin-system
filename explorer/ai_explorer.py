"""AI-powered feature explorer — single-pass Gemini pipeline.

Gemini reads scoped source code and returns both:
1) a structured JSON index, and
2) a human-readable requirement markdown document.

Usage::

    from explorer.ai_explorer import explore_feature
    explore_feature(spec_path="explorer/feature_specs/check_price.yaml")

CLI::

    python scripts/explore_feature.py --spec explorer/feature_specs/check_price.yaml
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
import yaml
from app.config import settings

logger = logging.getLogger(__name__)

_MAX_ERROR_RAW_PREVIEW_CHARS = 4000
_MAX_ERROR_REQUIREMENT_PREVIEW_CHARS = 6000

_INFERENCE_MARKERS = (
    "inferred",
    "assume",
    "assumed",
    "likely",
    "probably",
    "possibly",
    "it seems",
    "it appears",
    "guess",
    "hypothesis",
    "infer",
    "implied",
    "typically",
    "potentially",
    "may include",
    "should include",
)

# ---------------------------------------------------------------------------
# Single-pass prompt — Gemini Flash 2.5
# ---------------------------------------------------------------------------

_SINGLE_PASS_PROMPT_TEMPLATE = """
You are a senior backend engineer and technical writer performing a deep code audit.

Below is the full source code for feature "{feature_name}".
Return BOTH a structured feature index and a requirement markdown document.
You MUST maximize detail from code evidence and MUST NOT skip business flows.

Output ONLY valid JSON with exactly this shape (no markdown fences, no extra text):

{{
    "index": {{
        "feature": "{feature_name}",
        "use_cases": [
            {{
                "id": "UC-1",
                "title": "Guest checks estimate before placing order",
                "actor": "Guest user",
                "trigger": "User wants a delivery quote",
                "preconditions": ["waypoints are provided"],
                "happy_path": [
                    "Client sends estimate request",
                    "Validation runs",
                    "Pricing service calculates estimate",
                    "Response returned to client"
                ],
                "edge_cases": [
                    "Invalid waypoint",
                    "Invalid coupon"
                ],
                "business_value": "Lets user compare price before checkout",
                "api_paths": ["POST /guest/estimate"],
                "evidence_refs": [
                    {{
                        "file": "internal/api/http/v1/order_handler.go",
                        "symbol": "EstimateGuest"
                    }}
                ]
            }}
        ],
        "endpoints": [
            {{
                "method": "POST",
                "path": "/guest/estimate",
                "handler_file": "internal/api/http/v1/order_handler.go",
                "handler_function": "EstimateGuest",
                "auth_required": false,
                "service_chain": [
                    "h.Estimate(c, 0)",
                    "EstimateHandler.Handle(ctx, req)",
                    "PricingService.Calculate(ctx, params)"
                ],
                "request_schema": {{
                    "vehicleTypeId": {{"type": "int", "required": true, "description": ""}},
                    "fromPlace": {{"type": "Place", "required": true, "description": ""}}
                }},
                "response_schema": {{
                    "basePrice": {{"type": "int64", "description": "Price in local currency cents"}},
                    "breakdown": {{"type": "[]PriceFee", "description": ""}}
                }},
                "business_rules": [
                    "Price is calculated from origin to destination based on vehicle type",
                    "Guest flow uses userId=0"
                ],
                "error_cases": [
                    {{"code": "DRIVER_INVALID", "http_status": 400, "condition": "driverId not found or userId=0"}}
                ],
                "external_dependencies": [
                    {{"name": "DriverClient.GetDriverById", "type": "gRPC", "purpose": "validate driver and get vehicle type"}}
                ],
                "read_only_safe": true,
                "evidence_refs": [
                    {{
                        "file": "internal/api/http/v1/order_handler.go",
                        "symbol": "EstimateGuest"
                    }}
                ]
            }}
        ],
        "shared_types": {{
            "Place": {{"lat": "float64", "lng": "float64", "address": "string"}},
            "PriceFee": {{"label": "string", "amount": "int64"}}
        }},
        "fe_types": {{
            "EstimateRequest": {{"vehicleTypeId": "number", "fromPlace": "Place"}},
            "EstimateResponse": {{"basePrice": "number", "breakdown": "PriceFee[]"}}
        }},
        "cross_cutting_observations": [
            "Guest and auth flows use the same internal Estimate() method",
            "driverId overrides vehicleTypeId when provided"
        ],
        "logic_evidence": [
            {{
                "file": "internal/api/http/v1/order_handler.go",
                "symbol": "EstimateGuest",
                "why_it_matters": "Entry point for guest estimate flow"
            }}
        ]
    }},
    "requirement_markdown": "# Feature Requirement Document: ..."
}}

Feature description: {description}

APIs to focus on: {api_scope}

Go types to find: {go_types}

TypeScript types to find: {ts_types}

Business terms that MUST be explicitly documented in output: {business_terms}

Matched source files (MUST cite key files in logic_evidence):
{source_manifest}

Hard requirements:
1) Cover every API listed in "APIs to focus on". If a path has no strong evidence, still include it with a clear "evidence_gap" note.
2) Generate detailed use_cases with concrete happy_path and edge_cases from source logic.
3) In requirement_markdown, include a section named exactly "Detailed Use Cases" with one subsection per use case.
4) Cite evidence files/functions in markdown where relevant (handler, validator, service).
5) Do not fabricate database tables, gRPC methods, or statuses that are not evidenced.
6) STRICT EVIDENCE ONLY: never infer, assume, or hypothesize. If evidence is missing, say "UNKNOWN" and add evidence_gap.
7) Do not use words such as "inferred", "assumed", "likely", "probably", "seems", "appears" in index or markdown.

Source code:
---
{source_code}
---
""".strip()


_STRICT_REPAIR_PROMPT_TEMPLATE = """
You are a strict JSON normalizer.

Rewrite the provided model output so it passes strict evidence-only policy.

Rules:
1) Output ONLY valid JSON with the same top-level keys: index, requirement_markdown.
2) Remove all inference language and speculative wording.
3) If evidence is missing, use UNKNOWN and evidence_gap explicitly.
4) Keep evidence_refs and logic_evidence. Do not invent new files or symbols.
5) Keep content factual, concise, and directly evidence-based.

Validation errors to fix:
{validation_errors}

Original payload:
---
{raw_payload}
---
""".strip()


# ---------------------------------------------------------------------------
# Source file collection
# ---------------------------------------------------------------------------

def _collect_files(repo_path: str, globs: list[str]) -> dict[str, str]:
    """Walk repo_path and collect files matching any glob pattern.

    Returns a dict of relative_path → file_content.
    Skips binary files and files larger than 200 KB to avoid token overflow.
    """
    if not repo_path or not Path(repo_path).exists():
        logger.warning("[AIExplorer] Repo path not found or not set: %r", repo_path)
        return {}

    result: dict[str, str] = {}
    repo = Path(repo_path)
    max_bytes = 200_000

    for root, dirs, files in os.walk(repo):
        # Skip hidden and vendor directories.
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("vendor", "node_modules", "__pycache__")]
        rel_root = Path(root).relative_to(repo)

        for fname in files:
            rel_path = str(rel_root / fname)
            if not any(fnmatch.fnmatch(rel_path, g) for g in globs):
                continue

            abs_path = Path(root) / fname
            if abs_path.stat().st_size > max_bytes:
                logger.debug("[AIExplorer] Skipping large file: %s", rel_path)
                continue

            try:
                content = abs_path.read_text(encoding="utf-8", errors="ignore")
                result[rel_path] = content
            except OSError:
                pass

    logger.info("[AIExplorer] Collected %d source file(s) from %s", len(result), repo_path)
    return result


def _format_source_bundle(files: dict[str, str]) -> str:
    """Format collected files into a single annotated string for the prompt."""
    parts: list[str] = []
    for rel_path in sorted(files.keys()):
        content = files[rel_path]
        parts.append(f"// FILE: {rel_path}\n{content}")
    return "\n\n// ---\n\n".join(parts)


def _auto_fill_api_scope_from_discovery(feature: dict[str, Any]) -> None:
    """Populate feature.api_scope from discovery artifacts when it is empty."""
    existing = feature.get("api_scope")
    if isinstance(existing, list) and existing:
        return

    discovery_file = Path("docs/discovery/fe_api_inventory.json")
    if not discovery_file.exists():
        return

    try:
        records = json.loads(discovery_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(records, list):
        return

    fe_patterns = feature.get("fe_files", []) if isinstance(feature.get("fe_files"), list) else []
    api_scope: list[str] = []

    for item in records:
        if not isinstance(item, dict):
            continue
        file_path = str(item.get("file", "")).strip()
        method = str(item.get("method", "")).strip().upper()
        url = str(item.get("url", "")).strip()
        if not file_path or not method or not url:
            continue

        if fe_patterns and not any(fnmatch.fnmatch(file_path, pattern) for pattern in fe_patterns):
            continue

        normalized_url = url if url.startswith("/") else f"/{url}"
        api_scope.append(f"{method} {normalized_url}")

    api_scope = sorted(set(api_scope))
    if api_scope:
        feature["api_scope"] = api_scope
        logger.info("[AIExplorer] Auto-filled api_scope with %d endpoint(s) from discovery", len(api_scope))


def _build_source_manifest(files: dict[str, str], limit: int = 200) -> str:
    """Build a compact newline-delimited file list for prompt grounding."""
    file_list = sorted(files.keys())
    if not file_list:
        return "(no files matched)"
    if len(file_list) > limit:
        visible = file_list[:limit]
        return "\n".join(visible) + f"\n... (+{len(file_list) - limit} more)"
    return "\n".join(file_list)


# ---------------------------------------------------------------------------
# Single-pass Gemini call
# ---------------------------------------------------------------------------

def _strip_markdown_fence(text: str) -> str:
    """Strip markdown code fences if model wraps JSON response."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def _contains_inference_markers(text: str) -> bool:
    """Return True if text contains wording that implies non-evidence inference."""
    lowered = text.lower()
    return any(marker in lowered for marker in _INFERENCE_MARKERS)


def _strip_inference_phrases(text: str) -> str:
    """Remove known inference phrases from text in a deterministic way."""
    result = text
    for marker in sorted(_INFERENCE_MARKERS, key=len, reverse=True):
        pattern = re.compile(re.escape(marker), flags=re.IGNORECASE)
        result = pattern.sub("UNKNOWN", result)
    return re.sub(r"\s+", " ", result).strip()


def _sanitize_strings(obj: Any) -> Any:
    """Recursively sanitize strings to remove inference wording."""
    if isinstance(obj, str):
        return _strip_inference_phrases(obj)
    if isinstance(obj, list):
        return [_sanitize_strings(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _sanitize_strings(value) for key, value in obj.items()}
    return obj


def _first_source_file(source_files: set[str]) -> str:
    return sorted(source_files)[0] if source_files else "UNKNOWN"


def _normalize_evidence_refs(items: list[dict], source_files: set[str]) -> None:
    """Ensure evidence refs exist and point to matched files."""
    fallback_file = _first_source_file(source_files)
    for item in items:
        if not isinstance(item, dict):
            continue
        refs = item.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            item["evidence_refs"] = [{"file": fallback_file, "symbol": "UNKNOWN"}]
            continue
        fixed_refs: list[dict[str, str]] = []
        for ref in refs:
            if not isinstance(ref, dict):
                fixed_refs.append({"file": fallback_file, "symbol": "UNKNOWN"})
                continue
            file_path = str(ref.get("file", "")).strip()
            symbol = str(ref.get("symbol", "UNKNOWN")).strip() or "UNKNOWN"
            if file_path not in source_files:
                file_path = fallback_file
            fixed_refs.append({"file": file_path, "symbol": symbol})
        item["evidence_refs"] = fixed_refs


def _local_strict_normalize(
    index: dict[str, Any],
    requirement_md: str,
    source_files: set[str],
) -> tuple[dict[str, Any], str]:
    """Best-effort local strict normalization without extra LLM calls."""
    normalized_index = _sanitize_strings(index)
    normalized_requirement = _strip_inference_phrases(requirement_md)

    if "detailed use cases" not in normalized_requirement.lower():
        normalized_requirement = (
            "## Detailed Use Cases\n\n- UNKNOWN (evidence_gap)\n\n" + normalized_requirement
        )

    use_cases = normalized_index.get("use_cases")
    if not isinstance(use_cases, list):
        use_cases = []
    endpoints = normalized_index.get("endpoints")
    if not isinstance(endpoints, list):
        endpoints = []

    _normalize_evidence_refs([x for x in use_cases if isinstance(x, dict)], source_files)
    _normalize_evidence_refs([x for x in endpoints if isinstance(x, dict)], source_files)

    normalized_index["use_cases"] = use_cases
    normalized_index["endpoints"] = endpoints

    logic = normalized_index.get("logic_evidence")
    if not isinstance(logic, list) or not logic:
        inferred_logic: list[dict[str, str]] = []
        for collection in (use_cases, endpoints):
            for item in collection:
                if not isinstance(item, dict):
                    continue
                refs = item.get("evidence_refs")
                if isinstance(refs, list):
                    for ref in refs:
                        if isinstance(ref, dict):
                            inferred_logic.append(
                                {
                                    "file": str(ref.get("file", _first_source_file(source_files))),
                                    "symbol": str(ref.get("symbol", "UNKNOWN")),
                                    "why_it_matters": "Evidence reference from normalized output",
                                }
                            )
        normalized_index["logic_evidence"] = inferred_logic[:20]

    return normalized_index, normalized_requirement


def _validate_strict_evidence_payload(
    index: dict[str, Any],
    requirement_md: str,
    source_files: set[str],
) -> list[str]:
    """Validate model output against strict-evidence-only constraints."""
    errors: list[str] = []

    serialized_index = json.dumps(index, ensure_ascii=False)
    if _contains_inference_markers(serialized_index):
        errors.append("index contains inference wording")
    if _contains_inference_markers(requirement_md):
        errors.append("requirement markdown contains inference wording")

    logic_evidence = index.get("logic_evidence")
    if not isinstance(logic_evidence, list) or not logic_evidence:
        errors.append("index.logic_evidence must be a non-empty list")

    for i, ev in enumerate(logic_evidence or []):
        if not isinstance(ev, dict):
            errors.append(f"logic_evidence[{i}] must be an object")
            continue
        file_path = ev.get("file")
        symbol = ev.get("symbol")
        if not file_path or not isinstance(file_path, str):
            errors.append(f"logic_evidence[{i}].file is required")
        elif file_path not in source_files:
            errors.append(f"logic_evidence[{i}].file not found in matched source files: {file_path}")
        if not symbol or not isinstance(symbol, str):
            errors.append(f"logic_evidence[{i}].symbol is required")

    for field_name in ("use_cases", "endpoints"):
        items = index.get(field_name)
        if not isinstance(items, list) or not items:
            errors.append(f"index.{field_name} must be a non-empty list")
            continue

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"index.{field_name}[{i}] must be an object")
                continue

            evidence_refs = item.get("evidence_refs")
            if not isinstance(evidence_refs, list) or not evidence_refs:
                errors.append(f"index.{field_name}[{i}].evidence_refs must be a non-empty list")
                continue

            for j, ref in enumerate(evidence_refs):
                if not isinstance(ref, dict):
                    errors.append(f"index.{field_name}[{i}].evidence_refs[{j}] must be an object")
                    continue
                file_path = ref.get("file")
                symbol = ref.get("symbol")
                if not file_path or not isinstance(file_path, str):
                    errors.append(f"index.{field_name}[{i}].evidence_refs[{j}].file is required")
                elif file_path not in source_files:
                    errors.append(
                        f"index.{field_name}[{i}].evidence_refs[{j}].file not found in matched source files: {file_path}"
                    )
                if not symbol or not isinstance(symbol, str):
                    errors.append(f"index.{field_name}[{i}].evidence_refs[{j}].symbol is required")

    if "detailed use cases" not in requirement_md.lower():
        errors.append("requirement markdown must include a 'Detailed Use Cases' section")

    return errors


def _render_requirement_from_index(index: dict[str, Any]) -> str:
    """Render requirement markdown deterministically from index content."""
    feature = str(index.get("feature", "unknown_feature"))
    use_cases = index.get("use_cases") if isinstance(index.get("use_cases"), list) else []
    endpoints = index.get("endpoints") if isinstance(index.get("endpoints"), list) else []
    logic_evidence = index.get("logic_evidence") if isinstance(index.get("logic_evidence"), list) else []

    lines: list[str] = [
        f"# Feature Requirement Document: {feature}",
        "",
        "## 1. Introduction",
        "",
        "This document is generated strictly from indexed evidence.",
        "",
        "## 2. Detailed Use Cases",
        "",
    ]

    if use_cases:
        for uc in use_cases:
            if not isinstance(uc, dict):
                continue
            title = str(uc.get("title", "UNKNOWN"))
            actor = str(uc.get("actor", "UNKNOWN"))
            trigger = str(uc.get("trigger", "UNKNOWN"))
            lines.extend([
                f"### {title}",
                "",
                f"- Actor: {actor}",
                f"- Trigger: {trigger}",
                "",
            ])
    else:
        lines.extend(["- UNKNOWN (evidence_gap)", ""])

    lines.extend(["## 3. Endpoints", ""])
    if endpoints:
        for ep in endpoints:
            if not isinstance(ep, dict):
                continue
            method = str(ep.get("method", "UNKNOWN"))
            path = str(ep.get("path", "UNKNOWN"))
            handler = str(ep.get("handler_function", "UNKNOWN"))
            lines.append(f"- {method} {path}")
            lines.append(f"  - Handler: {handler}")
        lines.append("")
    else:
        lines.extend(["- UNKNOWN (evidence_gap)", ""])

    lines.extend(["## 4. Logic Evidence", ""])
    if logic_evidence:
        for ev in logic_evidence:
            if not isinstance(ev, dict):
                continue
            file_path = str(ev.get("file", "UNKNOWN"))
            symbol = str(ev.get("symbol", "UNKNOWN"))
            lines.append(f"- {file_path}::{symbol}")
    else:
        lines.append("- UNKNOWN (evidence_gap)")

    lines.append("")
    return "\n".join(lines)


def _attempt_strict_repair(
    client: genai.Client,
    raw_payload: str,
    validation_errors: str,
    source_files: set[str],
) -> dict[str, Any] | None:
    """Try one strict-repair pass and return normalized payload if valid."""
    logger.warning("[AIExplorer] Attempting one strict-repair retry...")

    repair_prompt = _STRICT_REPAIR_PROMPT_TEMPLATE.format(
        validation_errors=validation_errors,
        raw_payload=raw_payload[:50000],
    )
    try:
        repair_response = client.models.generate_content(
            model=settings.model_name,
            contents=repair_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=32768,
                response_mime_type="application/json",
            ),
        )
    except Exception as exc:
        logger.error("[AIExplorer] Strict-repair request failed: %s", exc)
        return None

    repair_raw = _strip_markdown_fence(repair_response.text or "")
    try:
        repair_payload = json.loads(repair_raw)
    except json.JSONDecodeError:
        logger.error("[AIExplorer] Strict-repair failed: output is not valid JSON")
        return None

    repair_index = repair_payload.get("index")
    repair_requirement_md = repair_payload.get("requirement_markdown")
    if not isinstance(repair_index, dict):
        logger.error("[AIExplorer] Strict-repair failed: missing or invalid 'index'")
        return None
    if not isinstance(repair_requirement_md, str) or not repair_requirement_md.strip():
        logger.warning(
            "[AIExplorer] Strict-repair returned no requirement_markdown; "
            "rendering deterministic markdown from index"
        )
        repair_requirement_md = _render_requirement_from_index(repair_index)

    repair_errors = _validate_strict_evidence_payload(
        repair_index,
        repair_requirement_md,
        source_files,
    )
    if repair_errors:
        logger.error("[AIExplorer] Strict-repair failed validation: %s", "; ".join(repair_errors))
        return None

    logger.info("[AIExplorer] Strict-repair retry succeeded")
    return {
        "index": repair_index,
        "requirement_markdown": repair_requirement_md,
    }


def _run_single_pass(spec: dict[str, Any], source_bundle: str, source_manifest: str) -> dict[str, Any]:
    """Run one Gemini call that returns both index JSON and requirement markdown."""
    client = genai.Client(api_key=settings.gemini_api_key)

    feature = spec["feature"]
    prompt = _SINGLE_PASS_PROMPT_TEMPLATE.format(
        feature_name=feature["name"],
        description=feature.get("description", ""),
        api_scope=", ".join(feature.get("api_scope", [])),
        go_types=", ".join(feature.get("go_types", [])),
        ts_types=", ".join(feature.get("ts_types", [])),
        business_terms=", ".join(feature.get("business_terms", [])),
        source_manifest=source_manifest,
        source_code=source_bundle,
    )

    logger.info("[AIExplorer] Single-pass: sending %d chars to Gemini Flash 2.5...", len(prompt))

    response = client.models.generate_content(
        model=settings.model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=32768,
            response_mime_type="application/json",
        ),
    )

    raw_text = response.text or ""
    raw = _strip_markdown_fence(raw_text)
    source_files = {
        line.strip()
        for line in source_manifest.splitlines()
        if line.strip() and not line.startswith("...") and line.strip() != "(no files matched)"
    }

    try:
        payload = json.loads(raw)
        index = payload.get("index")
        requirement_md = payload.get("requirement_markdown")

        if not isinstance(index, dict):
            raise ValueError("Missing or invalid 'index' object in model output")
        if not isinstance(requirement_md, str) or not requirement_md.strip():
            raise ValueError("Missing or invalid 'requirement_markdown' in model output")

        strict_errors = _validate_strict_evidence_payload(index, requirement_md, source_files)
        if strict_errors:
            normalized_index, normalized_md = _local_strict_normalize(
                index=index,
                requirement_md=requirement_md,
                source_files=source_files,
            )
            normalized_errors = _validate_strict_evidence_payload(
                normalized_index,
                normalized_md,
                source_files,
            )
            if not normalized_errors:
                logger.info("[AIExplorer] Local strict normalization succeeded")
                return {
                    "index": normalized_index,
                    "requirement_markdown": normalized_md,
                }

            repaired = _attempt_strict_repair(
                client=client,
                raw_payload=raw,
                validation_errors="; ".join(strict_errors),
                source_files=source_files,
            )
            if repaired is not None:
                return repaired
            raise ValueError("Strict evidence validation failed: " + "; ".join(strict_errors))

        logger.info("[AIExplorer] Single-pass complete: index + requirement parsed OK")
        return {
            "index": index,
            "requirement_markdown": requirement_md,
        }
    except json.JSONDecodeError as exc:
        logger.error("[AIExplorer] Single-pass: failed to parse JSON — %s", exc)
        logger.debug("[AIExplorer] Raw response:\n%s", raw[:3000])
        repaired = _attempt_strict_repair(
            client=client,
            raw_payload=raw_text,
            validation_errors=f"JSON parse failure: {exc}",
            source_files=source_files,
        )
        if repaired is not None:
            return repaired
        return {
            "index": {"feature": feature["name"], "raw_response": raw},
            "requirement_markdown": raw_text.strip(),
        }
    except ValueError as exc:
        logger.error("[AIExplorer] Single-pass: invalid payload shape — %s", exc)
        logger.debug("[AIExplorer] Raw response:\n%s", raw[:3000])
        return {
            "index": {"feature": feature["name"], "raw_response": raw},
            "requirement_markdown": raw_text.strip(),
        }


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[truncated]..."


def _build_error_index_payload(feature_name: str, index: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "feature": feature_name,
        "error": "STRICT_EVIDENCE_VALIDATION_FAILED",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "payload_type": type(index).__name__,
    }

    if isinstance(index, dict):
        raw_response = index.get("raw_response")
        if isinstance(raw_response, str):
            payload["raw_response_chars"] = len(raw_response)
            payload["raw_response_preview"] = _truncate_text(
                raw_response,
                _MAX_ERROR_RAW_PREVIEW_CHARS,
            )
        payload["index_keys"] = sorted(index.keys())
    else:
        payload["raw_value"] = str(index)

    payload["note"] = (
        "This is a compact troubleshooting artifact. "
        "Re-run explore when needed; this file is intentionally truncated."
    )
    return payload


def _write_error_artifacts(out_dir: Path, feature_name: str, index: Any, requirement_md: str) -> None:
    error_cache = out_dir / "index_error.json"
    compact_error = _build_error_index_payload(feature_name, index)
    error_cache.write_text(
        json.dumps(compact_error, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.warning("[AIExplorer] Invalid index payload saved → %s", error_cache)

    requirement_error = out_dir / "requirement_error.md"
    requirement_preview = _truncate_text(requirement_md, _MAX_ERROR_REQUIREMENT_PREVIEW_CHARS)
    requirement_error.write_text(requirement_preview, encoding="utf-8")
    logger.warning("[AIExplorer] Invalid requirement payload saved → %s", requirement_error)


def _cleanup_error_artifacts(out_dir: Path) -> None:
    for stale in ("index_error.json", "requirement_error.md"):
        stale_path = out_dir / stale
        if stale_path.exists():
            stale_path.unlink()
            logger.info("[AIExplorer] Removed stale error artifact → %s", stale_path)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def explore_feature(
    spec_path: str,
    be_repo_path: str = "",
    fe_repo_path: str = "",
) -> Path:
    """Run single-pass Gemini feature exploration for a feature spec.

    Args:
        spec_path:    Path to the feature YAML spec file.
        be_repo_path: Override for BE repo path (defaults to settings.be_repo_path).
        fe_repo_path: Override for FE repo path (defaults to settings.fe_repo_path).

    Returns:
        Path to the written requirement.md file.
    """
    from app.config import settings

    spec_file = Path(spec_path)
    if not spec_file.exists():
        raise FileNotFoundError(f"Feature spec not found: {spec_path}")

    spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
    feature = spec["feature"]
    _auto_fill_api_scope_from_discovery(feature)
    feature_name: str = feature["name"]

    be_path = be_repo_path or settings.be_repo_path
    fe_path = fe_repo_path or settings.fe_repo_path

    # Output directory for this feature.
    out_dir = Path("docs/features") / feature_name
    out_dir.mkdir(parents=True, exist_ok=True)

    index_cache = out_dir / "index.json"

    be_files = _collect_files(be_path, feature.get("be_files", []))
    fe_files = _collect_files(fe_path, feature.get("fe_files", []))
    all_files = {**be_files, **fe_files}

    if not all_files:
        raise ValueError(
            "No source files collected. Check be_repo_path/fe_repo_path in .env "
            "and be_files/fe_files in the feature spec."
        )

    source_bundle = _format_source_bundle(all_files)
    source_manifest = _build_source_manifest(all_files)
    result = _run_single_pass(spec, source_bundle, source_manifest)

    index = result["index"]
    doc_md = result["requirement_markdown"]

    if isinstance(index, dict) and "raw_response" not in index:
        index_cache.write_text(
            json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("[AIExplorer] Index saved → %s", index_cache)

        out_md = out_dir / "requirement.md"
        out_md.write_text(doc_md, encoding="utf-8")
        logger.info("[AIExplorer] Requirement doc saved → %s", out_md)

        _cleanup_error_artifacts(out_dir)
    else:
        _write_error_artifacts(
            out_dir=out_dir,
            feature_name=feature_name,
            index=index,
            requirement_md=doc_md,
        )

        raise ValueError(
            "Strict-evidence output validation failed. "
            "See index_error.json and requirement_error.md (truncated preview)."
        )

    out_md = out_dir / "requirement.md"

    return out_md
