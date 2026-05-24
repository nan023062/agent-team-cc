"""actions/dispatch_arch.py — knowledge governance dispatcher.

Yields a DispatchRequest(agent_type="architect", subtask_id="governance_knowledge")
on first tick when bb.arch_governance_dispatched is None. On resume the
matching CollectArchAdvice node consumes the payload — this node only owns
the yield gesture.

Per-tick idempotent: once dispatched (flag set), subsequent ticks are SUCCESS
no-ops, so this node is safe under any composite that may re-enter it on
resume.
"""

from __future__ import annotations

from engine.bt.core.node import Node, Status

from ..api.result import DispatchRequest


# Default agent file paths (matched at .claude/agents/<role>/<role>.md per
# project convention; ArchGate/CallHR use the same files in the execution loop).
DEFAULT_ARCH_FILE = ".claude/agents/architect/architect.md"


class DispatchArchGovern(Node):
    def __init__(
        self,
        *,
        agent_file: str = DEFAULT_ARCH_FILE,
        timeout_hint_s: int = 600,
        name: str = "DispatchArchGovern",
    ) -> None:
        self.name = name
        self._agent_file = agent_file
        self._timeout_hint_s = timeout_hint_s

    def tick(self, bb) -> Status:
        if bb.arch_governance_dispatched:
            return Status.SUCCESS
        bb.pending_dispatch = DispatchRequest(
            agent_type="architect",
            agent_file=self._agent_file,
            prompt=self._compose_prompt(bb),
            subtask_id="governance_knowledge",
            timeout_hint_s=self._timeout_hint_s,
        )
        bb.arch_governance_dispatched = True
        return Status.RUNNING

    def _compose_prompt(self, bb) -> str:
        return (
            "## 治理模式\n\n"
            "# Architect Governance Sub-loop\n\n"
            f"run_id: {bb.run_id}\n"
            f"trigger_reason: {bb.trigger_reason or 'unknown'}\n\n"
            "## Task\n"
            "Run the Architect governance sub-loop per "
            "`design/WORKFLOW-ARCHITECT.zh-CN.md` §2: scan .dna/ registry for "
            "orphan / drift / split-candidate / merge-candidate / dependency-conflict "
            "/ memory-promotion-candidate modules. Return a structured report:\n\n"
            "```\n"
            "safe_actions_applied:\n"
            "  - <one line per safe idempotent action taken>\n"
            "advice_pending:\n"
            "  - <one line per high-impact suggestion needing user confirm>\n"
            "```\n\n"
            "Safe actions (timestamps, missing fields, log entries) may be "
            "executed directly. High-impact actions (archive module, change "
            "contract, delete .dna/) MUST go to advice_pending only."
        )
