"""actions/dispatch_arch.py — knowledge governance dispatcher.

Yields a DispatchRequest(agent_type="architect", subtask_id="governance_knowledge")
on first tick when bb.arch_governance_dispatched is None. On resume the
matching CollectArchAdvice node consumes the payload — this node only owns
the yield gesture.

Prompt scaffolding is delegated to `engine.loops.architect_governance` so
the design flowchart (WORKFLOW-ARCHITECT.zh-CN.md §2) NodeSpec list is the
single source of truth.

Per-tick idempotent: once dispatched (flag set), subsequent ticks are SUCCESS
no-ops, so this node is safe under any composite that may re-enter it on
resume.
"""

from __future__ import annotations

from engine.execution.core.node import Node, Status

from ..api.result import DispatchRequest


def _loop():
    # Lazy import to break the import cycle: engine.loops/__init__ eagerly
    # imports dream_root → dream_loop → this module.
    import engine.loops.architect_governance as m
    return m


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
            prompt=_loop().compose_prompt(bb),
            subtask_id="governance_knowledge",
            timeout_hint_s=self._timeout_hint_s,
        )
        bb.arch_governance_dispatched = True
        return Status.RUNNING
