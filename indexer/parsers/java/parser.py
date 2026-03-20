"""Java LanguageParser implementation — delegates to specialised extractors.

Supports Java 8 Spring Boot codebases including:
  - REST controllers (@RestController, @RequestMapping)
  - Internal services without REST (@Service, @Component)
  - Scheduled tasks (@Scheduled)
  - MyBatis mappers (@Mapper)
  - Lombok DTOs (@Data, @Value, @Builder)
  - JPA entities (@Entity, @Table)

Designed to work well for web-admin services that do NOT expose
public REST APIs — indexes internal service flows, DI graphs,
enum constants, and DTOs regardless of HTTP exposure.
"""

from __future__ import annotations

from indexer.models import CodeChunk, Edge, EnumGroup, ServiceFlow, StructDefinition
from indexer.parsers.base import LanguageParser
from indexer.parsers.java.enum_extractor import extract_enums_from_repo
from indexer.parsers.java.flow_extractor import (
    extract_flows_from_repo,
    extract_handler_chunks_from_repo,
)
from indexer.parsers.java.type_extractor import extract_types_from_repo


class JavaParser(LanguageParser):
    """Parser for Java 8 Spring Boot services."""

    @property
    def language(self) -> str:
        return "java"

    @property
    def file_extensions(self) -> tuple[str, ...]:
        return (".java",)

    @property
    def ignore_dirs(self) -> frozenset[str]:
        return frozenset({
            ".git", "target", "build", ".gradle", ".idea", ".mvn",
            "test", "tests", "node_modules", "__pycache__", "dist",
            "generated-sources", "generated-test-sources",
        })

    @property
    def ignore_file_patterns(self) -> tuple[str, ...]:
        return ("Test.java", "Tests.java", "IT.java", "package-info.java")

    def extract_enums(self, repo_path: str, service: str) -> list[EnumGroup]:
        return extract_enums_from_repo(repo_path, service)

    def extract_types(self, repo_path: str, service: str) -> list[StructDefinition]:
        return extract_types_from_repo(repo_path, service)

    def extract_flows(self, repo_path: str, service: str) -> list[ServiceFlow]:
        return extract_flows_from_repo(repo_path, service)

    def extract_handler_chunks(self, repo_path: str, service: str) -> list[CodeChunk]:
        """Extract method source-code chunks (controller + service methods)."""
        return extract_handler_chunks_from_repo(repo_path, service)

    def extract_edges(self, repo_path: str, service: str) -> list[Edge]:
        """Generate Java-specific graph edges.

        Beyond the standard flow-derived edges (defines, handles, calls,
        delegates_to), this adds:
          - 'injects' edges: class → injected dependency (Spring DI)
          - 'implements' / 'extends' edges from type definitions
        """
        edges: list[Edge] = []
        seen: set[str] = set()

        def _add(edge: Edge) -> None:
            key = f"{edge.from_name}|{edge.edge_type}|{edge.to_name}"
            if key not in seen:
                seen.add(key)
                edges.append(edge)

        # Edges from type hierarchy (extends / implements)
        types = extract_types_from_repo(repo_path, service)
        for t in types:
            for parent in t.embedded_types:
                edge_type = "extends" if t.embedded_types.index(parent) == 0 else "implements"
                _add(Edge(
                    from_type="class", from_name=f"{service}.{t.name}",
                    from_service=service, edge_type=edge_type,
                    to_type="class", to_name=parent,
                    to_service=service, file=t.file,
                ))

        # Edges from DI injection (class → dependency via @Autowired)
        import re
        from pathlib import Path

        _AUTOWIRED_RE = re.compile(
            r"@(?:Autowired|Resource|Inject)\s+"
            r"(?:private|protected)?\s*"
            r"([\w<>]+)\s+(\w+)\s*;",
        )
        _FINAL_FIELD_RE = re.compile(
            r"(?:private|protected)\s+final\s+"
            r"([\w<>]+)\s+(\w+)\s*;",
        )
        _CLASS_DEF_RE = re.compile(
            r"(?:public\s+)?(?:abstract\s+)?(?:class|interface)\s+(\w+)",
        )
        _SERVICE_SUFFIXES = ("Service", "Svc", "Client", "Gateway", "Provider",
                             "Facade", "Manager", "Repository", "Repo", "Mapper",
                             "Dao", "DAO", "Store", "Cache")

        root = Path(repo_path).resolve()
        ignore_dirs = self.ignore_dirs

        for java_file in root.rglob("*.java"):
            if any(part in ignore_dirs for part in java_file.parts):
                continue
            if any(java_file.name.endswith(pat) for pat in self.ignore_file_patterns):
                continue

            try:
                content = java_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            rel_path = str(java_file.relative_to(root))
            cm = _CLASS_DEF_RE.search(content)
            if not cm:
                continue
            class_name = cm.group(1)

            # @Autowired fields
            for m in _AUTOWIRED_RE.finditer(content):
                dep_type, dep_name = m.group(1), m.group(2)
                _add(Edge(
                    from_type="class", from_name=f"{service}.{class_name}",
                    from_service=service, edge_type="injects",
                    to_type="class", to_name=dep_type,
                    to_service=service, file=rel_path,
                    metadata={"field_name": dep_name},
                ))

            # private final fields that look like DI
            for m in _FINAL_FIELD_RE.finditer(content):
                dep_type, dep_name = m.group(1), m.group(2)
                if any(dep_type.endswith(s) for s in _SERVICE_SUFFIXES):
                    _add(Edge(
                        from_type="class", from_name=f"{service}.{class_name}",
                        from_service=service, edge_type="injects",
                        to_type="class", to_name=dep_type,
                        to_service=service, file=rel_path,
                        metadata={"field_name": dep_name, "injection": "constructor"},
                    ))

        return edges
