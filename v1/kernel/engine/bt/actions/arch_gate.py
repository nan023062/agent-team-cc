"""actions/arch_gate.py — the knowledge gate.

Yields a DispatchRequest(agent_type="architect", prompt=<context request>)
on first tick when bb.arch_context is absent; on resume stores the
Architect's reply into bb.arch_context. Subsequent ticks SUCCESS through
without re-dispatch (the gate is per-tick idempotent so Retry is safe).

Only runs when at least one subtask in dispatch_plan declares
depends_on=["arch_context"]. Single-subtask non-execution plans
(pure_query / review / non_requirement) skip the gate.
"""

from __future__ import annotations

from ..api.result import DispatchRequest
from ..core.node import Node, Status


class ArchGate(Node):
    def __init__(self, *, name: str = "ArchGate") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        plan = bb.dispatch_plan or []
        needs_gate = any("arch_context" in (s.get("depends_on") or []) for s in plan)
        if not needs_gate:
            return Status.SUCCESS
        if bb.arch_context is not None:
            return Status.SUCCESS
        bb.pending_dispatch = DispatchRequest(
            agent_type="architect",
            agent_file=".claude/agents/architect/architect.md",
            prompt=self._compose_arch_prompt(bb),
            subtask_id=None,
        )
        return Status.RUNNING

    def on_resume(self, bb, payload) -> None:
        if isinstance(payload, str):
            bb.arch_context = {"output": payload, "kind": "context_pack_raw"}
        elif isinstance(payload, dict):
            bb.arch_context = payload
        else:
            bb.arch_context = {"output": str(payload), "kind": "context_pack_raw"}
        bb.pending_dispatch = None

    def _compose_arch_prompt(self, bb) -> str:
        user_request = bb.user_request or ""
        intent = bb.intent or {}
        prior = bb.subtask_results or {}
        escalation = ""
        for sid, r in prior.items():
            if r.get("needs_arch_decision"):
                escalation = (
                    f"\n\n## Work Agent Escalation\n"
                    f"Subtask `{sid}` returned NEEDS_ARCH_DECISION. "
                    f"Full output:\n\n{r.get('output', '')}\n"
                )
                break
        return (
            "# Knowledge Gate — Architect Context Request\n\n"
            "## User request\n"
            f"{user_request}\n\n"
            "## Intent classification\n"
            f"- kind: {intent.get('kind')}\n"
            f"- target_agent: {intent.get('target_agent')}\n"
            f"{escalation}\n"
            "## Asked of Architect\n"
            "Produce a ContextPack per `cbim skill show architect.arch_modules` "
            "containing: task_id, modules[], dependency_rules, work_agent_notes. "
            "Return the ContextPack block verbatim — the engine will embed it "
            "into the Work Agent prompt without modification."
        )
