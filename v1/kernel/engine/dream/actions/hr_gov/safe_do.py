"""hr_gov/safe_do.py — SafeDo deterministic leaf.

Executes the "safe" bucket of HR-governance findings. Currently the only
recognized safe action is补 frontmatter 缺失字段（ScanBroken with
bucket_hint=safe）. Real MCP-tool execution (agent_edit) is intentionally
stubbed until t5 wires this subtree into the dream root — see arch_gov/
safe_apply.py for the same rationale.
"""
from __future__ import annotations

from engine.core.node import Node, Status


class SafeDo(Node):
    def __init__(self, *, state: dict, name: str = "SafeDo") -> None:
        self.name = name
        self._state = state

    def tick(self, bb) -> Status:
        safe = (self._state.get("buckets") or {}).get("safe") or []
        applied: list[str] = []
        for item in safe:
            kind = item.get("kind", "?")
            subject = item.get("subject", "?")
            detail = item.get("detail", "")
            if kind == "scan_broken":
                applied.append(
                    f"agent_edit on {subject!r}: would补 frontmatter ({detail})"
                )
            else:
                applied.append(f"safe action on {subject!r}: {detail}")
        self._state["safe_actions_applied"] = applied
        return Status.SUCCESS
