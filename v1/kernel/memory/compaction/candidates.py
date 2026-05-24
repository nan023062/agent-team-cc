"""
compaction/candidates.py — Candidates work-area (independent path).

Phase 4A: implements the G3 decision (DNA module.md, Key Decision #1):
candidates/ is NOT a third storage tier; it is the compaction module's
private scratch space. Path is hard-coded here so no other layer can
accidentally repoint it.

Layout:
  <project>/.cbim/memory/candidates/      # this module's exclusive work area
"""

from __future__ import annotations

import json
from pathlib import Path

# Hard-coded relative path. Resolved against a `store_dir` passed in by
# the caller (typically `<project>/.cbim/memory/`). Do NOT thread this
# through config — G3 keeps the path stable.
CANDIDATES_SUBDIR = "candidates"


class CandidatesArea:
    """The candidates/ work-area handle.

    4A scope: stage / pull_pending / clear shapes are stubbed; the on-disk
    layout is "one .json per entry" so external scans (e.g. parent
    facade's `scan(filter='promote_candidate')`) can read without any
    library code. compact() proper lands in 4B.
    """

    def __init__(self, store_dir: Path) -> None:
        self._dir = Path(store_dir) / CANDIDATES_SUBDIR

    @property
    def path(self) -> Path:
        return self._dir

    def ensure(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def stage(self, entry: dict) -> None:
        """Drop a candidate into the work area. Idempotent on 'path' key.

        4A skeleton: write the raw entry dict as JSON for inspection;
        4B will define the real on-disk schema (frontmatter + body).
        """
        self.ensure()
        key = entry.get("path") or entry.get("id") or "unknown"
        safe = key.replace("/", "_").replace("\\", "_")
        out = self._dir / f"{safe}.candidate.json"
        out.write_text(
            json.dumps(entry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def pull_pending(self) -> list[dict]:
        """Return every staged candidate (4A: best-effort JSON load)."""
        if not self._dir.exists():
            return []
        out: list[dict] = []
        for f in sorted(self._dir.glob("*.candidate.json")):
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return out

    def clear(self, ids: list[str]) -> None:
        for i in ids:
            safe = i.replace("/", "_").replace("\\", "_")
            p = self._dir / f"{safe}.candidate.json"
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass

    def count(self) -> int:
        if not self._dir.exists():
            return 0
        return sum(1 for _ in self._dir.glob("*.candidate.json"))

    def disk_bytes(self) -> int:
        if not self._dir.exists():
            return 0
        total = 0
        for f in self._dir.glob("*.candidate.json"):
            try:
                total += f.stat().st_size
            except OSError:
                continue
        return total
