"""hr_exec/assemble.py — Build deterministic leaf.

Promotes the per-task draft list (`bb.hr_assignments_draft`) into the
canonical `bb.agent_assignments` field that the parent execution-root
loop consumes. Pure data shaping — no LLM, no I/O.
"""

from __future__ import annotations

from engine.core.node import Node, Status


class Build(Node):
    def __init__(self, *, name: str = "Build") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        draft = getattr(bb, "hr_assignments_draft", None) or []
        # Defensive copy so downstream mutations don't bleed back into draft.
        bb.agent_assignments = [dict(item) for item in draft if isinstance(item, dict)]
        return Status.SUCCESS


def build() -> Build:
    return Build()
