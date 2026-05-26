"""actions/mem_steps.py — memory governance step actions (in-process leaves).

Four pure-Python structural nodes:
  MemHealthScan      — in-process call to memory.HealthChecker.check()
  MemCompact         — in-process call to memory.compact()
  MemSweepExpired    — in-process call to memory.sweep_expired()
  MemRebuildIndex    — in-process call to memory.compaction.rebuilder
                       .rebuild_and_verify() (always runs in v2)

The v2 distill triggering (TranscriptScan + DistillGate + the
DispatchMemDistill / CollectMemDistill / TranscriptDelete yield triad)
lives in ``actions/transcript_steps.py`` and the matching dispatch /
collect modules.

**Rule:** memory governance is mostly pure in-process Python — health
scan, compact, sweep, rebuild are deterministic and never yield.
Semantic short→medium compression is LLM-driven and runs via the
DispatchMemDistill self-yield to the main agent.

Any other node added here MUST be pure Python unless its inputs / outputs
are not enumerable (i.e. unless semantic judgment is intrinsic to the work).

Construction contract (per architect spec):
  - store_dir: Path is injected at construction time and stored as self._store_dir
  - backend: MemoryBackend is injected at construction time and stored as
    self._backend (omitted for the two calls that don't take a backend:
    compact() and HealthChecker.check())
  - neither is placed on bb
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.core.node import Node, Status

from memory.compaction import HealthChecker, compact, sweep_expired
from memory.compaction.rebuilder import rebuild_and_verify
from memory.crud.backend import MemoryBackend


# ---------------------------------------------------------------------------
# MemHealthScan
# ---------------------------------------------------------------------------

class MemHealthScan(Node):
    """Run memory.HealthChecker.check() and store the report on bb.mem_health.

    HealthChecker is a Phase-4A skeleton; an empty/default report is a
    legal SUCCESS.
    """

    def __init__(self, *, store_dir: Path, name: str = "MemHealthScan") -> None:
        self.name = name
        self._store_dir = Path(store_dir)

    def tick(self, bb) -> Status:
        try:
            report = HealthChecker(self._store_dir).check()
        except Exception as e:
            bb.mem_health = {"error": f"{type(e).__name__}: {e}"}
            return Status.FAILURE
        bb.mem_health = _report_to_dict(report)
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# MemCompact
# ---------------------------------------------------------------------------

class MemCompact(Node):
    """Run memory.compact(); skip-empty is SUCCESS per architect spec."""

    def __init__(self, *, store_dir: Path, name: str = "MemCompact") -> None:
        self.name = name
        self._store_dir = Path(store_dir)

    def tick(self, bb) -> Status:
        try:
            report = compact(self._store_dir)
        except Exception as e:
            bb.mem_compact_result = {"error": f"{type(e).__name__}: {e}"}
            return Status.FAILURE
        bb.mem_compact_result = _report_to_dict(report)
        return Status.SUCCESS


# MemDistillGate (v1) was removed in v2 — the distill triggering rule is
# now data-volume on bb.transcript_paths via DistillGate (see
# actions/transcript_steps.py). MemHealthScan no longer needs to feed a
# threshold check.


# ---------------------------------------------------------------------------
# MemSweepExpired
# ---------------------------------------------------------------------------

class MemSweepExpired(Node):
    """Run memory.sweep_expired(store_dir, backend, keep_days)."""

    def __init__(
        self,
        *,
        store_dir: Path,
        backend: MemoryBackend,
        keep_days: int = 3,
        name: str = "MemSweepExpired",
    ) -> None:
        self.name = name
        self._store_dir = Path(store_dir)
        self._backend = backend
        self._keep_days = keep_days

    def tick(self, bb) -> Status:
        try:
            deleted = sweep_expired(self._store_dir, self._backend, keep_days=self._keep_days)
        except Exception as e:
            bb.mem_sweep_result = {"error": f"{type(e).__name__}: {e}"}
            return Status.FAILURE
        bb.mem_sweep_result = {"deleted": int(deleted), "keep_days": self._keep_days}
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# MemRebuildIndex
# ---------------------------------------------------------------------------

class MemRebuildIndex(Node):
    """Run memory.compaction.rebuild_and_verify() unconditionally.

    v2 behaviour (per .dna/contract.md outbound table): always run the
    rebuild + drift-verify pair on the medium tier. The rebuild step is
    idempotent (re-feeds the per-entry retrieval upsert; a clean medium
    re-converges in one pass), and the verify step surfaces anything
    the rebuild couldn't reconcile. Skipping on "no drift" was a v1
    heuristic that depended on a HealthChecker indicator that the v2
    rebuilder makes redundant — every tick now does the full check.

    Writes the ``RebuildReport`` (as a dict) to ``bb.mem_index_result``.
    """

    def __init__(
        self,
        *,
        store_dir: Path,
        backend: MemoryBackend,
        tier: str | None = None,
        name: str = "MemRebuildIndex",
    ) -> None:
        self.name = name
        self._store_dir = Path(store_dir)
        self._backend = backend
        # ``tier`` kept for v1 signature compatibility; rebuild_and_verify
        # only addresses medium in v2.
        self._tier = tier

    def tick(self, bb) -> Status:
        try:
            report = rebuild_and_verify(self._store_dir, self._backend)
        except Exception as e:
            bb.mem_index_result = {"error": f"{type(e).__name__}: {e}"}
            return Status.FAILURE
        bb.mem_index_result = _report_to_dict(report)
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _report_to_dict(obj: Any) -> dict:
    """Best-effort conversion of a dataclass/report to a plain dict.

    The 4A HealthChecker / CompactionReport are dataclass-ish; zero-value
    defaults convert cleanly. Unknown shapes return {} (still a legal SUCCESS).
    """
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "__dataclass_fields__"):
        out = {}
        for f in obj.__dataclass_fields__:
            try:
                out[f] = getattr(obj, f)
            except Exception:
                continue
        return out
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    return {"repr": repr(obj)[:200]}
