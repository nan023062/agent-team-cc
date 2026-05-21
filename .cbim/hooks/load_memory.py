"""
load_memory.py — SessionStart hook.

Receives session-start event from Claude Code and:
  1. Opens a new per-session log file under .cbim/logs/session_*.log
  2. Loads recent memory context  (python .cbim/engine memory load-context)
  3. Generates project knowledge snapshot  (python .cbim/engine snapshot)
Merges both into a single additionalContext JSON block.
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
        sys.path.insert(0, str(_cbim_root()))
        from engine.session_log import start_session
        start_session(session_id=session_id, cwd=cwd, cbim=_cbim_root())
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

    cwd = Path(event.get("cwd", os.getcwd()))
    session_id = event.get("session_id", "")
    cbim = _cbim_root()
    python = _find_python()

    _start_session_log(session_id, str(cwd))

    # 1. Memory context
    memory_out = _run(
        python,
        ["-m", "engine", "memory", "load-context"],
        str(cbim),
    )

    # 2. Project knowledge snapshot
    snapshot_out = _run(
        python,
        ["-m", "engine", "snapshot", "--root", str(cwd)],
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

    sys.stdout.buffer.write(json.dumps({"additionalContext": combined}, ensure_ascii=False).encode("utf-8") + b"\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
