"""core/blackboard.py — Blackboard: the single carrier of cross-node state.

The 18 fields from WORKFLOW-EXECUTION §2.1 are declared as dataclass-style
attributes. Dirty tracking: any explicit attribute assignment marks the bb
dirty; the Runner consults `bb._dirty` to decide whether to rewrite bb.json
on node exit.

No write barriers are enforced here (the "single writer per field" rule
is a design-time invariant; runtime enforcement would be ceremonious and
duplicate static review). Reads are unrestricted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Canonical field set per WORKFLOW-EXECUTION §2.1 (18 fields).
FIELDS: tuple[str, ...] = (
    "tick_id",
    "user_request",
    "intent",
    "dispatch_plan",
    "arch_context",
    "subtask_results",
    "iteration",
    "iteration_cap",
    "converge_signal",
    "final_response",
    "interrupt_reason",
    "runner_resume_path",
    "bb_status",
    "pending_dispatch",
    "trace",
    "memory_flush_queue",
    "audit_report",
    "agent_list",
)


class Blackboard:
    """Single in-memory carrier of all cross-node state for one tick.

    Any direct attribute assignment (e.g. `bb.intent = {...}`) marks the
    bb dirty for the next Runner snapshot.
    """

    __slots__ = ("_dirty", *FIELDS, "_created_at", "_updated_at")

    def __init__(self) -> None:
        # Bypass __setattr__ during init so we don't mark dirty for defaults.
        object.__setattr__(self, "_dirty", False)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        object.__setattr__(self, "_created_at", now)
        object.__setattr__(self, "_updated_at", now)
        for f in FIELDS:
            object.__setattr__(self, f, None)
        # Sensible empty containers for the few list/dict-typed fields.
        object.__setattr__(self, "subtask_results", {})
        object.__setattr__(self, "trace", [])
        object.__setattr__(self, "memory_flush_queue", [])
        object.__setattr__(self, "iteration", 0)

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
    # Serialization (consumed by persistence/snapshot.py)
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
            "tick_id": self.tick_id,
            "created_at": self._created_at,
            "updated_at": self._updated_at,
            "bb_status": self.bb_status or "running",
            "fields": fields,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Blackboard":
        bb = cls()
        # Restore timestamps without dirtying.
        object.__setattr__(bb, "_created_at", d.get("created_at", bb._created_at))
        object.__setattr__(bb, "_updated_at", d.get("updated_at", bb._updated_at))
        fields = d.get("fields", {}) or {}
        for k, v in fields.items():
            if k in FIELDS:
                object.__setattr__(bb, k, v)
        # bb_status sits both at top-level and inside fields per spec; prefer top.
        if "bb_status" in d:
            object.__setattr__(bb, "bb_status", d["bb_status"])
        object.__setattr__(bb, "_dirty", False)
        return bb

    def clear_dirty(self) -> None:
        object.__setattr__(self, "_dirty", False)

    @property
    def dirty(self) -> bool:
        return self._dirty
