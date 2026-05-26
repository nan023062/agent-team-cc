"""
crud/primitives.py — Memory CRUD primitives (write / update / delete) + IndexMaintainer.

v2: short/ tier removed. Only medium/ is writable here. Each primitive performs
a synchronous side-effect on engine.retrieval to keep the external search index
in lockstep with on-disk entries.

Design (see crud/.dna/module.md, status=spec):
- `write` is a single primitive in three ordered steps; success requires all three:
    1. Persist new entry to medium/ and sync the local backend index.
    2. Call `compaction.identify(entry)` (deferred import — keeps the static
       dependency arrow `compaction -> crud` from reversing).
    3. Call `engine.retrieval.index_upsert("memory_medium", doc_id, content,
       metadata={"source_path": <abs path>, ...})`.
  Failure of step 1 or 3 propagates as the original exception. Step 2 failures
  are swallowed (identify is a non-essential side effect; never blocks write).
- `update` is the patch-style mutation used by compaction when rewriting medium
  entries; same three steps as `write` minus identify (identify on update would
  recurse via compaction's own writes).
- `delete` removes the entry from the backend, the filesystem, and the external
  retrieval index. Failure of any step propagates.

Iron rule: passing `tier="short"` raises `ValueError`. There is no migration
path — short tier was removed in v2 because CC transcripts already serve as
the short-term memory layer.
"""

from __future__ import annotations

import re
from pathlib import Path

from .backend import MemoryBackend

MEDIUM = "medium"
TIERS = (MEDIUM,)

# Logical source name for engine.retrieval. Lives here so identifier /
# compaction / facade all refer to the same constant.
RETRIEVAL_SOURCE = "memory_medium"


def _check_tier(tier: str) -> None:
    if tier not in TIERS:
        raise ValueError(
            f"tier must be one of {TIERS}, got {tier!r}; "
            f"short tier was removed in v2 (CC transcripts are the short-term layer)"
        )


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


def _build_metadata(path: Path, tier: str) -> dict:
    meta = _read_frontmatter(path.read_text(encoding="utf-8"))
    meta["tier"] = tier
    meta["path"] = str(path)
    meta["filename"] = path.name
    m = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
    if m:
        meta["date"] = m.group(1)
    return meta


# ---------------------------------------------------------------------------
# IndexMaintainer — sync local backend index on every CRUD primitive
# ---------------------------------------------------------------------------

class IndexMaintainer:
    """Keep the backend's index in lockstep with on-disk entries.

    Thin wrapper over backend.upsert / .delete. The seam stays in case a
    future backend wants a separate "store vs. index" split.
    """

    def __init__(self, backend: MemoryBackend) -> None:
        self._backend = backend

    def on_write(self, doc_id: str, text: str, metadata: dict) -> None:
        self._backend.upsert(doc_id=doc_id, text=text, metadata=metadata)

    def on_update(self, doc_id: str, text: str, metadata: dict) -> None:
        self._backend.upsert(doc_id=doc_id, text=text, metadata=metadata)

    def on_delete(self, doc_id: str) -> None:
        self._backend.delete(doc_id)


# ---------------------------------------------------------------------------
# engine.retrieval sync — third step of write/update, primary step of delete
# ---------------------------------------------------------------------------

def _retrieval_upsert(path: Path, text: str, metadata: dict) -> None:
    """Sync upsert to engine.retrieval. source_path is mandatory metadata.

    Errors propagate to the caller — retrieval consistency is a hard
    contract of memory.crud (see crud/.dna/module.md Key Decision #3).
    """
    # Deferred import: keeps the retrieval dependency a runtime call, and
    # lets the rest of memory.crud import even when retrieval isn't wired
    # (tests that stub it out, etc.).
    from engine.retrieval import index_upsert

    meta = dict(metadata)
    # Always carry source_path so retrieval.fast_check can stat the original.
    meta.setdefault("source_path", str(path))
    index_upsert(
        source=RETRIEVAL_SOURCE,
        doc_id=str(path),
        content=text,
        metadata=meta,
    )


def _retrieval_delete(doc_id: str) -> None:
    from engine.retrieval import index_delete
    index_delete(source=RETRIEVAL_SOURCE, doc_id=doc_id)


# ---------------------------------------------------------------------------
# 3 primitives — write / update / delete
# ---------------------------------------------------------------------------

def write(path: Path, tier: str, backend: MemoryBackend) -> None:
    """Index a markdown entry file at `path` into `tier`.

    Three ordered steps (see module docstring). Steps 1 and 3 are required
    for success; step 2 (identify) is best-effort.
    """
    _check_tier(tier)
    text = _entry_text(path)
    if not text:
        return
    meta = _build_metadata(path, tier)

    # Step 1: persist + local index.
    index = IndexMaintainer(backend)
    index.on_write(doc_id=str(path), text=text, metadata=meta)

    # Step 2: best-effort identify (deferred import; never blocks write).
    try:
        from memory.compaction.identifier import identify
        identify({"path": str(path), "tier": tier, "metadata": meta})
    except Exception:
        pass

    # Step 3: synchronous external retrieval index. Errors propagate so the
    # caller can decide whether to roll back step 1 or surface the failure.
    _retrieval_upsert(path, text, meta)


def update(path: Path, tier: str, backend: MemoryBackend) -> None:
    """Re-index a modified entry. Same shape as write() minus identify.

    `compaction.compact()` calls this after rewriting a medium entry;
    identify on update would double-count.
    """
    _check_tier(tier)
    text = _entry_text(path)
    if not text:
        return
    meta = _build_metadata(path, tier)

    index = IndexMaintainer(backend)
    index.on_update(doc_id=str(path), text=text, metadata=meta)

    _retrieval_upsert(path, text, meta)


def delete(path: Path, backend: MemoryBackend) -> None:
    """Remove an entry from the local backend index, the filesystem snapshot,
    and the external retrieval index.

    Does NOT trigger compaction.identify (identify fires only on write).
    """
    index = IndexMaintainer(backend)
    index.on_delete(str(path))
    _retrieval_delete(str(path))
