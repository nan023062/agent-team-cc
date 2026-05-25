"""
compaction/compactor.py — `compact()` orchestration.

The contract (compaction/.dna/module.md):
- compact() runs independently of write — triggered by CLI / schedule / threshold.
- It reads candidates/, merges short entries into medium, and writes results
  back through crud.primitives.update / .delete (compaction holds NO direct
  file-write permission on short/ or medium/).
- The candidates/ work area is exclusive to this module.
- Internal closure: compact's writes trigger identify again — naturally
  convergent since each compact strictly reduces candidate count.

Iron rule (this module): ``compact()`` itself is deterministic Python —
NO LLM call here. Semantic short→medium merging is the ``memory_distill``
skill's job (LLM-driven, dispatched separately by the dream loop's
MemDistill triad — Gate/Dispatch/Collect — which yields to the HR agent).
``compact()`` only consumes the pre-composed merge candidates that
identifier.py + the distill skill have already produced; it never invents
content. What compact() does mechanically:

  1. Run HealthChecker; no breach AND no pending candidates → empty report.
  2. Pull pending candidates from CandidatesArea.
  3. For each candidate, dispatch on its `kind`:
       - "merge_short_into_medium": rewrite an existing medium entry to
         absorb the listed short entries' bodies, then delete the source
         shorts. The candidate itself carries the pre-composed merged
         text (built by identifier/scan_for_promote_candidates upstream);
         this module never invents content.
       - "delete_short": delete a short entry that's been superseded.
       - "promote_candidate": leave in place (consumed by knowledge loop
         via parent facade scan; compact doesn't touch).
       - unknown kind: record as error and skip.
  4. Clear processed candidates from the work area.

Single-candidate failure is isolated — error recorded, loop continues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from memory.crud.backend import MemoryBackend
from memory.crud.file_backend import FileBackend
from memory.crud.primitives import MEDIUM, delete as _crud_delete, update as _crud_update

from .candidates import CandidatesArea
from .health import HealthChecker


@dataclass
class CompactionReport:
    candidates_processed: int = 0
    medium_entries_written: int = 0
    short_entries_deleted: int = 0
    errors: list[str] = field(default_factory=list)
    # Diagnostic-only fields (callers may ignore; mem_steps._report_to_dict
    # surfaces them onto bb for the dream report).
    skipped: int = 0
    health_breaches: list[str] = field(default_factory=list)


def compact(store_dir: Path, backend: MemoryBackend | None = None) -> CompactionReport:
    """Drive the candidates → medium merge pipeline.

    `backend` is optional; defaults to a FileBackend over the same
    `store_dir` so the CLI / scheduler callers (which pass only the store
    dir) keep working without a wiring change. Tests / advanced callers
    that want ChromaBackend can pass one in.
    """
    store_dir = Path(store_dir)
    report = CompactionReport()

    # Step 1 — Health gate. Skip the heavy path when nothing is wrong AND
    # the candidates queue is empty. (An empty queue with a breach still
    # means "nothing to do mechanically" — the breach is informational and
    # surfaces via report.health_breaches for the dream-report.)
    health = HealthChecker(store_dir).check()
    report.health_breaches = list(health.breaches)

    candidates_area = CandidatesArea(store_dir)
    pending = candidates_area.pull_pending()
    if not pending:
        return report

    if backend is None:
        backend = FileBackend(store_dir)

    processed_ids: list[str] = []

    # Step 2 — Mechanical dispatch per candidate. Each branch is isolated
    # in try/except so one rotten candidate doesn't poison the batch.
    for cand in pending:
        cand_id = cand.get("path") or cand.get("id") or "<unknown>"
        kind = (cand.get("kind") or cand.get("action") or "").strip()

        try:
            if kind == "merge_short_into_medium":
                wrote, deleted = _apply_merge(cand, store_dir, backend)
                report.medium_entries_written += wrote
                report.short_entries_deleted += deleted
                report.candidates_processed += 1
                processed_ids.append(cand_id)
            elif kind == "delete_short":
                deleted = _apply_delete_short(cand, backend)
                report.short_entries_deleted += deleted
                report.candidates_processed += 1
                processed_ids.append(cand_id)
            elif kind == "promote_candidate" or kind == "":
                # Promote candidates are owned by the knowledge loop; an
                # untagged candidate is a stub from the 4A identifier path
                # — leave it for now, don't drop on the floor.
                report.skipped += 1
            else:
                report.errors.append(f"unknown candidate kind '{kind}' on {cand_id}")
                report.skipped += 1
        except Exception as e:
            # Hard rule: never let one candidate kill the batch.
            report.errors.append(f"{cand_id}: {type(e).__name__}: {e}")
            report.skipped += 1

    # Step 3 — Clear what we actually consumed. Untouched candidates stay
    # so the next compact tick sees them again.
    if processed_ids:
        candidates_area.clear(processed_ids)

    return report


# ---------------------------------------------------------------------------
# Per-kind handlers — surgical, no semantic logic.
# ---------------------------------------------------------------------------

def _apply_merge(cand: dict, store_dir: Path, backend: MemoryBackend) -> tuple[int, int]:
    """Write a pre-composed medium entry and delete the listed sources.

    Candidate shape expected:
      {
        "kind": "merge_short_into_medium",
        "target_medium_path": "<absolute path under store_dir/medium/>",
        "target_medium_text": "<frontmatter + body markdown>",
        "source_short_paths": ["<absolute path>", ...],
      }

    The candidate carries the merged text verbatim — compact() does not
    compose, summarize, or rewrite. That stays the upstream identifier's
    (or LLM distill skill's) responsibility.
    """
    target = cand.get("target_medium_path")
    text = cand.get("target_medium_text")
    sources = cand.get("source_short_paths") or []
    if not target or text is None:
        raise ValueError("merge candidate missing target_medium_path / target_medium_text")

    target_path = Path(target)
    # Boundary: target must live inside store_dir/medium/. Drop anything else.
    medium_root = (Path(store_dir) / "medium").resolve()
    try:
        resolved = target_path.resolve()
    except OSError as e:
        raise ValueError(f"cannot resolve target {target}: {e}") from e
    if medium_root not in resolved.parents and resolved != medium_root:
        raise ValueError(f"target {target} outside medium/")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(text, encoding="utf-8")
    _crud_update(target_path, MEDIUM, backend)

    deleted = 0
    for s in sources:
        sp = Path(s)
        if not sp.exists():
            continue
        try:
            _crud_delete(sp, backend)
            sp.unlink(missing_ok=True)
            deleted += 1
        except Exception:
            # Bubble nothing — main loop logs at the candidate boundary.
            continue
    return 1, deleted


def _apply_delete_short(cand: dict, backend: MemoryBackend) -> int:
    """Delete a short entry already superseded elsewhere.

    Candidate shape:
      {"kind": "delete_short", "source_short_paths": ["<path>", ...]}
    """
    deleted = 0
    for s in cand.get("source_short_paths") or []:
        sp = Path(s)
        if not sp.exists():
            continue
        try:
            _crud_delete(sp, backend)
            sp.unlink(missing_ok=True)
            deleted += 1
        except Exception:
            continue
    return deleted
