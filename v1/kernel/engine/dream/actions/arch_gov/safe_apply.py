"""arch_gov/safe_apply.py — SafeApply deterministic leaf.

Executes the "safe" bucket of findings produced by Classify. Per the
governance contract (safe = idempotent, reversible, doesn't touch public
contracts), the only safe action currently supported is dna_reindex on
orphan modules (ScanOrphan findings).

Behavior:
  - Collect all `scan_orphan` findings, fire ONE `update_index` call
    (idempotent — re-scans + rewrites `.cbim/index.md`), then record one
    `safe_actions_applied` entry per orphan.
  - Non-orphan safe findings degrade to advisory entries in
    `advice_pending` — there is no other safe action wired today.
  - Per-finding error isolation: a service exception is recorded to
    `advice_pending` and the leaf still returns SUCCESS, so the rest of
    the governance tick can proceed.
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
        advice: list[str] = list(self._state.get("advice_pending") or [])

        orphans = [item for item in safe if item.get("kind") == "scan_orphan"]
        others = [item for item in safe if item.get("kind") != "scan_orphan"]

        if orphans:
            try:
                from cbi._primitives.modules import update_index
                from services._fm import find_project_root
                from pathlib import Path

                root = Path(find_project_root(None))
                update_index(root)
            except Exception as exc:  # noqa: BLE001 — isolate every failure
                reason = f"reindex failed: {type(exc).__name__}: {exc}"
                for item in orphans:
                    subject = item.get("subject", "?")
                    advice.append(f"reindex skipped for {subject!r}: {reason}")
            else:
                for item in orphans:
                    subject = item.get("subject", "?")
                    detail = item.get("detail", "")
                    applied.append(
                        f"dna_reindex on orphan module {subject!r} ({detail})"
                    )

        for item in others:
            subject = item.get("subject", "?")
            detail = item.get("detail", "")
            advice.append(
                f"safe action on {subject!r}: no handler wired ({detail})"
            )

        self._state["safe_actions_applied"] = applied
        self._state["advice_pending"] = advice
        return Status.SUCCESS
