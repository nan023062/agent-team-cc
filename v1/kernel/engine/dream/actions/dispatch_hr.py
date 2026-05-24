"""actions/dispatch_hr.py — capability governance dispatcher.

Yields a DispatchRequest(agent_type="hr", subtask_id="governance_capability")
on first tick when bb.hr_governance_dispatched is None.
"""

from __future__ import annotations

from engine.bt.core.node import Node, Status

from ..api.result import DispatchRequest


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
            prompt=self._compose_prompt(bb),
            subtask_id="governance_capability",
            timeout_hint_s=self._timeout_hint_s,
        )
        bb.hr_governance_dispatched = True
        return Status.RUNNING

    def _compose_prompt(self, bb) -> str:
        return (
            "## 治理模式\n\n"
            "# HR Governance Sub-loop\n\n"
            f"run_id: {bb.run_id}\n"
            f"trigger_reason: {bb.trigger_reason or 'unknown'}\n\n"
            "## Task\n"
            "Run the HR governance sub-loop per "
            "`design/WORKFLOW-HR.zh-CN.md` §2: scan .claude/agents/ registry "
            "for idle / disabled / capability-gap / drift / duplicate / "
            "split-candidate agents. Return a structured report:\n\n"
            "```\n"
            "safe_actions_applied:\n"
            "  - <one line per safe idempotent action taken>\n"
            "advice_pending:\n"
            "  - <one line per high-impact suggestion needing user confirm>\n"
            "```\n\n"
            "Safe actions (refresh timestamps, fill missing fields, log "
            "entries) may be executed directly. High-impact actions "
            "(recruit / archive / merge agents) MUST go to advice_pending only."
        )
