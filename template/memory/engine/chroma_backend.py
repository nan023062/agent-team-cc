"""
chroma_backend.py — ChromaDB implementation of MemoryBackend.

Single collection "memory" with a `tier` metadata field ("short"|"medium")
to separate the two memory layers within one ChromaDB collection.

Replace this file to swap the storage backend without touching anything else.
"""

import os
from pathlib import Path

from .base import MemoryBackend

_DEFAULT_DB_PATH = Path("memory/store/.chroma")


class ChromaBackend(MemoryBackend):

    def __init__(self, db_path: Path | None = None):
        import chromadb

        host = os.environ.get("CHROMA_HOST")
        port = int(os.environ.get("CHROMA_PORT", "8000"))

        if host:
            self._client = chromadb.HttpClient(host=host, port=port)
        else:
            path = db_path or _DEFAULT_DB_PATH
            path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(path))

        self._col = self._client.get_or_create_collection(
            name="memory",
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # MemoryBackend interface
    # ------------------------------------------------------------------

    def upsert(self, doc_id: str, text: str, metadata: dict) -> None:
        self._col.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])

    def query(self, text: str, n_results: int, where: dict | None) -> list[dict]:
        kwargs: dict = {"query_texts": [text], "n_results": n_results}
        if where:
            kwargs["where"] = where

        count = self._col.count()
        if count == 0:
            return []
        kwargs["n_results"] = min(n_results, count)

        res = self._col.query(**kwargs)
        out = []
        ids = res["ids"][0]
        distances = res["distances"][0]
        metadatas = res["metadatas"][0]
        for doc_id, dist, meta in zip(ids, distances, metadatas):
            out.append({"doc_id": doc_id, "score": 1.0 - dist, "metadata": meta})
        return out

    def delete(self, doc_id: str) -> None:
        self._col.delete(ids=[doc_id])

    def list_ids(self, where: dict | None = None) -> list[str]:
        kwargs: dict = {}
        if where:
            kwargs["where"] = where
        result = self._col.get(**kwargs)
        return result["ids"]
