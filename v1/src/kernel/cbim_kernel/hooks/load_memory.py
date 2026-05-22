"""
load_memory.py — SessionStart hook.

Receives session-start event from Claude Code and:
  1. Opens a new per-session log file under .cbim/logs/session_*.log
  2. Loads recent memory context (in-process via memory.engine.loader.load_context)
  3. Generates project knowledge snapshot (in-process via cbi._primitives.snapshot.build_snapshot)
Merges both into a single additionalContext JSON block.
"""

import json
import os
import sys
from pathlib import Path

from cbim_kernel.context import cbim_dir, project_root
from updater.upgrade.notify import session_start_line


def _start_session_log(session_id: str, cwd: str) -> None:
    """Open a fresh session log via session_log.start_session()."""
    try:
        from cbim_kernel.engine.session_log import start_session
        start_session(session_id=session_id, cwd=cwd, cbim=cbim_dir())
    except Exception:
        pass


def _load_memory_context() -> str:
    """In-process equivalent of the former `cbim memory load-context`.

    Returns the JSON-wrapped additionalContext payload (str) or "" on
    nothing-to-show / any error.
    """
    try:
        from cbim_kernel.memory.engine.config import load_config
        from cbim_kernel.memory.engine.engine import MemoryEngine
        from cbim_kernel.memory.engine.file_backend import FileBackend
        from cbim_kernel.memory.engine.loader import load_context

        store_dir = cbim_dir() / "memory"
        engine = MemoryEngine(backend=FileBackend(store_dir), store_dir=store_dir)
        cfg = load_config()
        return load_context(store_dir, engine, cfg) or ""
    except Exception:
        return ""


def _build_snapshot(root: Path) -> str:
    """In-process equivalent of the former `cbim snapshot --root <root>`."""
    try:
        from cbim_kernel.cbi._primitives.snapshot import build_snapshot
        return build_snapshot(Path(root).resolve()) or ""
    except Exception:
        return ""


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

    _start_session_log(session_id, str(cwd))

    # 1. Memory context (JSON-wrapped additionalContext payload)
    memory_out = _load_memory_context()

    # 2. Project knowledge snapshot
    snapshot_out = _build_snapshot(cwd)

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
