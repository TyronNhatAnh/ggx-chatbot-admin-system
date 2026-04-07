"""Check which Gemini models are available on the configured Vertex AI project.

Usage:
    python scripts/check_models.py
    python scripts/check_models.py --filter flash
    python scripts/check_models.py --filter gemini-3

Reads credentials from the same .env / vertex-ai.json as the main app.
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.config import settings
from app.llm.vertex_credentials import create_vertex_client


def main() -> None:
    parser = argparse.ArgumentParser(description="List available Vertex AI Gemini models")
    parser.add_argument(
        "--filter", "-f",
        default="",
        help="Case-insensitive substring to filter model names (e.g. 'flash', 'pro')",
    )
    args = parser.parse_args()

    print(f"Credentials file : {settings.vertex_ai_credentials_file}")
    print(f"SA key           : {settings.vertex_ai_sa_key}")
    print(f"Location         : {settings.vertex_ai_location}")
    print(f"Configured Flash : {settings.model_name}")
    print(f"Configured Pro   : {settings.pro_model_name or '(not set)'}")
    print()

    client = create_vertex_client()

    models = list(client.models.list())
    if args.filter:
        models = [m for m in models if args.filter.lower() in (m.name or "").lower()]

    if not models:
        print("No models found" + (f" matching '{args.filter}'" if args.filter else "") + ".")
        return

    print(f"{'Model name':<55}  {'Display name'}")
    print("-" * 90)
    for m in sorted(models, key=lambda x: x.name or ""):
        name = m.name or ""
        display = getattr(m, "display_name", "") or ""
        marker = ""
        if name == settings.model_name or name.endswith(f"/{settings.model_name}"):
            marker = "  ← FLASH"
        elif settings.pro_model_name and (
            name == settings.pro_model_name or name.endswith(f"/{settings.pro_model_name}")
        ):
            marker = "  ← PRO"
        print(f"{name:<55}  {display}{marker}")

    print()
    _probe_configured_models(client)


def _probe_configured_models(client) -> None:
    """Send a minimal generate call to each configured model to confirm it's reachable."""
    from google.genai import types

    models_to_check = [
        ("Flash", settings.model_name),
    ]
    if settings.pro_model_name:
        models_to_check.append(("Pro", settings.pro_model_name))

    print("Probing configured models with a minimal request...")
    print()
    for label, model_name in models_to_check:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents="Reply with the single word OK.",
                config=types.GenerateContentConfig(max_output_tokens=8),
            )
            text = (resp.text or "").strip()
            status = f"OK  — response: {text!r}"
        except Exception as exc:  # noqa: BLE001
            status = f"FAILED — {type(exc).__name__}: {exc}"
        print(f"  [{label:5}] {model_name}")
        print(f"          {status}")
    print()


if __name__ == "__main__":
    main()
