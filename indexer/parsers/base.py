"""Abstract base class for language-specific code parsers.

Each language (Go, Java, React/TS, Ruby, …) implements this interface.
The runner uses it to extract enums, types, and flows uniformly regardless
of the source language.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

from indexer.models import Edge, EnumGroup, ServiceFlow, StructDefinition

logger = logging.getLogger(__name__)


class LanguageParser(ABC):
    """Contract every language parser must satisfy."""

    # ---- identity ----

    @property
    @abstractmethod
    def language(self) -> str:
        """Short key used in CLI and registry, e.g. 'go', 'java', 'react'."""

    @property
    @abstractmethod
    def file_extensions(self) -> tuple[str, ...]:
        """Glob-friendly extensions, e.g. ('.go',) or ('.ts', '.tsx')."""

    # ---- optional overrides ----

    @property
    def ignore_dirs(self) -> frozenset[str]:
        """Directory names to skip during file walking."""
        return frozenset({
            ".git", "vendor", "testdata", "test", "mocks",
            "node_modules", "__pycache__", "dist", "build",
        })

    @property
    def ignore_file_patterns(self) -> tuple[str, ...]:
        """Filename suffixes/patterns to exclude (e.g. '_test.go', '.pb.go')."""
        return ()

    # ---- extraction interface ----

    @abstractmethod
    def extract_enums(self, repo_path: str, service: str) -> list[EnumGroup]:
        """Extract enum / constant definitions from the repository."""

    @abstractmethod
    def extract_types(self, repo_path: str, service: str) -> list[StructDefinition]:
        """Extract type definitions (structs, classes, interfaces, …)."""

    @abstractmethod
    def extract_flows(self, repo_path: str, service: str) -> list[ServiceFlow]:
        """Extract execution flows (handler → service → repository)."""

    def extract_edges(self, repo_path: str, service: str) -> list[Edge]:
        """Extract graph edges (relationships between code entities).

        Default: returns empty list. Override in parsers that produce
        language-specific edges (e.g. React: component → API endpoint).
        """
        return []

    # ---- shared helpers ----

    def iter_source_files(self, repo_path: str) -> Iterator[Path]:
        """Yield source files matching this parser's extensions.

        Respects ignore_dirs and ignore_file_patterns.
        """
        root = Path(repo_path).resolve()
        for ext in self.file_extensions:
            for path in root.rglob(f"*{ext}"):
                if any(part in self.ignore_dirs for part in path.parts):
                    continue
                if any(path.name.endswith(pat) for pat in self.ignore_file_patterns):
                    continue
                yield path
