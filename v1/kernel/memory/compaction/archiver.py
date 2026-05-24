"""
compaction/archiver.py — `sweep_expired()` (replaces legacy cleanup_short).

Phase 4A: moved out of the legacy cleanup_short path. Same semantics:
- Walk short/ for entries whose filename date is older than keep_days.
- Skip entries that lack a `distilled: <date>` frontmatter marker (those
  are still pending distillation and must not be silently dropped).
- Delete the rest through crud.primitives.delete (compaction does NOT
  hold direct file-write permission on short/ or medium/).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from memory.crud.backend import MemoryBackend
from memory.crud.primitives import delete as _crud_delete


def sweep_expired(store_dir: Path, backend: MemoryBackend,
                  keep_days: int = 3) -> int:
    """Delete short-term entries that are distilled AND older than keep_days.

    Returns count of deleted files. Undistilled entries are never touched —
    they stay until explicitly processed.
    """
    cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d")
    short_dir = Path(store_dir) / "short"
    if not short_dir.exists():
        return 0

    deleted = 0
    for md_file in sorted(short_dir.glob("*.md")):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", md_file.name)
        if not m or m.group(1) >= cutoff:
            continue
        try:
            raw = md_file.read_text(encoding="utf-8")
            if not re.search(r"^distilled:\s*\S", raw, re.MULTILINE):
                continue  # not yet distilled — skip
        except (FileNotFoundError, PermissionError):
            continue
        try:
            _crud_delete(md_file, backend)
        except Exception:
            pass
        deleted += 1
    return deleted
