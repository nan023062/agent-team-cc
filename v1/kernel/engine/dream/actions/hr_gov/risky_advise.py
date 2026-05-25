"""hr_gov/risky_advise.py — RiskyAdvise deterministic leaf.

Serializes risky HR findings into state["advice_pending"] (招募 / 归档 /
合并 / 裂变 / 改写 Positioning all live here). No agent-file writes.
"""
from __future__ import annotations

from engine.core.node import Node, Status


class RiskyAdvise(Node):
    def __init__(self, *, state: dict, name: str = "RiskyAdvise") -> None:
        self.name = name
        self._state = state

    def tick(self, bb) -> Status:
        risky = (self._state.get("buckets") or {}).get("risky") or []
        pending: list[str] = []
        for item in risky:
            kind = item.get("kind", "?")
            subject = item.get("subject", "?")
            detail = item.get("detail", "")
            pending.append(f"[{kind}] {subject}: {detail}")
        self._state["advice_pending"] = pending
        return Status.SUCCESS
