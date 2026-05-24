"""actions/ask_clarify.py — short-circuit branch when intent is ambiguous.

Writes the clarifying question into bb.final_response and sets
converge_signal=done so LoopUntilConverge terminates immediately and
Respond ships the question back to the user.
"""

from __future__ import annotations

from ..core.node import Node, Status


class AskClarify(Node):
    def __init__(self, *, name: str = "AskClarify") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        intent = bb.intent or {}
        q = (intent.get("clarifying_question") or "").strip()
        if not q:
            q = "Could you clarify what you want me to do?"
        bb.final_response = q
        bb.converge_signal = "done"
        return Status.SUCCESS
