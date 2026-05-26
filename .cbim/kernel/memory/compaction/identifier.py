"""
compaction/identifier.py — `identify(entry)` — sync side-effect of crud.write.

v2: short tier removed. The two v1 rules (`delete_short` /
`merge_short_into_medium`) both scanned short/, which no longer exists in v2.
The dream loop now owns transcript-to-medium distillation (memory_distill
skill), so identifier no longer has anything to stage at write time on the
existing tiers.

The seam stays in place: crud.write still calls `identify(entry)` after each
medium write. Future v2-native candidate kinds (e.g. medium-to-promote-candidate
detection) belong here. Today this is a deterministic no-op — never reads,
never writes, never raises.

Iron rule: identify is deterministic Python — NO LLM call, no event emission,
no callback into crud.
"""

from __future__ import annotations


def identify(entry: dict) -> None:
    """Sync side-effect of crud.primitives.write.

    `entry` shape (built by crud.primitives.write):
        {"path": <str>, "tier": "medium", "metadata": {...}}

    v2 no-op: short→medium grouping is gone (no short tier); promote-candidate
    detection on medium entries hasn't been spec'd yet. Keeping the symbol so
    crud.write's deferred import keeps resolving without conditional logic.
    """
    return
