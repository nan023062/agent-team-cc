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


def _cbim_root() -> Path:
    """cc-template/hooks/ -> cc-template/ -> cbim root"""
    return Path(__file__).resolve().parent.parent.parent


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


def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = event.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    cbim = _cbim_root()
    python = _find_python()

    subprocess.run(
        [python, "-m", "memory.engine.cli", "write-session", transcript_path],
        cwd=str(cbim),
        timeout=60,
        check=False,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
