"""
compaction/compactor.py — `compact()` orchestration.

Phase 4A: SKELETON. The contract (compaction/.dna/module.md):
- compact() runs independently of write — triggered by CLI / schedule / threshold.
- It reads candidates/, merges short entries into medium, and writes results
  back through crud.primitives.update / .delete (compaction holds NO direct
  file-write permission on short/ or medium/).
- The candidates/ work area is exclusive to this module.
- Internal closure: compact's writes trigger identify again — naturally
  convergent since each compact strictly reduces candidate count.

4B will land:
- read pending candidates from CandidatesArea
- group/merge by topic+module
- compose new medium/ entry text
- call crud.primitives.update for the new medium entry, crud.primitives.delete
  for each merged short entry
- CandidatesArea.clear(...) at the end
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CompactionReport:
    candidates_processed: int = 0
    medium_entries_written: int = 0
    short_entries_deleted: int = 0
    errors: list[str] = field(default_factory=list)


def compact(store_dir: Path) -> CompactionReport:
    """Skeleton stub. See module docstring.

    Phase 4A: returns an empty report; 4B will implement the full pipeline.
    """
    # TODO 4B: drive the candidates → medium merge pipeline.
    return CompactionReport()
