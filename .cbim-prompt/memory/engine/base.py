"""
base.py — MemoryBackend abstract interface.

Swap the backend by subclassing MemoryBackend and passing an instance
to MemoryEngine. The rest of the system stays untouched.
"""

from abc import ABC, abstractmethod


class MemoryBackend(ABC):

    @abstractmethod
    def upsert(self, doc_id: str, text: str, metadata: dict) -> None:
        """Insert or update a document in the store."""

    @abstractmethod
    def query(self, text: str, n_results: int, where: dict | None) -> list[dict]:
        """Semantic search. Returns list of dicts with keys:
        - doc_id (str)
        - score   (float, higher = more relevant)
        - metadata (dict)
        """

    @abstractmethod
    def delete(self, doc_id: str) -> None:
        """Remove a document from the store."""

    @abstractmethod
    def list_ids(self, where: dict | None = None) -> list[str]:
        """Return all doc_ids, optionally filtered by metadata."""
