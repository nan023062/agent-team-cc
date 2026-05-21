"""
engine.py — MemoryEngine facade.

Public CRUD API used by CLI, hooks, and agents. Backend-agnostic.

Default backend: FileBackend (zero external dependencies, recency-based retrieval).
To enable semantic search: pass ChromaBackend (or any MemoryBackend subclass)
to MemoryEngine — all callers above this layer are unaffected.
"""

import re
from pathlib import Path

from .base import MemoryBackend

SHORT = "short"
MEDIUM = "medium"
TIERS = (SHORT, MEDIUM)


def _read_frontmatter(text: str) -> dict:
    meta: dict = {}
    if not text.startswith("---"):
        return meta
    end = text.find("\n---", 3)
    if end == -1:
        return meta
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta


def _entry_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            raw = raw[end + 4:]
    return raw.strip()


class MemoryEngine:

    def __init__(self, backend: MemoryBackend, store_dir: Path | None = None):
        self._backend = backend
        self._store = store_dir or Path("memory")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(self, path: Path, tier: str) -> None:
        """Index a markdown entry file into the given tier."""
        _check_tier(tier)
        text = _entry_text(path)
        if not text:
            return
        meta = _read_frontmatter(path.read_text(encoding="utf-8"))
        meta["tier"] = tier
        meta["path"] = str(path)
        meta["filename"] = path.name
        m = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
        if m:
            meta["date"] = m.group(1)
        self._backend.upsert(doc_id=str(path), text=text, metadata=meta)

    def delete(self, path: Path) -> None:
        """Remove an entry from the index and filesystem."""
        self._backend.delete(str(path))

    # ------------------------------------------------------------------
    # Read / Search
    # ------------------------------------------------------------------

    def query(self, text: str, tier: str | None = None, top_k: int = 5) -> list[str]:
        """Return list of file paths. Ordering is backend-defined.

        FileBackend: most recently modified first (text ignored).
        SemanticBackend: cosine similarity to text.
        """
        return [r["doc_id"] for r in self.query_verbose(text, tier=tier, top_k=top_k)]

    def query_verbose(self, text: str, tier: str | None = None,
                      top_k: int = 5) -> list[dict]:
        """Same as query but returns full result dicts: doc_id, score, metadata."""
        if tier is not None:
            _check_tier(tier)
        where = {"tier": tier} if tier else None
        return self._backend.query(text, n_results=top_k, where=where)

    def list_ids(self, tier: str | None = None) -> list[str]:
        """Enumerate all indexed doc_ids, optionally filtered by tier."""
        where = {"tier": tier} if tier else None
        return self._backend.list_ids(where=where)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def cleanup_short(self, keep_days: int = 3) -> int:
        """Delete short-term entries that are distilled AND older than keep_days.

        Lifecycle: distill skill marks entries with 'distilled: YYYY-MM-DD' in
        frontmatter. This cleanup only removes entries that carry that marker AND
        whose filename date is older than keep_days. Undistilled entries are never
        deleted by cleanup — they stay until explicitly processed or manually removed.
        Returns count of deleted files.
        """
        from datetime import datetime, timedelta

        cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d")
        short_dir = self._store / SHORT
        if not short_dir.exists():
            return 0

        deleted = 0
        for md_file in sorted(short_dir.glob("*.md")):
            m = re.match(r"(\d{4}-\d{2}-\d{2})", md_file.name)
            if not m or m.group(1) >= cutoff:
                continue
            try:
                raw = md_file.read_text(encoding="utf-8")
                if not re.search(r"^distilled:\s*\S", raw, re.MULTILINE):
                    continue  # not yet distilled — skip
            except (FileNotFoundError, PermissionError):
                continue
            try:
                self.delete(md_file)
            except Exception:
                pass
            deleted += 1
        return deleted

    def reindex(self, tier: str | None = None) -> int:
        """Rebuild backend index by scanning store directories.

        No-op for FileBackend (files are the index). Useful when switching
        to a semantic backend to populate it from existing entries.
        Returns count of indexed files.
        """
        tiers = [tier] if tier else list(TIERS)
        count = 0
        for t in tiers:
            tier_dir = self._store / t
            if not tier_dir.exists():
                continue
            for md_file in sorted(tier_dir.glob("*.md")):
                try:
                    self.add(md_file, t)
                    count += 1
                except Exception:
                    pass
        return count


def _check_tier(tier: str) -> None:
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}, got {tier!r}")
