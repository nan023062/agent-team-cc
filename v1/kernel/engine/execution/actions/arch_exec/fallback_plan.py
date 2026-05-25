"""arch_exec/fallback_plan.py — deterministic fallback for the architect-execution chain.

When any LLM-driven leaf in the architect-execution subtree (Scan / StateCheck /
Worth / Create / Extract / Diff / Validate / Map / Assemble) fails — typically a
truncated LLM response, missing API key (NullLLM), or malformed JSON — the
outer Selector falls through to this node so the execution pipeline still
produces a dispatchable plan instead of collapsing to an empty `done`.

The plan is intentionally trivial: a single task whose description is the raw
user_request and whose required_capability is "programmer". DispatchWork then
yields a normal work-agent dispatch, letting the assistant route the request to
HR / Programmer through the standard path.

No LLM call — never fails.
"""

from __future__ import annotations

from engine.core.node import Node, Status


class FallbackPlan(Node):
    """Write a one-task arch_plan derived from bb.user_request. Always SUCCESS."""

    def __init__(self, *, name: str = "FallbackPlan") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        description = (getattr(bb, "user_request", None) or "").strip() or "(empty request)"
        bb.arch_plan = [{
            "id": "t1",
            "description": description,
            "required_capability": "programmer",
            "params": {},
            "arch_context": "",
        }]
        return Status.SUCCESS
