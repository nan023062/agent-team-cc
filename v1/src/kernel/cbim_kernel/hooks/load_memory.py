"""
load_memory.py — SessionStart hook.

Receives session-start event from Claude Code and:
  1. Opens a new per-session log file under .cbim/logs/session_*.log
  2. Loads recent memory context  (python -m cbim_kernel memory load-context)
  3. Generates project knowledge snapshot  (python -m cbim_kernel snapshot)
Merges both into a single additionalContext JSON block.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from cbim_kernel.context import cbim_dir, project_root
from updater.upgrade.notify import session_start_line


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


def _run(python: str, args: list[str], cwd: str) -> str:
    try:
        result = subprocess.run(
            [python] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            timeout=60,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _start_session_log(session_id: str, cwd: str) -> None:
    """Open a fresh session log via session_log.start_session()."""
    try:
        from cbim_kernel.engine.session_log import start_session
        start_session(session_id=session_id, cwd=cwd, cbim=cbim_dir())
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

    cwd = Path(event.get("cwd", os.getcwd()))
    session_id = event.get("session_id", "")
    python = _find_python()

    _start_session_log(session_id, str(cwd))

    # 1. Memory context
    memory_out = _run(
        python,
        ["-m", "cbim_kernel", "memory", "load-context"],
        str(project_root()),
    )

    # 2. Project knowledge snapshot
    snapshot_out = _run(
        python,
        ["-m", "cbim_kernel", "snapshot", "--root", str(cwd)],
        str(project_root()),
    )

    # Upgrade banner
    try:
        banner = session_start_line(project_root())
    except Exception:
        banner = None

    parts = [p for p in [banner, snapshot_out, memory_out] if p]
    if not parts:
        return 0

    combined = "\n\n---\n\n".join(parts)

    # Extract memory additionalContext text if already JSON-wrapped
    if memory_out.startswith("{"):
        try:
            mem_data = json.loads(memory_out)
            mem_text = mem_data.get("additionalContext", memory_out)
            parts = [p for p in [banner, snapshot_out, mem_text] if p]
            combined = "\n\n---\n\n".join(parts)
        except json.JSONDecodeError:
            pass

    sys.stdout.buffer.write(json.dumps({"additionalContext": combined}, ensure_ascii=False).encode("utf-8") + b"\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
