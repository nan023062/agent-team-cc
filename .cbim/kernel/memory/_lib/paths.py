"""
memory/_lib/paths.py — Claude Code transcript path helpers.

Cross-cutting helpers used by:
  - .claude/hooks/cbim_stop.py            (resolve transcript file at session end)
  - .claude/hooks/cbim_session_start.py   (catch-up scan at session start)
  - engine/dream/actions/transcript_steps (governance loop scan)

Claude Code stores per-project transcripts under
``~/.claude/projects/<slug>/<session_id>.jsonl`` where ``<slug>`` is derived
from the project's absolute path by replacing the three separator characters
``':'``, ``'\\'``, ``'/'`` with ``'-'`` and leaving every other character
intact. The rule is the same on Windows and POSIX — only the input path
shape differs.

stdlib only. No cbim.* imports; safe to import from hook subprocesses.
"""

from __future__ import annotations

from pathlib import Path


def cc_project_slug(cwd: Path | str) -> str:
    """Return Claude Code's ``projects/<slug>`` segment for the given directory.

    The slug is ``str(cwd)`` with ``':'``, ``'\\'`` and ``'/'`` each replaced
    by ``'-'``. Every other character is preserved verbatim (Claude Code
    does not escape, lowercase, or hash anything else).

    Does **not** call ``Path.resolve()`` — that's the caller's responsibility
    when needed. Keeping resolution out preserves cross-platform test
    predictability: a literal POSIX path like ``/home/x`` slugs the same
    on Windows test runs as on the Linux production box.
    """
    s = str(cwd)
    out = []
    for ch in s:
        out.append("-" if ch in (":", "\\", "/") else ch)
    return "".join(out)


def cc_transcripts_dir(cwd: Path | str | None = None) -> Path:
    """Return ``~/.claude/projects/<slug>/`` for the given (or current) cwd.

    Resolves ``cwd`` to its absolute form before slugging — production
    callers (hooks, dream loop) expect the absolute project root to drive
    the slug. Pass an already-resolved path to skip the resolve step.

    Returns the path unconditionally; callers that need existence checks
    should test ``.is_dir()`` themselves.
    """
    base = Path(cwd) if cwd is not None else Path.cwd()
    return Path.home() / ".claude" / "projects" / cc_project_slug(base.resolve())
