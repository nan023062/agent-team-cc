"""arch_gov/report.py — Report deterministic leaf.

Finalizes the subtree by writing the governance report onto the dream
blackboard. Shape matches what CollectArchAdvice's parser expects (see
engine.dream.loops.architect_governance.parse_response):

    bb.arch_governance_report = {
        "safe_actions_applied": [str, ...],
        "advice_pending":       [str, ...],
    }

Both lists are required (empty allowed). Once written, the subtree's
scratch state is dropped — it's purely intra-tick.
"""
from __future__ import annotations

from engine.core.node import Node, Status


class Report(Node):
    def __init__(self, *, state: dict, name: str = "Report") -> None:
        self.name = name
        self._state = state

    def tick(self, bb) -> Status:
        bb.arch_governance_report = {
            "safe_actions_applied": list(self._state.get("safe_actions_applied") or []),
            "advice_pending":       list(self._state.get("advice_pending") or []),
        }
        return Status.SUCCESS
