# Thin re-export — prompt content now lives in app/prompts/ (.md files).
# All assembly logic is in app/prompts/builder.py.
from app.prompts.builder import build_system_prompt

__all__ = ["build_system_prompt"]
