"""
write_memory.py — Stop hook (fires at end of each assistant turn).

  1. Appends a [TURN] end marker to the per-session log
  2. Delegates the actual memory write to the memory engine
"""

import json
import subprocess
import sys
from pathlib import Path

from cbim_kernel.context import cbim_dir, project_root


def _find_python() -> str:
    """Look for .venv in project root then cbim dir; fall back to sys.executable."""
    for root in [project_root(), cbim_dir()]:
        for candidate in [
            root / ".venv" / "Scripts" / "python.exe",
            root / ".venv" / "bin" / "python",
        ]:
            if candidate.exists():
                return str(candidate)
    return sys.executable


def _log_turn_end(stop_reason: str) -> None:
    try:
        from cbim_kernel.engine.session_log import append
        append("TURN", f"end reason={stop_reason or '?'}", cbim=cbim_dir())
    except Exception:
        pass


def _mark_idle() -> None:
    """Tell the scheduler CC is idle now — opt-in tasks may fire."""
    try:
        from datetime import datetime
        (cbim_dir() / ".cc-status").write_text(
            f"idle {datetime.now().isoformat()}\n", encoding="utf-8"
        )
    except Exception:
        pass


def main(event: dict | None = None) -> int:
    if event is None:
        raw = sys.stdin.buffer.read().decode("utf-8").strip()
        if not raw:
            return 0
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return 0

    _log_turn_end(event.get("stop_hook_active", "") or event.get("reason", ""))
    _mark_idle()

    transcript_path = event.get("transcript_path", "")
    if not transcript_path:
        return 0

    python = _find_python()

    subprocess.run(
        [python, "-m", "cbim_kernel", "memory", "write-session", transcript_path],
        cwd=str(project_root()),
        timeout=60,
        check=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
