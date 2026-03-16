"""Backward-compatible re-export — real implementation moved to indexer.parsers.go."""
# ruff: noqa: F401
from indexer.parsers.go.type_extractor import (  # noqa: F401
    extract_structs_from_file,
    extract_structs_from_repo,
)
