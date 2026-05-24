"""actions/mem_steps.py — memory governance step actions.

Four nodes covering the memory governance sub-loop:
  MemHealthScan      — in-process call to memory.HealthChecker.check()
  MemCompact         — in-process call to memory.compact()
  MemSweepExpired    — in-process call to memory.sweep_expired()
  MemRebuildIndex    — in-process call to memory.compaction.rebuild()
                       (conditional: only when bb.mem_health.index_drift truthy)

Iron rule per WORKFLOW-DREAM §四: memory governance does NOT go through MCP
and does NOT yield. All four are pure in-process Python.

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

from engine.bt.core.node import Node, Status

from memory.compaction import HealthChecker, compact, rebuild, sweep_expired
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
    """Run memory.compaction.rebuild() — conditional on bb.mem_health.index_drift.

    When index_drift is falsy the action is skipped and returns SUCCESS with a
    `{skipped: true}` result; this matches the design rule "SUCCESS = 重建完成或跳过".
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
        self._tier = tier

    def tick(self, bb) -> Status:
        health = bb.mem_health or {}
        if not health.get("index_drift"):
            bb.mem_index_result = {"skipped": True, "reason": "no_index_drift"}
            return Status.SUCCESS
        try:
            count = rebuild(self._store_dir, self._backend, tier=self._tier)
        except Exception as e:
            bb.mem_index_result = {"error": f"{type(e).__name__}: {e}"}
            return Status.FAILURE
        bb.mem_index_result = {"indexed": int(count), "tier": self._tier}
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
