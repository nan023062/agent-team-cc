"""
write_memory.py — Stop hook (fires at end of each assistant turn).

  1. Logs [ASSIST] — the assistant's last text response (from transcript JSONL)
  2. Marks .cc-status as idle so the scheduler may fire idle-sensitive tasks
  3. Writes a short-term memory entry from the transcript (in-process — no
     subprocess hop into a CLI)
"""

import json
import sys
from pathlib import Path

from cbim_kernel.context import cbim_dir


def _mark_idle() -> None:
    try:
        from datetime import datetime
        (cbim_dir() / ".cc-status").write_text(
            f"idle {datetime.now().isoformat()}\n", encoding="utf-8"
        )
    except Exception:
        pass


def _write_session_entry(transcript_path: str) -> None:
    """In-process equivalent of the former `cbim memory write-session`.

    Mirrors memory/engine/cli.py:cmd_write_session: build the default
    FileBackend-backed engine pointed at <project>/.cbim/memory/, then hand
    the transcript to writer.write_session.
    """
    try:
        from cbim_kernel.memory.engine.config import load_config
        from cbim_kernel.memory.engine.engine import MemoryEngine
        from cbim_kernel.memory.engine.file_backend import FileBackend
        from cbim_kernel.memory.engine.writer import write_session

        store_dir = cbim_dir() / "memory"
        engine = MemoryEngine(backend=FileBackend(store_dir), store_dir=store_dir)
        cfg = load_config()
        path = write_session(transcript_path, store_dir, engine, cfg)
        if path:
            print(f"[memory] wrote {path.name}", file=sys.stderr)
    except Exception as e:
        # Hooks must never break the assistant turn. Swallow but surface
        # the reason on stderr for debuggability.
        print(f"[memory] write_session failed: {e}", file=sys.stderr)


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

    _write_session_entry(transcript_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
