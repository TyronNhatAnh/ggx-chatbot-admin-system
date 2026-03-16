"""Backward-compatible re-export — real implementation moved to indexer.parsers.go."""
# ruff: noqa: F401
from indexer.parsers.go.enum_extractor import (  # noqa: F401
    extract_enums_from_file,
    extract_enums_from_repo,
)
