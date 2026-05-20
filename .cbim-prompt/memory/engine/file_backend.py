"""
file_backend.py — File-based MemoryBackend (default, zero external dependencies).

Retrieval is recency-based (modification time), not semantic.
To enable semantic search, swap in a vector backend (e.g. ChromaBackend)
by subclassing MemoryBackend and passing an instance to MemoryEngine.
"""

from pathlib import Path

from .base import MemoryBackend


class FileBackend(MemoryBackend):
    """Default backend: stores entries as Markdown files, retrieves by mtime."""

    def __init__(self, store_dir: Path) -> None:
        self._store = store_dir

    def upsert(self, doc_id: str, text: str, metadata: dict) -> None:
        # File is already written by writer.py before add() is called; nothing to index.
        pass

    def query(self, text: str, n_results: int,
              where: dict | None = None) -> list[dict]:
        """Return the most recently modified .md files.

        `text` is accepted for interface compatibility but ignored —
        retrieval order is modification time, newest first.
        `where` may carry {"tier": "short"|"medium"} to restrict scope.
        """
        tier = (where or {}).get("tier")
        tiers = [tier] if tier else ["short", "medium"]

        candidates: list[tuple[float, Path]] = []
        for t in tiers:
            tier_dir = self._store / t
            if tier_dir.exists():
                for p in tier_dir.glob("*.md"):
                    try:
                        candidates.append((p.stat().st_mtime, p))
                    except OSError:
                        pass

        candidates.sort(reverse=True)
        return [
            {
                "doc_id": str(p),
                "score": mtime,
                "metadata": {"tier": p.parent.name, "filename": p.name},
            }
            for mtime, p in candidates[:n_results]
        ]

    def delete(self, doc_id: str) -> None:
        p = Path(doc_id)
        if p.exists():
            p.unlink()

    def list_ids(self, where: dict | None = None) -> list[str]:
        tier = (where or {}).get("tier")
        tiers = [tier] if tier else ["short", "medium"]
        result = []
        for t in tiers:
            tier_dir = self._store / t
            if tier_dir.exists():
                result.extend(str(p) for p in sorted(tier_dir.glob("*.md")))
        return result
