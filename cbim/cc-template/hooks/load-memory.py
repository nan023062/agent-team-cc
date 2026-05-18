"""
load-memory.py — SessionStart hook.

Receives session-start event from Claude Code and delegates to the memory engine.
Contains no memory logic — that lives in memory/engine/loader.py.
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

    cwd = Path(event.get("cwd", os.getcwd()))

    python = _find_python(cwd)
    if not python:
        sys.exit(0)

    # Run with cwd=cbim/ so `memory` package is importable as memory.engine.cli
    result = subprocess.run(
        [python, "-m", "memory.engine.cli", "load-context"],
        capture_output=True,
        text=True,
        cwd=str(cwd / "cbim"),
        timeout=60,
        check=False,
    )

    if result.stdout.strip():
        print(result.stdout.strip())

    sys.exit(0)


if __name__ == "__main__":
    main()
