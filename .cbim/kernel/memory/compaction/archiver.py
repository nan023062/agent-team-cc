"""
compaction/archiver.py — `sweep_expired()` for stale work-area candidates.

v2: short tier removed. The v1 sweep target (distilled + aged short entries)
no longer exists. This module now sweeps stale candidate stubs from the
work area — candidates whose mtime is older than `keep_days` and that the
knowledge loop never picked up.

medium/ entries are never auto-archived: long-lived knowledge is the whole
point of the tier; lifecycle decisions there are explicit (human or LLM-
driven via memory_distill), not time-based.
"""

from __future__ import annotations

import time
from pathlib import Path

from memory.crud.backend import MemoryBackend

_DAY_SECONDS = 86400


def sweep_expired(store_dir: Path, backend: MemoryBackend,
                  keep_days: int = 30) -> int:
    """Delete candidate stubs older than `keep_days`.

    Returns count of deleted candidate files. The `backend` arg is kept for
    signature parity with v1 callers (CLI / services); candidates are not
    indexed in the backend, so the backend itself isn't touched.
    """
    from .candidates import CANDIDATES_SUBDIR

    cand_dir = Path(store_dir) / CANDIDATES_SUBDIR
    if not cand_dir.exists():
        return 0

    cutoff = time.time() - (keep_days * _DAY_SECONDS)
    deleted = 0
    for f in sorted(cand_dir.glob("*.candidate.json")):
        try:
            st = f.stat()
        except OSError:
            continue
        if st.st_mtime >= cutoff:
            continue
        try:
            f.unlink()
            deleted += 1
        except OSError:
            continue
    return deleted
