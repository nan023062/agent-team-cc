"""loops/memory_governance.py — Memory governance sub-loop, re-export.

The memory governance sub-loop is already implemented as four in-process
BT actions at engine.dream.actions.mem_steps:
  MemHealthScan / MemCompact / MemSweepExpired / MemRebuildIndex

The governance root (engine.dream.tree.dream_loop) wires them into a
Sequence wrapped by Catch+Timeout. This module re-exports the four
action classes plus a thin builder that returns the same inner Sequence
(no Catch/Timeout — those belong to the parent root) for callers who
want the sub-loop in isolation (e.g. topology tests, dry runs).

No new logic; design source of truth stays in dream/actions/mem_steps.py.
"""
from __future__ import annotations

from pathlib import Path

from engine.core.composite import Sequence
from engine.core.node import Node
from engine.dream.actions.mem_steps import (
    MemCompact,
    MemHealthScan,
    MemRebuildIndex,
    MemSweepExpired,
)
from memory.crud.backend import MemoryBackend
from memory.crud.file_backend import FileBackend


def build_memory_governance_subtree(
    *,
    store_dir: Path,
    backend: MemoryBackend | None = None,
) -> Node:
    """Construct the four-step memory governance Sequence (no decorators).

    Matches the inner sequence of MemoryGovernanceStep in
    dream/tree/dream_loop.py. Use this when you want the bare sub-loop
    without the Catch/Timeout that the dream root adds.
    """
    store_dir = Path(store_dir)
    backend = backend or FileBackend(store_dir)
    return Sequence(
        [
            MemHealthScan(store_dir=store_dir, name="MemHealthScan"),
            MemCompact(store_dir=store_dir, name="MemCompact"),
            MemSweepExpired(store_dir=store_dir, backend=backend, name="MemSweepExpired"),
            MemRebuildIndex(store_dir=store_dir, backend=backend, name="MemRebuildIndex"),
        ],
        name="MemoryGovernanceStep",
    )


__all__ = [
    "MemHealthScan",
    "MemCompact",
    "MemSweepExpired",
    "MemRebuildIndex",
    "build_memory_governance_subtree",
]
