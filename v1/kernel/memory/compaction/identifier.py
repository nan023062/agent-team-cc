"""
compaction/identifier.py — `identify(entry)` — sync side-effect of crud.write.

Phase 4A: SKELETON. The contract (crud/.dna/module.md Key Decision #1):
- `identify` is called by crud.primitives.write step 2 (after persist+index).
- It must NOT notify any external caller, emit events, or call back into crud.
- Its sole side-effect is staging matching entries into the candidates/ work area.

4A behaviour: pass. No identification logic yet — full pattern matching lands in 4B.
"""

from __future__ import annotations


def identify(entry: dict) -> None:
    """Skeleton stub. See module docstring.

    Phase 4A: no-op. 4B will:
      - inspect entry.metadata for short/medium tier + tag patterns
      - decide if it qualifies as a compaction or promote candidate
      - call CandidatesArea.stage(entry) when applicable
    """
    # TODO 4B: pattern-match entry into candidate buckets and stage.
    return None
