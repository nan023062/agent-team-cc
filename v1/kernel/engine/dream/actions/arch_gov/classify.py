"""arch_gov/classify.py — Classify deterministic leaf.

Reads every list under state["findings"][<scan_id>] and bins each finding
into state["buckets"]["safe"] or state["buckets"]["risky"] per hard rules:

  safe   ← scan_orphan (幽灵模块，dna_reindex 可清), or any finding whose
            bucket_hint=="safe" (per-scan default set in scans.py).
  risky  ← everything else (status changes, cycle breaks, contract drift,
            memory promotion, split, merge, restructure).

The criterion is intentionally simple: classification is a kernel rule, not
an LLM judgment. If a scan ever wants to override the default, it sets
`bucket_hint` on the finding (already plumbed by _ScanBase.parse_reply).
"""
from __future__ import annotations

from engine.core.node import Node, Status


_SAFE_SCAN_IDS = {"scan_orphan"}


class Classify(Node):
    def __init__(self, *, state: dict, name: str = "Classify") -> None:
        self.name = name
        self._state = state

    def tick(self, bb) -> Status:
        findings_by_scan = self._state.get("findings") or {}
        safe: list[dict] = []
        risky: list[dict] = []

        for scan_id, items in findings_by_scan.items():
            for item in items or []:
                bucket = item.get("bucket_hint")
                if not bucket:
                    bucket = "safe" if scan_id in _SAFE_SCAN_IDS else "risky"
                (safe if bucket == "safe" else risky).append(item)

        self._state["buckets"] = {"safe": safe, "risky": risky}
        return Status.SUCCESS
