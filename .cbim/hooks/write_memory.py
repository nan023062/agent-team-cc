"""
write_memory.py — Stop hook (fires at end of each assistant turn).

  1. Appends a [TURN] end marker to the per-session log
  2. Delegates the actual memory write to the memory engine
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def _cbim_root() -> Path:
    """hooks/ -> .cbim/ (cbim root)"""
    return Path(__file__).resolve().parent.parent


def _find_python() -> str:
    """Look for .venv in cbim root then parent (project root); fall back to sys.executable."""
    cbim = _cbim_root()
    for root in [cbim, cbim.parent]:
        for candidate in [
            root / ".venv" / "Scripts" / "python.exe",
            root / ".venv" / "bin" / "python",
        ]:
            if candidate.exists():
                return str(candidate)
    return sys.executable


def _log_turn_end(stop_reason: str) -> None:
    try:
        sys.path.insert(0, str(_cbim_root()))
        from engine.session_log import append
        append("TURN", f"end reason={stop_reason or '?'}", cbim=_cbim_root())
    except Exception:
        pass


def _mark_idle() -> None:
    """Tell the scheduler CC is idle now — opt-in tasks may fire."""
    try:
        from datetime import datetime
        (_cbim_root() / ".cc-status").write_text(
            f"idle {datetime.now().isoformat()}\n", encoding="utf-8"
        )
    except Exception:
        pass


def main() -> None:
    raw = sys.stdin.buffer.read().decode("utf-8").strip()
    if not raw:
        sys.exit(0)

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    _log_turn_end(event.get("stop_hook_active", "") or event.get("reason", ""))
    _mark_idle()

    transcript_path = event.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    cbim = _cbim_root()
    python = _find_python()

    subprocess.run(
        [python, "-m", "engine", "memory", "write-session", transcript_path],
        cwd=str(cbim),
        timeout=60,
        check=False,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
