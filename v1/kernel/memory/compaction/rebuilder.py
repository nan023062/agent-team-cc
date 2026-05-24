"""
compaction/rebuilder.py — `rebuild()` (replaces legacy reindex).

Phase 4A: moved out of the legacy reindex path. Same semantics:
- Walk each tier dir and re-feed every .md file through crud.primitives.write
  so the backend index is rebuilt from on-disk truth.
- No-op-ish on FileBackend (files ARE the index), genuinely useful on
  ChromaBackend (re-embeds every doc).
"""

from __future__ import annotations

from pathlib import Path

from memory.crud.backend import MemoryBackend
from memory.crud.primitives import TIERS, write as _crud_write


def rebuild(store_dir: Path, backend: MemoryBackend,
            tier: str | None = None) -> int:
    """Rebuild backend index by scanning store directories.

    `tier` is "short" / "medium" / None (both). Returns count of indexed files.
    """
    tiers = [tier] if tier else list(TIERS)
    count = 0
    for t in tiers:
        tier_dir = Path(store_dir) / t
        if not tier_dir.exists():
            continue
        for md_file in sorted(tier_dir.glob("*.md")):
            try:
                _crud_write(md_file, t, backend)
                count += 1
            except Exception:
                pass
    return count
