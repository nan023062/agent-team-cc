"""hr_gov/build.py — Build deterministic leaf.

Finalizes the subtree by writing bb.hr_governance_report (same shape as
arch_governance_report: safe_actions_applied + advice_pending). Downstream
consumer is `emit_report.py`, which renders both reports into the
dream-tick markdown.
"""
from __future__ import annotations

from engine.core.node import Node, Status


class Build(Node):
    def __init__(self, *, state: dict, name: str = "Build") -> None:
        self.name = name
        self._state = state

    def tick(self, bb) -> Status:
        bb.hr_governance_report = {
            "safe_actions_applied": list(self._state.get("safe_actions_applied") or []),
            "advice_pending":       list(self._state.get("advice_pending") or []),
        }
        return Status.SUCCESS
