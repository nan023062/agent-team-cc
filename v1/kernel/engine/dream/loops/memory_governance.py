"""loops/memory_governance.py — Memory governance sub-loop, re-export.

The memory governance sub-loop is implemented across two action modules:
  - engine.dream.actions.mem_steps    (5 in-process structural nodes:
      MemHealthScan / MemCompact / MemDistillGate / MemSweepExpired /
      MemRebuildIndex)
  - engine.dream.actions.dispatch_mem_distill + collect_mem_distill
      (the MemDistill yield triad — Dispatch yields to the HR agent for
      the ``memory_distill`` skill; Collect parses the report on resume)

The governance root (engine.dream.tree.dream_loop) wires the 7 nodes into
a Sequence wrapped by Catch+Timeout. This module re-exports the action
classes plus a thin builder that returns the same inner Sequence (no
Catch/Timeout — those belong to the parent root) for callers who want the
sub-loop in isolation (e.g. topology tests, dry runs).

No new logic; design source of truth stays in dream/actions/mem_steps.py +
dream/actions/dispatch_mem_distill.py + dream/actions/collect_mem_distill.py.
"""
from __future__ import annotations

from pathlib import Path

from engine.core.composite import Sequence
from engine.core.node import Node
from engine.dream.actions.collect_mem_distill import CollectMemDistill
from engine.dream.actions.dispatch_mem_distill import DispatchMemDistill
from engine.dream.actions.mem_steps import (
    MemCompact,
    MemDistillGate,
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
    """Construct the seven-step memory governance Sequence (no decorators).

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
            MemDistillGate(store_dir=store_dir, name="MemDistillGate"),
            DispatchMemDistill(store_dir=store_dir, name="DispatchMemDistill"),
            CollectMemDistill(store_dir=store_dir, name="CollectMemDistill"),
            MemSweepExpired(store_dir=store_dir, backend=backend, name="MemSweepExpired"),
            MemRebuildIndex(store_dir=store_dir, backend=backend, name="MemRebuildIndex"),
        ],
        name="MemoryGovernanceStep",
    )


__all__ = [
    "MemHealthScan",
    "MemCompact",
    "MemDistillGate",
    "DispatchMemDistill",
    "CollectMemDistill",
    "MemSweepExpired",
    "MemRebuildIndex",
    "build_memory_governance_subtree",
]
