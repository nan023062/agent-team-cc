"""
session_log.py — One log file per Claude Code session, all signal types interleaved.

Layout:
  .cbim/logs/session_<YYYY-MM-DD_HHMMSS>_<short-id>.log    one file per session
  .cbim/logs/.current                                       pointer to active session log

Signal tags written to the log:
  [SESSION]   SessionStart / SessionEnd boundaries
  [USER]      UserPromptSubmit — user spoke; assistant about to think
  [TOOL]      PreToolUse — tool call about to fire
  [RESULT]    PostToolUse — tool call returned (reflection point)
  [TURN]      Stop — assistant turn ended
  [ENG]       internal: engine CLI invocation
  [IMP]       internal: skill/soul module import

All log writers go through this module to guarantee one-file-per-session output.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def cbim_root_from_cwd() -> Path | None:
    """Walk up from cwd to find a .cbim/ directory."""
    p = Path.cwd().resolve()
    for _ in range(6):
        if (p / ".cbim").is_dir():
            return p / ".cbim"
        if p.parent == p:
            break
        p = p.parent
    return None


def logs_dir(cbim: Path | None = None) -> Path:
    """Return .cbim/logs/, creating it if missing."""
    cbim = cbim or cbim_root_from_cwd() or Path(__file__).resolve().parent.parent
    d = cbim / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pointer_path(cbim: Path | None = None) -> Path:
    return logs_dir(cbim) / ".current"


def current_log_path(cbim: Path | None = None) -> Path | None:
    """Return the active session log file, or the most recent session log if no pointer."""
    pointer = _pointer_path(cbim)
    if pointer.exists():
        try:
            target = Path(pointer.read_text(encoding="utf-8").strip())
            if target.exists():
                return target
        except OSError:
            pass
    # Fallback: pick the most recent session_*.log
    candidates = sorted(logs_dir(cbim).glob("session_*.log"))
    return candidates[-1] if candidates else None


def start_session(session_id: str = "", cwd: str = "", cbim: Path | None = None) -> Path:
    """Create a new session log file, write the pointer, log the SESSION-START line.

    Returns the new log file path.
    """
    cbim = cbim or cbim_root_from_cwd() or Path(__file__).resolve().parent.parent
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    short = (session_id or "anon").replace("/", "_").replace("\\", "_")[:8]
    log_path = logs_dir(cbim) / f"session_{ts}_{short}.log"
    log_path.touch(exist_ok=True)
    _pointer_path(cbim).write_text(str(log_path), encoding="utf-8")
    append("SESSION", f"start session_id={session_id or '?'} cwd={cwd or os.getcwd()}", cbim=cbim, log_path=log_path)
    return log_path


def append(tag: str, message: str, cbim: Path | None = None, log_path: Path | None = None) -> None:
    """Append a timestamped line to the current session log.

    If no session log exists yet (no SessionStart has fired), creates an
    'orphan' session log on the fly so messages aren't lost.
    """
    try:
        cbim = cbim or cbim_root_from_cwd() or Path(__file__).resolve().parent.parent
        path = log_path or current_log_path(cbim)
        if path is None:
            # Orphan messages: create a synthetic session
            path = start_session(session_id="orphan", cwd=os.getcwd(), cbim=cbim)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{tag}] {message}\n")
    except Exception:
        # Logging must never break the host
        pass
