"""arch_gov/risky_advise.py — RiskyAdvise deterministic leaf.

Serializes the "risky" bucket into state["advice_pending"] as one-line
human-readable strings. No .dna/ writes — risky items are queued for
user / HR / future-session adjudication.
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
