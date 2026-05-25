"""actions/mem_steps.py — memory governance step actions.

Five structural nodes covering the memory governance sub-loop:
  MemHealthScan      — in-process call to memory.HealthChecker.check()
  MemCompact         — in-process call to memory.compact()
  MemDistillGate     — pure decision: should we trigger MemDistill yield?
  MemSweepExpired    — in-process call to memory.sweep_expired()
  MemRebuildIndex    — in-process call to memory.compaction.rebuild()
                       (conditional: only when bb.mem_health.index_drift truthy)

**Rule (revised):** memory governance is mostly pure in-process Python —
health scan, compact, sweep, rebuild are deterministic and never yield.
The single exception is the MemDistill triad (Gate / Dispatch / Collect):
the Dispatch leaf yields to the HR agent to run the ``memory_distill``
skill — semantic short→medium compression is LLM-driven.

Boundary: structural merging → Python (identifier.py + compactor.py).
Semantic merging → LLM (MemDistill yield).

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

import time
from pathlib import Path
from typing import Any

from engine.core.node import Node, Status

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
# MemDistillGate
# ---------------------------------------------------------------------------

# Independent threshold from health.short_max_entries; we want distill to
# pre-empt the hard ceiling so SHORT_OVERFLOW is rare.
_DISTILL_THRESHOLD = 30
# Cadence cap — distill at least once per week regardless of pressure.
_DISTILL_PERIOD_DAYS = 7
# Breach codes that should force a distill attempt.
_DISTILL_BREACH_CODES = ("SHORT_OVERFLOW", "SHORT_VOLUME", "SHORT_STALE")


class MemDistillGate(Node):
    """Decide whether the MemDistill yield should fire this tick.

    Reads bb.mem_health (set by MemHealthScan) and the .last_distill marker
    under store_dir to set bb.mem_distill_dispatched as a hint for the
    paired Dispatch / Collect nodes:

      - True  → DispatchMemDistill will yield to HR for the memory_distill
                skill; CollectMemDistill will await the parsed report.
      - False → Dispatch / Collect short-circuit; mem_distill_result records
                the skip reason for EmitReport's rendering.

    The gate itself never yields and never touches the store beyond reading
    the .last_distill mtime. Decision is local + cheap.
    """

    def __init__(self, *, store_dir: Path, name: str = "MemDistillGate") -> None:
        self.name = name
        self._store_dir = Path(store_dir)

    def tick(self, bb) -> Status:
        health = bb.mem_health or {}
        # _report_to_dict flattens HealthReport into
        # {"indicators": {...}, "breaches": [...], "index_drift": bool}
        indicators = health.get("indicators") or {}
        breaches = health.get("breaches") or []
        short_count = int(indicators.get("short_count") or 0)

        marker = self._store_dir / ".last_distill"
        days_since: float = float("inf")
        if marker.exists():
            try:
                age_seconds = time.time() - marker.stat().st_mtime
                days_since = age_seconds / 86400.0
            except OSError:
                days_since = float("inf")

        should_distill = (
            any(code in breaches for code in _DISTILL_BREACH_CODES)
            or short_count >= _DISTILL_THRESHOLD
            or days_since >= _DISTILL_PERIOD_DAYS
        )

        bb.mem_distill_dispatched = bool(should_distill)
        if not should_distill:
            bb.mem_distill_result = {
                "skipped": True,
                "reason": "below_threshold",
                "short_count": short_count,
                "days_since_last_distill": (
                    None if days_since == float("inf") else round(days_since, 2)
                ),
            }
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
