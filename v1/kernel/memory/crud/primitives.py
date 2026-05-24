"""
crud/primitives.py — Memory CRUD primitives (write / update / delete) + IndexMaintainer.

Phase 4A: the 3 write-side primitives are the only path that mutates the
short/ and medium/ store dirs and the .index/. All compaction products
(merged entries, archived sweeps, rebuilt index) must come through here.

Design (see crud/.dna/module.md):
- `write` is a single primitive in two ordered steps:
    1. put new entry into short/ and sync .index/
    2. call `compaction.identify(entry)` (deferred import to keep
       crud → compaction static dependency forbidden)
  The two steps form one atomic-feeling primitive; identify is a sync side
  effect of write, not a separate API call. If identify raises in step 2,
  step 1 is NOT rolled back (TODO 4B: decide rollback vs. log-and-continue).
- `delete` does NOT trigger identify; identify is only triggered on write.
- `update` is a patch-style mutation (4A: minimal shape; full patch
  semantics may extend later).

All write entry points (Hook / memory_write MCP / CLI) call these primitives
directly with a constructed backend — no MemoryEngine adapter layer.
"""

from __future__ import annotations

import re
from pathlib import Path

from .backend import MemoryBackend

SHORT = "short"
MEDIUM = "medium"
TIERS = (SHORT, MEDIUM)


def _check_tier(tier: str) -> None:
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}, got {tier!r}")


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


# ---------------------------------------------------------------------------
# IndexMaintainer — sync `.index/` on every CRUD primitive
# ---------------------------------------------------------------------------

class IndexMaintainer:
    """Keep the backend's index in lockstep with on-disk entries.

    4A: this is a thin wrapper over the existing backend.upsert / .delete
    calls (which the FileBackend treats as no-ops, ChromaBackend uses to
    keep its vector store synced). The class exists so future backends
    (or a future split between "the store" and "the index") have an
    obvious seam — today it's just delegation.
    """

    def __init__(self, backend: MemoryBackend) -> None:
        self._backend = backend

    def on_write(self, doc_id: str, text: str, metadata: dict) -> None:
        self._backend.upsert(doc_id=doc_id, text=text, metadata=metadata)

    def on_update(self, doc_id: str, text: str, metadata: dict) -> None:
        # Same shape as upsert today; here for symmetry / future divergence.
        self._backend.upsert(doc_id=doc_id, text=text, metadata=metadata)

    def on_delete(self, doc_id: str) -> None:
        self._backend.delete(doc_id)


# ---------------------------------------------------------------------------
# 3 primitives — write / update / delete
# ---------------------------------------------------------------------------

def write(path: Path, tier: str, backend: MemoryBackend) -> None:
    """Index a markdown entry file at `path` into `tier`.

    "Create is one primitive in two ordered steps" — see crud/.dna/module.md
    Key Decision #1. Step 1: persist to short/ + sync .index/. Step 2: call
    compaction.identify (deferred import to keep crud → compaction static
    dependency forbidden).
    """
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

    # Step 1: persist + index.
    index = IndexMaintainer(backend)
    index.on_write(doc_id=str(path), text=text, metadata=meta)

    # Step 2: deferred import — keep crud → compaction static dependency
    # forbidden (the dependency arrow points the other way; identify
    # being called from here is a runtime callback, not a static link).
    # Identify failure must NOT roll back step 1.
    # TODO 4B: decide rollback vs. log-and-continue policy.
    try:
        from memory.compaction.identifier import identify
        identify({"path": str(path), "tier": tier, "metadata": meta})
    except Exception:
        # 4A: identify is a skeleton — swallow until 4B defines policy.
        pass


def update(path: Path, tier: str, backend: MemoryBackend) -> None:
    """Re-index a modified entry. 4A shape: same as write() minus identify.

    `compaction.compact()` calls this after merging short entries into
    medium ones; identify on update would double-count, so we skip it.
    """
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

    index = IndexMaintainer(backend)
    index.on_update(doc_id=str(path), text=text, metadata=meta)


def delete(path: Path, backend: MemoryBackend) -> None:
    """Remove an entry from the backend index and the filesystem.

    Does NOT trigger compaction.identify (identify fires only on write).
    """
    index = IndexMaintainer(backend)
    index.on_delete(str(path))
