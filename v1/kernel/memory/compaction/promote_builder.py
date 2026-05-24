"""
compaction/promote_builder.py — `scan_for_promote_candidates()`.

Phase 4A: SKELETON. The contract (compaction/.dna/module.md, Key Decision #2):
- This module identifies entries worth promoting to the knowledge system
  (e.g. .dna/ writeable patterns).
- Detection only — never notifies architect/HR; never emits events.
- Hits land in CandidatesArea with a `promote_candidate` tag, then sit
  idle until a knowledge-loop caller does `scan(filter='promote_candidate')`
  through the parent facade.

4B will land the actual scan + tag-and-stage logic.
"""

from __future__ import annotations

from pathlib import Path


def scan_for_promote_candidates(store_dir: Path) -> int:
    """Skeleton stub. See module docstring.

    Returns the number of candidates staged. 4A: always 0.
    """
    # TODO 4B: walk medium/ for promotion-pattern hits and stage them.
    return 0
