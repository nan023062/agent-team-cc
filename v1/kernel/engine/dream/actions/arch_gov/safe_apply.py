"""arch_gov/safe_apply.py — SafeApply deterministic leaf.

Executes the "safe" bucket of findings produced by Classify. Per the
governance contract (safe = idempotent, reversible, doesn't touch public
contracts), the only safe action currently supported is dna_reindex on
orphan modules (ScanOrphan findings).

For every safe finding, records a one-line description into
state["safe_actions_applied"]. Actual MCP-tool execution is deliberately
stubbed: when t5 wires this subtree into the dream root, it will be
plumbed through the same kernel.dna service the MCP dna_reindex tool
calls. Until then this leaf just declares intent — never SUCCESS-with-
silent-modification.
"""
from __future__ import annotations

from engine.core.node import Node, Status


class SafeApply(Node):
    def __init__(self, *, state: dict, name: str = "SafeApply") -> None:
        self.name = name
        self._state = state

    def tick(self, bb) -> Status:
        safe = (self._state.get("buckets") or {}).get("safe") or []
        applied: list[str] = []

        for item in safe:
            kind = item.get("kind", "?")
            subject = item.get("subject", "?")
            detail = item.get("detail", "")
            # Action mapping: safe → describe what we would / did do.
            # Real MCP call is intentionally stubbed here; see module docstring.
            if kind == "scan_orphan":
                applied.append(
                    f"dna_reindex on orphan module {subject!r} ({detail})"
                )
            else:
                applied.append(f"safe action on {subject!r}: {detail}")

        self._state["safe_actions_applied"] = applied
        return Status.SUCCESS
