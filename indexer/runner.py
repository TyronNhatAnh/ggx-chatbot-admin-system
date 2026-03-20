"""Index runner — orchestrates the full background indexing pipeline.

This is the entry point for indexing backend/frontend services across
multiple languages (Go, Java, React/TS, Ruby, …).  Each language has
its own parser under `indexer.parsers.<lang>/` implementing the shared
LanguageParser interface.

Usage:
    python -m indexer.runner --repo /path/to/order-service --service order-service
    python -m indexer.runner --repo /path/to/order-service --service order-service --lang go
    python -m indexer.runner --repo /path/to/web2 --service web2 --lang react
    python -m indexer.runner --config indexer.yaml
"""

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path

from indexer.models import CodeChunk, Edge
from indexer.parsers import detect_language, get_parser, list_languages
from indexer.store import KnowledgeStore, get_knowledge_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _build_code_chunks_from_enums(enums, service: str) -> list[CodeChunk]:
    """Convert enum groups into searchable code chunks."""
    chunks = []
    seen_names: dict[str, int] = {}
    for eg in enums:
        values_text = "\n".join(
            f"  {v.name} = {v.value}  // {v.comment}" if v.comment
            else f"  {v.name} = {v.value}"
            for v in eg.values
        )
        content = f"// Enum: {eg.name} (type: {eg.type_name})\n{values_text}"
        # Ensure unique qualified names (multiple unnamed enums per file)
        base_name = f"{service}.{eg.name}"
        count = seen_names.get(base_name, 0)
        seen_names[base_name] = count + 1
        qname = base_name if count == 0 else f"{base_name}.{count}"
        chunks.append(CodeChunk(
            qualified_name=qname,
            content=content,
            chunk_type="enum",
            file=eg.file,
            service=service,
        ))
    return chunks


def _build_code_chunks_from_flows(flows, service: str) -> list[CodeChunk]:
    """Convert service flows into searchable code chunks."""
    chunks = []
    seen_names: dict[str, int] = {}
    for flow in flows:
        svc_text = ", ".join(
            f"{c.receiver}.{c.method}()" for c in flow.service_calls
        ) or "none"
        repo_text = ", ".join(
            f"{c.receiver}.{c.method}()" for c in flow.repository_calls
        ) or "none"
        content = (
            f"Handler: {flow.handler_name}\n"
            f"File: {flow.handler_file}\n"
            f"Service calls: {svc_text}\n"
            f"Repository calls: {repo_text}"
        )
        base_name = f"{service}.{flow.handler_name}"
        count = seen_names.get(base_name, 0)
        seen_names[base_name] = count + 1
        qname = base_name if count == 0 else f"{base_name}.{count}"
        chunks.append(CodeChunk(
            qualified_name=qname,
            content=content,
            chunk_type="flow",
            file=flow.handler_file,
            service=service,
        ))
    return chunks


def _build_code_chunks_from_structs(structs, service: str) -> list[CodeChunk]:
    """Convert struct definitions into searchable code chunks."""
    chunks = []
    seen_names: dict[str, int] = {}
    for s in structs:
        fields_text = "\n".join(
            f"  {f.name} {f.type} `json:\"{f.json_tag}\"`" if f.json_tag
            else f"  {f.name} {f.type}"
            for f in s.fields
        )
        content = f"type {s.name} struct {{\n{fields_text}\n}}"
        base_name = f"{service}.{s.name}"
        count = seen_names.get(base_name, 0)
        seen_names[base_name] = count + 1
        qname = base_name if count == 0 else f"{base_name}.{count}"
        chunks.append(CodeChunk(
            qualified_name=qname,
            content=content,
            chunk_type="struct",
            file=s.file,
            service=service,
        ))
    return chunks


def _build_edges_from_flows(flows, service: str) -> list[Edge]:
    """Generate graph edges from extracted service flows.

    Creates:
      - 'defines' edge: file → handler function
      - 'calls' edge: handler → service-layer method
      - 'delegates_to' edge: handler → repository method
      - 'handles' edge: api_endpoint → handler (if endpoint is known)
    """
    edges: list[Edge] = []
    seen: set[str] = set()

    def _add(edge: Edge) -> None:
        key = f"{edge.from_name}|{edge.edge_type}|{edge.to_name}"
        if key not in seen:
            seen.add(key)
            edges.append(edge)

    for flow in flows:
        handler_qn = f"{service}.{flow.handler_name}"

        # file → handler (defines)
        if flow.handler_file:
            _add(Edge(
                from_type="file", from_name=flow.handler_file,
                from_service=service, edge_type="defines",
                to_type="function", to_name=handler_qn,
                to_service=service, file=flow.handler_file,
            ))

        # endpoint → handler (handles)
        if flow.endpoint:
            _add(Edge(
                from_type="api_endpoint", from_name=flow.endpoint,
                from_service=service, edge_type="handles",
                to_type="function", to_name=handler_qn,
                to_service=service, file=flow.handler_file,
            ))

        # handler → service calls
        for call in flow.service_calls:
            callee = f"{call.receiver}.{call.method}"
            _add(Edge(
                from_type="function", from_name=handler_qn,
                from_service=service, edge_type="calls",
                to_type="method", to_name=callee,
                to_service=service, file=call.file or flow.handler_file,
            ))

        # handler → repository calls
        for call in flow.repository_calls:
            callee = f"{call.receiver}.{call.method}"
            _add(Edge(
                from_type="function", from_name=handler_qn,
                from_service=service, edge_type="delegates_to",
                to_type="method", to_name=callee,
                to_service=service, file=call.file or flow.handler_file,
            ))

    return edges


def index_service(repo_path: str, service: str,
                  store: KnowledgeStore | None = None,
                  enable_vectors: bool = False,
                  lang: str | None = None) -> dict:
    """Run the full indexing pipeline for a single service.

    Args:
        repo_path: Path to the repository root.
        service: Human-readable service name (e.g. "order-service", "web2").
        store: KnowledgeStore instance (uses singleton if None).
        enable_vectors: Whether to generate vector embeddings (requires extra deps).
        lang: Language key ('go', 'java', 'react', 'ruby').
              Auto-detected from repo contents if omitted.

    Returns:
        Summary dict with counts of extracted entities.
    """
    t0 = time.perf_counter()
    store = store or get_knowledge_store()

    # Resolve language parser
    if lang is None:
        lang = detect_language(repo_path)
        if lang is None:
            logger.error("Could not auto-detect language for %s", repo_path)
            sys.exit(1)
    parser = get_parser(lang)

    logger.info("=" * 60)
    logger.info("Indexing service: %s  repo: %s  lang: %s", service, repo_path, lang)
    logger.info("=" * 60)

    # Clear previous data for this service (incremental = per-service granularity)
    store.clear_service(service)

    # ----- Pass 1: Extract enums -----
    logger.info("Pass 1/4: Extracting enums...")
    enums = parser.extract_enums(repo_path, service)
    enum_count = store.store_enums(enums)
    logger.info("  → Stored %d enum groups", enum_count)

    # ----- Pass 2: Extract type definitions -----
    logger.info("Pass 2/4: Extracting type definitions...")
    structs = parser.extract_types(repo_path, service)
    struct_count = store.store_structs(structs)
    logger.info("  → Stored %d type definitions", struct_count)

    # ----- Pass 3: Extract service flows -----
    logger.info("Pass 3/4: Extracting service flows...")
    flows = parser.extract_flows(repo_path, service)
    flow_count = store.store_flows(flows)
    logger.info("  → Stored %d service flows", flow_count)

    # ----- Pass 4: Build graph edges -----
    logger.info("Pass 4/4: Building graph edges...")
    edges = _build_edges_from_flows(flows, service)
    # Merge parser-specific edges (e.g. React: calls_api, routes_to, dispatches)
    parser_edges = parser.extract_edges(repo_path, service)
    if parser_edges:
        # Deduplicate against flow-generated edges
        existing_keys = {f"{e.from_name}|{e.edge_type}|{e.to_name}" for e in edges}
        for pe in parser_edges:
            key = f"{pe.from_name}|{pe.edge_type}|{pe.to_name}"
            if key not in existing_keys:
                existing_keys.add(key)
                edges.append(pe)
        logger.info("  → Parser contributed %d additional edges", len(parser_edges))
    edge_count = store.store_edges(edges)
    logger.info("  → Stored %d graph edges total", edge_count)

    # ----- Build code chunks for full-text + vector search -----
    chunks = (
        _build_code_chunks_from_enums(enums, service)
        + _build_code_chunks_from_structs(structs, service)
        + _build_code_chunks_from_flows(flows, service)
    )
    # GoParser also extracts handler source-code chunks (actual Go bodies)
    if hasattr(parser, "extract_handler_chunks"):
        handler_chunks = parser.extract_handler_chunks(repo_path, service)
        chunks.extend(handler_chunks)
        logger.info("  → Extracted %d handler source-code chunks", len(handler_chunks))
    chunk_count = store.store_code_chunks(chunks)
    logger.info("  → Stored %d searchable code chunks", chunk_count)

    # ----- Optional: Vector embeddings -----
    vector_count = 0
    if enable_vectors:
        try:
            from indexer.vector_store import get_vector_store
            vs = get_vector_store()
            if vs:
                vs.clear_service(service)
                vector_count = vs.index_chunks(chunks)
                logger.info("  → Generated %d vector embeddings", vector_count)
        except Exception as e:
            logger.warning("  → Vector indexing failed: %s", e)

    # Write accumulated JSON sidecars (all services, from SQLite) for debugging
    store.export_json_sidecars()

    elapsed = time.perf_counter() - t0
    summary = {
        "service": service,
        "repo_path": repo_path,
        "enums": enum_count,
        "structs": struct_count,
        "flows": flow_count,
        "edges": edge_count,
        "code_chunks": chunk_count,
        "vector_embeddings": vector_count,
        "elapsed_seconds": round(elapsed, 2),
    }
    logger.info("Indexing complete: %s", json.dumps(summary))
    return summary


def index_all(services: list[dict], enable_vectors: bool = False,
              link: bool = True) -> list[dict]:
    """Index multiple services sequentially.

    Args:
        services: List of dicts with 'repo_path', 'service', and optional 'lang' keys.
        enable_vectors: Whether to generate vector embeddings.
        link: Whether to run cross-service endpoint linking after indexing.

    Returns:
        List of summary dicts, one per service.
    """
    results = []
    for svc in services:
        result = index_service(
            repo_path=svc["repo_path"],
            service=svc["service"],
            enable_vectors=enable_vectors,
            lang=svc.get("lang"),
        )
        results.append(result)

    # Phase 3: Cross-service endpoint linking
    if link and len(services) > 1:
        try:
            from indexer.linker import link_services
            link_summary = link_services()
            if results:
                results[-1]["cross_service_links"] = link_summary
        except Exception as e:
            logger.warning("Cross-service linking failed: %s", e)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index backend/frontend services for the AI admin assistant."
    )
    parser.add_argument(
        "--repo", required=True,
        help="Path to the repository root.",
    )
    parser.add_argument(
        "--service", required=True,
        help="Service name (e.g. 'order-service', 'web2', 'admin-service').",
    )
    parser.add_argument(
        "--lang", default=None,
        choices=list_languages() or None,
        help="Source language (auto-detected if omitted). Available: go, java, react, ruby.",
    )
    parser.add_argument(
        "--vectors", action="store_true",
        help="Enable vector embedding generation (requires chromadb + sentence-transformers).",
    )
    parser.add_argument(
        "--link", action="store_true",
        help="Run cross-service endpoint linking after indexing.",
    )
    args = parser.parse_args()

    if not Path(args.repo).is_dir():
        logger.error("Repository path does not exist: %s", args.repo)
        sys.exit(1)

    summary = index_service(
        repo_path=args.repo,
        service=args.service,
        enable_vectors=args.vectors,
        lang=args.lang,
    )

    if args.link:
        from indexer.linker import link_services
        link_summary = link_services()
        summary["cross_service_links"] = link_summary

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
