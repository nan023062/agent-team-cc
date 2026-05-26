"""
compaction/compactor.py — `compact()` orchestration.

The contract (compaction/.dna/module.md, status=spec):
- compact() runs independently of write — triggered by CLI / schedule / threshold.
- It reads candidates/ and writes results back through crud.primitives.update
  / .delete (compaction holds NO direct file-write permission on medium/).
- The candidates/ work area is exclusive to this module.

v2: short-tier responsibilities removed. The two candidate kinds that touched
short/ in v1 (`merge_short_into_medium`, `delete_short`) are gone — they were
the entire point of short→medium distillation, which has moved to the dream
loop's `memory_distill` skill. compact() in v2 is mostly a hatch for future
v2-native candidate kinds (promote-candidate review, medium-to-medium dedupe,
etc.); for now it just clears unknown candidates with a recorded error so the
work area doesn't accumulate stale stubs.

Iron rule: compact() itself is deterministic Python — NO LLM call here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from memory.crud.backend import MemoryBackend
from memory.crud.file_backend import FileBackend

from .candidates import CandidatesArea
from .health import HealthChecker


@dataclass
class CompactionReport:
    candidates_processed: int = 0
    medium_entries_written: int = 0
    errors: list[str] = field(default_factory=list)
    # Diagnostic fields surfaced via dream's mem_steps for the run report.
    skipped: int = 0
    health_breaches: list[str] = field(default_factory=list)


def compact(store_dir: Path, backend: MemoryBackend | None = None) -> CompactionReport:
    """Drive the candidates → medium pipeline.

    v2: with no short-tier candidate kinds defined, the only candidate kind
    recognised is `promote_candidate`, which is intentionally left in place
    (the knowledge loop scans for it via the parent facade). Anything else
    is skipped with an error recorded so stale candidates surface in logs.
    """
    store_dir = Path(store_dir)
    report = CompactionReport()

    # Health gate is informational. v2 health no longer surfaces SHORT_*
    # breaches; it still reports candidate / index status.
    health = HealthChecker(store_dir).check()
    report.health_breaches = list(health.breaches)

    candidates_area = CandidatesArea(store_dir)
    pending = candidates_area.pull_pending()
    if not pending:
        return report

    if backend is None:
        backend = FileBackend(store_dir)

    processed_ids: list[str] = []

    for cand in pending:
        cand_id = cand.get("path") or cand.get("id") or "<unknown>"
        kind = (cand.get("kind") or cand.get("action") or "").strip()

        try:
            if kind == "promote_candidate" or kind == "":
                # Owned by the knowledge loop — leave in the work area for
                # `scan(filter='promote_candidate')` to pick up.
                report.skipped += 1
            else:
                # v1 kinds like 'merge_short_into_medium' / 'delete_short'
                # are no longer recognised. Surface as an error so stale
                # candidates from a pre-v2 store get noticed.
                report.errors.append(f"unknown candidate kind '{kind}' on {cand_id}")
                report.skipped += 1
        except Exception as e:
            report.errors.append(f"{cand_id}: {type(e).__name__}: {e}")
            report.skipped += 1

    # Don't clear processed_ids here — v2 compact() doesn't actually consume
    # any kind today. Future medium-native kinds will populate processed_ids.
    if processed_ids:
        candidates_area.clear(processed_ids)

    return report
