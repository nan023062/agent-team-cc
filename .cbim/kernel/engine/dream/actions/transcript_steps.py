"""actions/transcript_steps.py — transcript-driven memory governance leaves.

v2 records: the memory governance step's distill input shifted from
``.cbim/memory/short/`` (the long-deprecated short tier) to Claude
Code's per-project transcript JSONL files under
``~/.claude/projects/<slug>/*.jsonl``. This module provides the three
new pure-Python leaves that surround the existing DispatchMemDistill /
CollectMemDistill yield triad:

  TranscriptScan      — scans ~/.claude/projects/<slug>/*.jsonl, picks
                        files older than 1 day; writes bb.transcript_paths.
  DistillGate         — non-empty paths → SUCCESS (continue to dispatch);
                        empty → SKIP (write bb.mem_distill_result, mark
                        bb.mem_distill_dispatched=False so the dispatch /
                        collect / delete leaves all no-op through).
  TranscriptDelete    — for every path in bb.mem_distill_result["distilled_paths"]:
                        call engine.retrieval.index_delete("transcript", doc_id)
                        and unlink the .jsonl. Errors accumulate in
                        bb.transcript_delete_errors; never aborts.

These replace the v1 ``MemDistillGate`` semantics (which read
``mem_health.short_count`` against a hard threshold). The v2 gate is a
pure data-volume check on the scan result — if there's nothing to
distill, skip; otherwise distill.

Slug computation is shared via ``memory._lib.paths.cc_transcripts_dir`` —
the same helper backs the cbim_stop / cbim_session_start hooks.
"""

from __future__ import annotations

import time
from pathlib import Path

from engine.core.node import Node, Status
from memory._lib.paths import cc_transcripts_dir


# 1 day = 86400s. Transcripts younger than this stay live (the user
# might still be writing into them; distilling a hot session would lose
# the tail).
_MIN_AGE_SECONDS = 86400


# ---------------------------------------------------------------------------
# TranscriptScan
# ---------------------------------------------------------------------------


class TranscriptScan(Node):
    """Scan ~/.claude/projects/<slug>/*.jsonl, pick files older than 1 day.

    Writes ``bb.transcript_paths`` = list[str] (absolute paths sorted by
    mtime ascending — oldest first, so distill consumes the riskiest
    backlog first). Empty list when the directory doesn't exist or no
    file is mature yet. Never fails (the dream loop is tolerant; a
    missing transcripts dir is not an error condition).

    Constructor args:
      transcripts_dir   — explicit scan directory. None → resolve to
                          ~/.claude/projects/<slug>/ against process CWD
                          (production path). Tests pass a tmp dir to
                          keep the scan hermetic.
      cwd_override      — only consulted when transcripts_dir is None.
                          Test seam for the slug-derivation path.
    """

    def __init__(self, *, transcripts_dir: Path | None = None,
                 cwd_override: Path | None = None,
                 min_age_seconds: int = _MIN_AGE_SECONDS,
                 name: str = "TranscriptScan") -> None:
        self.name = name
        self._transcripts_dir = transcripts_dir
        self._cwd_override = cwd_override
        self._min_age_seconds = min_age_seconds

    def tick(self, bb) -> Status:
        scan_dir = self._transcripts_dir or cc_transcripts_dir(self._cwd_override)
        paths: list[tuple[float, str]] = []
        if scan_dir.exists() and scan_dir.is_dir():
            now = time.time()
            for p in scan_dir.glob("*.jsonl"):
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    continue
                if (now - mtime) >= self._min_age_seconds:
                    paths.append((mtime, str(p)))
        paths.sort(key=lambda t: t[0])
        bb.transcript_paths = [p for _, p in paths]
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# DistillGate
# ---------------------------------------------------------------------------


class DistillGate(Node):
    """Volume gate on bb.transcript_paths.

    Sets bb.mem_distill_dispatched so the downstream Dispatch / Collect /
    Delete leaves see the same routing flag the v1 ``MemDistillGate``
    used. On skip, pre-populates ``bb.mem_distill_result`` with the skip
    reason — EmitReport / TranscriptDelete then no-op through it.
    """

    def __init__(self, *, name: str = "DistillGate") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        paths = bb.transcript_paths or []
        if not paths:
            bb.mem_distill_dispatched = False
            bb.mem_distill_result = {
                "skipped": True,
                "reason": "no_mature_transcripts",
            }
            return Status.SUCCESS
        bb.mem_distill_dispatched = True
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# TranscriptDelete
# ---------------------------------------------------------------------------


class TranscriptDelete(Node):
    """Delete the transcripts the distill skill reported as digested.

    Inputs: ``bb.mem_distill_result["distilled_paths"]`` written by
    ``CollectMemDistill``. For each:

      1. Try ``engine.retrieval.index_delete("transcript", doc_id)`` — the
         doc_id is the absolute path (the same string the retrieval index
         would have keyed on if the transcript was ever indexed). The
         retrieval contract makes index_delete idempotent, so calling on
         a never-indexed path is a no-op.
      2. ``Path(p).unlink()`` — the file might already be gone if a
         prior run partially succeeded; FileNotFoundError is swallowed.

    Errors accumulate in ``bb.transcript_delete_errors`` (a list of
    ``{path, stage, error}`` dicts). Never aborts; never fails the
    sequence — the v1 MemoryGovernanceStep treats single-leaf
    in-process errors as soft failures and continues.
    """

    def __init__(self, *, name: str = "TranscriptDelete") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        bb.transcript_delete_errors = []

        # Skip path: gate decided no distill happened, or the dispatch
        # was never collected. Nothing to delete.
        if not bb.mem_distill_dispatched:
            return Status.SUCCESS
        result = bb.mem_distill_result or {}
        if not isinstance(result, dict):
            return Status.SUCCESS
        if result.get("skipped"):
            return Status.SUCCESS
        if result.get("error") and not result.get("distilled_paths"):
            # Collect surfaced a parse error — don't touch transcripts.
            return Status.SUCCESS

        distilled = result.get("distilled_paths") or []
        if not isinstance(distilled, list) or not distilled:
            return Status.SUCCESS

        errors: list[dict] = []
        try:
            from engine.retrieval import index_delete
        except Exception:
            index_delete = None  # type: ignore[assignment]

        for raw in distilled:
            if not isinstance(raw, str) or not raw:
                continue
            p = Path(raw)

            if index_delete is not None:
                try:
                    index_delete("transcript", str(p))
                except Exception as e:
                    errors.append({
                        "path": str(p),
                        "stage": "index_delete",
                        "error": f"{type(e).__name__}: {e}",
                    })
            try:
                p.unlink()
            except FileNotFoundError:
                # Already gone — idempotent re-run path.
                pass
            except OSError as e:
                errors.append({
                    "path": str(p),
                    "stage": "unlink",
                    "error": f"{type(e).__name__}: {e}",
                })

        bb.transcript_delete_errors = errors
        return Status.SUCCESS
