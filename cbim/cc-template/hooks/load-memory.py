"""
load-memory.py — SessionStart hook.

Receives session-start event from Claude Code and:
  1. Loads recent memory context (memory.engine.cli load-context)
  2. Generates project knowledge snapshot (knowledge.engine.snapshot)
Merges both into a single additionalContext JSON block.
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


def _run(python: str, args: list[str], cwd: str) -> str:
    try:
        result = subprocess.run(
            [python] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=60,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


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

    # 1. Memory context (cwd=cbim/ so `memory` package is importable)
    memory_out = _run(
        python,
        ["-m", "memory.engine.cli", "load-context"],
        str(cwd / "cbim"),
    )

    # 2. Project knowledge snapshot (cwd=cbim/ so `knowledge` package is importable)
    snapshot_out = _run(
        python,
        ["-m", "knowledge.engine.snapshot", "--root", str(cwd)],
        str(cwd / "cbim"),
    )

    parts = [p for p in [snapshot_out, memory_out] if p]
    if not parts:
        sys.exit(0)

    combined = "\n\n---\n\n".join(parts)

    # Extract memory additionalContext text if already JSON-wrapped
    if memory_out.startswith("{"):
        try:
            mem_data = json.loads(memory_out)
            mem_text = mem_data.get("additionalContext", memory_out)
            parts = [p for p in [snapshot_out, mem_text] if p]
            combined = "\n\n---\n\n".join(parts)
        except json.JSONDecodeError:
            pass

    print(json.dumps({"additionalContext": combined}, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
