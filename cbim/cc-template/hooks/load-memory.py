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
    cbim = _cbim_root()
    python = _find_python()

    # 1. Memory context
    memory_out = _run(
        python,
        ["-m", "memory.engine.cli", "load-context"],
        str(cbim),
    )

    # 2. Project knowledge snapshot
    snapshot_out = _run(
        python,
        ["-m", "knowledge.engine.snapshot", "--root", str(cwd)],
        str(cbim),
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
