"""
write_memory.py — Stop hook (fires at end of each assistant turn).

  1. Logs [ASSIST] — the assistant's last text response (from transcript JSONL)
  2. Marks .cc-status as idle so the scheduler may fire idle-sensitive tasks
  3. Delegates memory distillation to the memory engine
"""

import json
import subprocess
import sys
from pathlib import Path

from cbim_kernel.context import cbim_dir, project_root


def _find_python() -> str:
    for root in [project_root(), cbim_dir()]:
        for candidate in [
            root / ".venv" / "Scripts" / "python.exe",
            root / ".venv" / "bin" / "python",
        ]:
            if candidate.exists():
                return str(candidate)
    return sys.executable


def _mark_idle() -> None:
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

    transcript_path = event.get("transcript_path", "")

    # Log the assistant's last text response
    if transcript_path:
        try:
            from cbim_kernel.engine.logger import log_assist
            log_assist(transcript_path, cbim=cbim_dir())
        except Exception:
            pass

    _mark_idle()

    if not transcript_path:
        return 0

    subprocess.run(
        [_find_python(), "-m", "cbim_kernel", "memory", "write-session", transcript_path],
        cwd=str(project_root()),
        timeout=60,
        check=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
