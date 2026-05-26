"""loops/memory_governance.py — Memory governance sub-loop, re-export.

The memory governance sub-loop is implemented across three action modules:
  - engine.dream.actions.mem_steps         (in-process structural nodes:
      MemHealthScan / MemCompact / MemSweepExpired / MemRebuildIndex)
  - engine.dream.actions.transcript_steps  (v2 transcript-driven leaves:
      TranscriptScan / DistillGate / TranscriptDelete)
  - engine.dream.actions.dispatch_mem_distill + collect_mem_distill
      (the MemDistill yield triad — Dispatch yields to the main agent
      for the ``memory_distill`` skill; Collect parses the report on resume)

The governance root (engine.dream.tree.dream_loop) wires the 9 nodes into
a Sequence wrapped by Catch+Timeout. This module re-exports the action
classes plus a thin builder that returns the same inner Sequence (no
Catch/Timeout — those belong to the parent root) for callers who want the
sub-loop in isolation (e.g. topology tests, dry runs).

No new logic; design source of truth stays in
dream/actions/mem_steps.py + dream/actions/transcript_steps.py +
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
    MemHealthScan,
    MemRebuildIndex,
    MemSweepExpired,
)
from engine.dream.actions.transcript_steps import (
    DistillGate,
    TranscriptDelete,
    TranscriptScan,
)
from memory.crud.backend import MemoryBackend
from memory.crud.file_backend import FileBackend


def build_memory_governance_subtree(
    *,
    store_dir: Path,
    backend: MemoryBackend | None = None,
    transcripts_dir: Path | None = None,
) -> Node:
    """Construct the nine-step memory governance Sequence (no decorators).

    Matches the inner sequence of MemoryGovernanceStep in
    dream/tree/dream_loop.py. Use this when you want the bare sub-loop
    without the Catch/Timeout that the dream root adds.

    ``transcripts_dir`` is forwarded to TranscriptScan; None falls back
    to ``~/.claude/projects/<slug>/`` against the process CWD.
    """
    store_dir = Path(store_dir)
    backend = backend or FileBackend(store_dir)
    return Sequence(
        [
            MemHealthScan(store_dir=store_dir, name="MemHealthScan"),
            TranscriptScan(transcripts_dir=transcripts_dir, name="TranscriptScan"),
            DistillGate(name="DistillGate"),
            DispatchMemDistill(store_dir=store_dir, name="DispatchMemDistill"),
            CollectMemDistill(store_dir=store_dir, name="CollectMemDistill"),
            TranscriptDelete(name="TranscriptDelete"),
            MemCompact(store_dir=store_dir, name="MemCompact"),
            MemSweepExpired(store_dir=store_dir, backend=backend, name="MemSweepExpired"),
            MemRebuildIndex(store_dir=store_dir, backend=backend, name="MemRebuildIndex"),
        ],
        name="MemoryGovernanceStep",
    )


__all__ = [
    "MemHealthScan",
    "TranscriptScan",
    "DistillGate",
    "DispatchMemDistill",
    "CollectMemDistill",
    "TranscriptDelete",
    "MemCompact",
    "MemSweepExpired",
    "MemRebuildIndex",
    "build_memory_governance_subtree",
]
