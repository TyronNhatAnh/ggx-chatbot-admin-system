"""Go LanguageParser implementation — delegates to the existing extractors."""

from __future__ import annotations

from indexer.models import CodeChunk, EnumGroup, ServiceFlow, StructDefinition
from indexer.parsers.base import LanguageParser
from indexer.parsers.go.enum_extractor import extract_enums_from_repo
from indexer.parsers.go.flow_extractor import (
    extract_flows_from_repo,
    extract_handler_chunks_from_repo,
)
from indexer.parsers.go.type_extractor import extract_structs_from_repo


class GoParser(LanguageParser):
    """Parser for Go backend services (Gin handlers, DI patterns)."""

    @property
    def language(self) -> str:
        return "go"

    @property
    def file_extensions(self) -> tuple[str, ...]:
        return (".go",)

    @property
    def ignore_file_patterns(self) -> tuple[str, ...]:
        return ("_test.go", ".pb.go")

    def extract_enums(self, repo_path: str, service: str) -> list[EnumGroup]:
        return extract_enums_from_repo(repo_path, service)

    def extract_types(self, repo_path: str, service: str) -> list[StructDefinition]:
        return extract_structs_from_repo(repo_path, service)

    def extract_flows(self, repo_path: str, service: str) -> list[ServiceFlow]:
        return extract_flows_from_repo(repo_path, service)

    def extract_handler_chunks(self, repo_path: str, service: str) -> list[CodeChunk]:
        """Extract handler source-code chunks (Go handler bodies)."""
        return extract_handler_chunks_from_repo(repo_path, service)
