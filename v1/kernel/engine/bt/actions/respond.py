"""actions/respond.py — render bb.final_response to ship to the user.

Reads converge_signal + final_response + interrupt_reason; writes nothing
new in the happy path (final_response already set by ConvergeJudge or
AskClarify). On interrupt-without-message, synthesizes a short note.
"""

from __future__ import annotations

from ..core.node import Node, Status


class Respond(Node):
    def __init__(self, *, name: str = "Respond") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        # Interrupt path: leave final_response empty so the Runner routes
        # to BtResult(kind="error", interrupt_reason=...). The runner
        # synthesizes the error_message from interrupt_reason.
        if bb.interrupt_reason and bb.converge_signal == "interrupt":
            return Status.SUCCESS
        if bb.final_response:
            return Status.SUCCESS
        bb.final_response = "(empty response)"
        return Status.SUCCESS
