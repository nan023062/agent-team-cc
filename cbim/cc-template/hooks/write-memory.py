"""
write-memory.py — Stop hook.

Receives session-end event from Claude Code and delegates to the memory engine.
Contains no memory logic — that lives in memory/engine/writer.py.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def _find_python(cwd: Path) -> str | None:
    for candidate in [
        cwd / ".venv" / "bin" / "python",
        cwd / ".venv" / "Scripts" / "python.exe",
    ]:
        if candidate.exists():
            return str(candidate)
    return None


def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = event.get("transcript_path", "")
    cwd = Path(event.get("cwd", os.getcwd()))

    if not transcript_path:
        sys.exit(0)

    python = _find_python(cwd)
    if not python:
        sys.exit(0)

    # Run with cwd=cbim/ so `memory` package is importable as memory.engine.cli
    subprocess.run(
        [python, "-m", "memory.engine.cli", "write-session", transcript_path],
        cwd=str(cwd / "cbim"),
        timeout=60,
        check=False,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
