"""actions/dispatch_hr.py — capability governance dispatcher.

Yields a DispatchRequest(agent_type="hr", subtask_id="governance_capability")
on first tick when bb.hr_governance_dispatched is None.

Prompt scaffolding is delegated to `engine.loops.hr_governance` so the
design flowchart (WORKFLOW-HR.zh-CN.md §2) NodeSpec list is the single
source of truth.
"""

from __future__ import annotations

from engine.execution.core.node import Node, Status

from ..api.result import DispatchRequest


def _loop():
    # Lazy import to break the import cycle (see dispatch_arch.py).
    import engine.loops.hr_governance as m
    return m


DEFAULT_HR_FILE = ".claude/agents/hr/hr.md"


class DispatchHRGovern(Node):
    def __init__(
        self,
        *,
        agent_file: str = DEFAULT_HR_FILE,
        timeout_hint_s: int = 600,
        name: str = "DispatchHRGovern",
    ) -> None:
        self.name = name
        self._agent_file = agent_file
        self._timeout_hint_s = timeout_hint_s

    def tick(self, bb) -> Status:
        if bb.hr_governance_dispatched:
            return Status.SUCCESS
        bb.pending_dispatch = DispatchRequest(
            agent_type="hr",
            agent_file=self._agent_file,
            prompt=_loop().compose_prompt(bb),
            subtask_id="governance_capability",
            timeout_hint_s=self._timeout_hint_s,
        )
        bb.hr_governance_dispatched = True
        return Status.RUNNING
