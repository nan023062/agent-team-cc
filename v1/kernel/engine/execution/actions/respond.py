"""actions/respond.py — render bb.final_response from bb.work_results.

v3 contract: if bb.final_response is already populated (e.g. DirectReply
already wrote one), leave it alone. If bb.interrupt_reason is set, leave
final_response empty so the Runner routes to BtResult.Error. Otherwise
concatenate work_results outputs into a single user-facing message.
"""

from __future__ import annotations

from engine.core.node import Node, Status


class Respond(Node):
    def __init__(self, *, name: str = "Respond") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        # Interrupt path: leave final_response empty so the Runner emits
        # BtResult(kind="error", interrupt_reason=...).
        if bb.interrupt_reason:
            return Status.SUCCESS
        if bb.final_response:
            return Status.SUCCESS
        results = bb.work_results or {}
        if not results:
            bb.final_response = "(empty response)"
            return Status.SUCCESS
        parts: list[str] = []
        # Preserve arch_plan order when available; fall back to dict order.
        order = [t.get("id") for t in (bb.arch_plan or []) if t.get("id") in results]
        if not order:
            order = list(results.keys())
        for tid in order:
            r = results.get(tid) or {}
            out = (r.get("output") or "").strip() if isinstance(r, dict) else ""
            if out:
                parts.append(out)
        bb.final_response = "\n\n---\n\n".join(parts) if parts else "(no output)"
        return Status.SUCCESS
