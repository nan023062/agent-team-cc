"""
engine.py — MemoryEngine facade.

Public CRUD API used by CLI, hooks, and agents. Backend-agnostic.
"""

import re
from pathlib import Path

from .base import MemoryBackend

SHORT = "short"
MEDIUM = "medium"
TIERS = (SHORT, MEDIUM)

_STORE_DIR = Path("memory/store")


def _default_store(base: Path = Path(".")) -> Path:
    return base / "memory" / "store"


def _read_frontmatter(text: str) -> dict:
    """Parse YAML-style frontmatter between --- delimiters."""
    meta: dict = {}
    if not text.startswith("---"):
        return meta
    end = text.find("\n---", 3)
    if end == -1:
        return meta
    block = text[3:end].strip()
    for line in block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta


def _entry_text(path: Path) -> str:
    """Read file; strip frontmatter for embedding."""
    raw = path.read_text(encoding="utf-8")
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            raw = raw[end + 4:]
    return raw.strip()


class MemoryEngine:

    def __init__(self, backend: MemoryBackend, store_dir: Path | None = None):
        self._backend = backend
        self._store = store_dir or _default_store()

    # ------------------------------------------------------------------
    # Public API
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
        # Extract date from filename (YYYY-MM-DD-...)
        m = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
        if m:
            meta["date"] = m.group(1)
        self._backend.upsert(doc_id=str(path), text=text, metadata=meta)

    def query(self, text: str, tier: str | None = None, top_k: int = 5) -> list[str]:
        """Semantic search. Returns list of file paths (strings).

        tier=None queries across both tiers.
        """
        where = {"tier": tier} if tier else None
        results = self._backend.query(text, n_results=top_k, where=where)
        return [r["doc_id"] for r in results]

    def query_verbose(self, text: str, tier: str | None = None, top_k: int = 5) -> list[dict]:
        """Same as query but returns full result dicts including score and metadata."""
        where = {"tier": tier} if tier else None
        return self._backend.query(text, n_results=top_k, where=where)

    def delete(self, path: Path) -> None:
        """Remove an entry from the index."""
        self._backend.delete(str(path))

    def reindex(self, tier: str | None = None) -> int:
        """Rebuild index by scanning store directories. Returns count of indexed files."""
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
