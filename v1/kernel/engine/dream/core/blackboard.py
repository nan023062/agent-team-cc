"""dream/core/blackboard.py — DreamBlackboard: governance-loop carrier.

Independent from bt's Blackboard (which carries the 18 execution-loop fields).
The dream loop owns its own 19-field schema per design WORKFLOW-DREAM §五 +
the runner-required scaffolding (bb_status / runner_resume_path / pending_dispatch
/ trace) shared with bt at the Runner protocol level (IdentifiableBB).

Field write-ownership (single-writer rule, validated by code review):
  - run_id, trigger_reason, started_at        ← InitDreamTick
  - mem_health                                  ← MemHealthScan
  - mem_compact_result                          ← MemCompact (or skip path)
  - mem_sweep_result                            ← MemSweepExpired
  - mem_index_result                            ← MemRebuildIndex
  - arch_governance_dispatched                  ← DispatchArchGovern
  - arch_governance_report                      ← CollectArchAdvice
  - hr_governance_dispatched                    ← DispatchHRGovern
  - hr_governance_report                        ← CollectHRAdvice
  - step_results                                ← SequenceTolerant container
  - summary_for_session, report_path            ← EmitReport
  - finished_at                                 ← FinalizeDreamTick
  - bb_status, runner_resume_path,
    pending_dispatch, trace                     ← Runner / decorators
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Canonical 19-field schema for the governance loop blackboard.
FIELDS: tuple[str, ...] = (
    # Identity & trigger
    "run_id",
    "trigger_reason",
    "started_at",
    "finished_at",
    # Memory governance step
    "mem_health",
    "mem_compact_result",
    "mem_sweep_result",
    "mem_index_result",
    # Knowledge governance step
    "arch_governance_dispatched",
    "arch_governance_report",
    # Capability governance step
    "hr_governance_dispatched",
    "hr_governance_report",
    # Aggregation + reporting
    "step_results",
    "summary_for_session",
    "report_path",
    # Runner-required scaffolding (mirrors bt.Blackboard semantics)
    "bb_status",
    "runner_resume_path",
    "pending_dispatch",
    "trace",
)


class DreamBlackboard:
    """In-memory carrier of cross-node state for one dream tick.

    Satisfies bt.core.blackboard.IdentifiableBB so the bt Runner can drive
    this blackboard without bt importing dream.
    """

    __slots__ = ("_dirty", *FIELDS, "_created_at", "_updated_at")

    def __init__(self) -> None:
        object.__setattr__(self, "_dirty", False)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        object.__setattr__(self, "_created_at", now)
        object.__setattr__(self, "_updated_at", now)
        for f in FIELDS:
            object.__setattr__(self, f, None)
        # Sensible empty containers.
        object.__setattr__(self, "step_results", {})
        object.__setattr__(self, "trace", [])

    def __setattr__(self, name: str, value: Any) -> None:
        if name in FIELDS:
            object.__setattr__(self, name, value)
            object.__setattr__(self, "_dirty", True)
            object.__setattr__(
                self, "_updated_at",
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        else:
            object.__setattr__(self, name, value)

    # ------------------------------------------------------------------
    # Serialization (consumed by bt.persistence.snapshot)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        fields = {}
        for f in FIELDS:
            v = getattr(self, f)
            if v is None:
                continue
            fields[f] = v
        return {
            "schema_version": 1,
            "tick_id": self.run_id,
            "created_at": self._created_at,
            "updated_at": self._updated_at,
            "bb_status": self.bb_status or "running",
            "fields": fields,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DreamBlackboard":
        bb = cls()
        object.__setattr__(bb, "_created_at", d.get("created_at", bb._created_at))
        object.__setattr__(bb, "_updated_at", d.get("updated_at", bb._updated_at))
        fields = d.get("fields", {}) or {}
        for k, v in fields.items():
            if k in FIELDS:
                object.__setattr__(bb, k, v)
        if "bb_status" in d:
            object.__setattr__(bb, "bb_status", d["bb_status"])
        object.__setattr__(bb, "_dirty", False)
        return bb

    def clear_dirty(self) -> None:
        object.__setattr__(self, "_dirty", False)

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def identifier(self) -> str | None:
        """Satisfies IdentifiableBB: stable directory name for this tick."""
        return self.run_id
