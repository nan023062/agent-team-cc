"""
compaction/rebuilder.py — `rebuild()` / `verify_retrieval_consistency()`.

v2: this replaces the v1 "rescan every tier dir and re-feed crud.write" path,
which existed to rebuild the in-process backend index. With the external
engine.retrieval index now the source of truth for cross-source search, the
rebuild action is two steps:

  1. Walk medium/ and re-call `crud.primitives.write` for each entry. This
     also re-fires the per-entry `engine.retrieval.index_upsert` sync, so a
     wholesale rebuild fixes drift on both the local backend index AND the
     external retrieval index.
  2. Call `engine.retrieval.verify_consistency("memory_medium", mode="full")`
     to surface anything step 1 couldn't reconcile (entries the retrieval
     index has but medium/ doesn't, etc.).

Step 1 is mostly a no-op on FileBackend (files ARE the local index) but
genuinely useful as a way to fan retrieval upserts for every medium entry.
Step 2 is the contractual side: a DriftReport callers can use to decide
whether further action is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memory.crud.backend import MemoryBackend
from memory.crud.primitives import MEDIUM, RETRIEVAL_SOURCE, write as _crud_write


@dataclass
class RebuildReport:
    indexed_count: int
    drift_checked: int
    drift_drifted: int
    drift_repaired: int
    drift_failed: int


def rebuild(store_dir: Path, backend: MemoryBackend,
            tier: str | None = None) -> int:
    """Rebuild the local backend index by scanning medium/.

    `tier` is accepted for v1 signature compatibility but only "medium" /
    None are valid in v2; any other value yields 0 (no walk performed).
    Returns count of re-indexed files.
    """
    if tier not in (None, MEDIUM):
        return 0
    tier_dir = Path(store_dir) / MEDIUM
    if not tier_dir.exists():
        return 0
    count = 0
    for md_file in sorted(tier_dir.glob("*.md")):
        try:
            _crud_write(md_file, MEDIUM, backend)
            count += 1
        except Exception:
            # Single-entry failure must not kill the rebuild — drift will
            # catch the gap on the verify pass.
            pass
    return count


def verify_retrieval_consistency(store_dir: Path):
    """Call engine.retrieval.verify_consistency for the memory_medium source.

    Returns the DriftReport. Deferred import keeps this module loadable in
    environments where retrieval isn't wired (rare; tests mostly).
    """
    from engine.retrieval import verify_consistency
    return verify_consistency(RETRIEVAL_SOURCE, mode="full")


def rebuild_and_verify(store_dir: Path, backend: MemoryBackend) -> RebuildReport:
    """Combined rebuild + verify pass — what the dream loop's MemRebuildIndex
    node should call. Returns a single report with both step outputs."""
    indexed = rebuild(store_dir, backend)
    drift = verify_retrieval_consistency(store_dir)
    return RebuildReport(
        indexed_count=indexed,
        drift_checked=drift.checked,
        drift_drifted=len(drift.drifted),
        drift_repaired=len(drift.repaired),
        drift_failed=len(drift.failed),
    )
