"""hr_gov/classify.py — Classify deterministic leaf.

Bins every finding into safe / risky per HR-governance hard rules
(see WORKFLOW-HR §2):

  safe   ← scan_broken with bucket_hint="safe" (补 frontmatter 字段)
         ← anything explicitly marked bucket_hint="safe"
  risky  ← everything else (招募 / 归档 / 合并 / 裂变 / 改写 Positioning)
"""
from __future__ import annotations

from engine.core.node import Node, Status


class Classify(Node):
    def __init__(self, *, state: dict, name: str = "Classify") -> None:
        self.name = name
        self._state = state

    def tick(self, bb) -> Status:
        findings_by_scan = self._state.get("findings") or {}
        safe: list[dict] = []
        risky: list[dict] = []

        for _, items in findings_by_scan.items():
            for item in items or []:
                bucket = item.get("bucket_hint") or "risky"
                (safe if bucket == "safe" else risky).append(item)

        self._state["buckets"] = {"safe": safe, "risky": risky}
        return Status.SUCCESS
