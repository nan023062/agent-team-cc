"""actions/decompose.py — turn intent into bb.dispatch_plan + bump iteration.

Two-path policy mirrors IntentAnalyze:
  - non_requirement / pure_query / review: build a single-subtask plan
    targeting the canonical agent for that kind (rule path).
  - execution / business_crud / capability_crud: try LLM decomposer; if
    NullLLM, fall back to a single execution subtask depending on
    "arch_context" (so ArchGate will yield first).

NEVER wrap this Action in @Retry — non-idempotent (bumps iteration).
"""

from __future__ import annotations

from typing import Any

from ..api.result import Subtask
from ..core.node import Node, Status


_AGENT_FILES = {
    "programmer": ".claude/agents/programmer/programmer.md",
    "architect": ".claude/agents/architect/architect.md",
    "auditor": ".claude/agents/auditor/auditor.md",
    "hr": ".claude/agents/hr/hr.md",
}


def _agent_file_for(role: str | None) -> str | None:
    if not role:
        return None
    return _AGENT_FILES.get(role)


class Decompose(Node):
    def __init__(self, *, llm: Any = None, name: str = "Decompose") -> None:
        self.name = name
        self._llm = llm

    def tick(self, bb) -> Status:
        bb.iteration = (bb.iteration or 0) + 1
        # Reset subtask_results at the start of every new iteration so that
        # ConvergeJudge's "all subtasks ok" rule can fire on the *current*
        # iteration's results rather than getting stuck on stale needs_arch
        # entries from prior iterations.
        bb.subtask_results = {}
        intent = bb.intent or {}
        kind = intent.get("kind", "ambiguous")

        # Single-subtask fast paths.
        if kind in ("non_requirement", "pure_query", "review"):
            target = intent.get("target_agent") or (
                "auditor" if kind == "review" else "architect"
            )
            bb.dispatch_plan = [Subtask(
                id="t1",
                kind=kind,
                target_agent=target,
                target_agent_file=_agent_file_for(target),
                prompt=bb.user_request or "",
                depends_on=[],
            ).to_dict()]
            return Status.SUCCESS

        # Try LLM decomposition first.
        if self._llm is not None:
            try:
                raw = self._llm.decompose(
                    bb.user_request or "", intent, bb.subtask_results or {},
                )
                bb.dispatch_plan = [Subtask(**d).to_dict() for d in raw]
                return Status.SUCCESS
            except NotImplementedError:
                pass

        # Fallback: single execution subtask depending on arch_context.
        target = intent.get("target_agent") or "programmer"
        bb.dispatch_plan = [Subtask(
            id=f"t{bb.iteration}",
            kind="execution",
            target_agent=target,
            target_agent_file=_agent_file_for(target),
            prompt=bb.user_request or "",
            depends_on=["arch_context"],
        ).to_dict()]
        return Status.SUCCESS
