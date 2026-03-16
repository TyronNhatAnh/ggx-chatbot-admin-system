"""Backward-compatible re-export — real implementation moved to indexer.parsers.go."""
# ruff: noqa: F401
from indexer.parsers.go.flow_extractor import (  # noqa: F401
    extract_flows_from_file,
    extract_flows_from_repo,
)
