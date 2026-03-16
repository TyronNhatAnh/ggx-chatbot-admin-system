"""Vector store for semantic code search using ChromaDB.

Embeds code chunks with sentence-transformers (lightweight, no GPU required)
and stores them in a persistent ChromaDB collection for cosine similarity search.

This gives the chatbot the ability to find relevant code by intent/meaning
rather than just keyword matching — e.g., "how is pricing calculated" finds
the EstimateGuest handler even if the user doesn't know the exact function name.

Falls back gracefully if chromadb/sentence-transformers are not installed.
"""

import logging
from pathlib import Path

from indexer.models import CodeChunk

logger = logging.getLogger(__name__)

_DEFAULT_PERSIST_DIR = str(Path(__file__).parents[1] / "data" / "vectordb")
_COLLECTION_NAME = "code_chunks"
_EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 384-dim, fast, good for code search
_MAX_BATCH_SIZE = 100


def _check_deps() -> bool:
    try:
        import chromadb  # noqa: F401
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


class VectorStore:
    """ChromaDB-backed vector store for semantic code search."""

    def __init__(self, persist_dir: str | None = None):
        if not _check_deps():
            raise ImportError(
                "Vector search requires: pip install chromadb sentence-transformers"
            )

        import chromadb

        self._persist_dir = persist_dir or _DEFAULT_PERSIST_DIR
        Path(self._persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = None

    def _get_embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(_EMBEDDING_MODEL)
        return self._embedder

    def index_chunks(self, chunks: list[CodeChunk]) -> int:
        """Embed and store code chunks. Returns count stored."""
        if not chunks:
            return 0

        embedder = self._get_embedder()
        stored = 0

        for i in range(0, len(chunks), _MAX_BATCH_SIZE):
            batch = chunks[i:i + _MAX_BATCH_SIZE]
            texts = [c.content for c in batch]
            ids = [f"{c.chunk_type}.{c.service}.{c.qualified_name}" for c in batch]
            metadatas = [
                {
                    "qualified_name": c.qualified_name,
                    "chunk_type": c.chunk_type,
                    "service": c.service,
                    "file": c.file,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                }
                for c in batch
            ]

            embeddings = embedder.encode(texts, show_progress_bar=False).tolist()

            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            stored += len(batch)

        logger.info("[VectorStore] Indexed %d code chunks", stored)
        return stored

    def search(self, query: str, top_k: int = 5,
               chunk_type: str | None = None,
               service: str | None = None) -> list[dict]:
        """Semantic search. Returns top_k most similar code chunks."""
        embedder = self._get_embedder()
        query_embedding = embedder.encode([query], show_progress_bar=False).tolist()

        where_filter = None
        conditions = []
        if chunk_type:
            conditions.append({"chunk_type": chunk_type})
        if service:
            conditions.append({"service": service})
        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        results = self._collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        output = []
        for idx, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][idx] if results["metadatas"] else {}
            distance = results["distances"][0][idx] if results["distances"] else 0.0
            output.append({
                "id": doc_id,
                "score": round(1.0 - distance, 3),  # cosine similarity
                "qualified_name": meta.get("qualified_name", ""),
                "chunk_type": meta.get("chunk_type", ""),
                "service": meta.get("service", ""),
                "file": meta.get("file", ""),
                "snippet": (results["documents"][0][idx] or "")[:300],
            })

        return output

    def clear_service(self, service: str) -> int:
        """Delete all vectors belonging to a specific service. Returns count deleted."""
        try:
            existing = self._collection.get(
                where={"service": service},
                include=[],
            )
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])
                logger.info("[VectorStore] Cleared %d vectors for service=%s", len(existing["ids"]), service)
                return len(existing["ids"])
        except Exception as e:
            logger.warning("[VectorStore] clear_service failed: %s", e)
        return 0

    def clear(self) -> None:
        """Delete all vectors from the collection."""
        self._client.delete_collection(_COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return self._collection.count()


# ---------------------------------------------------------------------------
# Safe accessor (returns None if deps not installed)
# ---------------------------------------------------------------------------

_store: VectorStore | None = None


def get_vector_store() -> VectorStore | None:
    """Get the singleton VectorStore, or None if dependencies are missing."""
    global _store
    if _store is not None:
        return _store
    if not _check_deps():
        logger.info("[VectorStore] chromadb/sentence-transformers not installed — vector search disabled")
        return None
    _store = VectorStore()
    return _store
