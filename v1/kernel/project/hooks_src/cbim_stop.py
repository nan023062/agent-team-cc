#!/usr/bin/env python3
"""Stop hook — in-process bridge to kernel."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.event_io import read_event
from _lib.paths import project_root_from_cwd
from _lib.bridge import bootstrap_kernel, safe_run


def _distill(root: Path, transcript_path: str) -> None:
    cbim = root / ".cbim"
    from memory._config import load_config
    from memory.crud.file_backend import FileBackend
    from memory.crud.session_writer import write_session

    store_dir = cbim / "memory"
    backend = FileBackend(store_dir)
    cfg = load_config()
    write_session(transcript_path, store_dir, backend, cfg)


def _mark_idle(root: Path) -> None:
    cbim = root / ".cbim"
    cbim.mkdir(parents=True, exist_ok=True)
    (cbim / ".cc-status").write_text(
        f"idle {datetime.now().isoformat()}\n", encoding="utf-8"
    )


def _log_assist(root: Path, transcript_path: str) -> None:
    from engine.logger import log_assist
    log_assist(transcript_path, cbim=root / ".cbim")


def main() -> int:
    event = read_event()
    cwd = event.get("cwd") or "."
    transcript_path = event.get("transcript_path", "") or ""
    root = project_root_from_cwd(cwd)

    if not bootstrap_kernel(root):
        return 0

    if transcript_path:
        safe_run(lambda: _log_assist(root, transcript_path), on_error_label="stop.log_assist")
        safe_run(lambda: _distill(root, transcript_path), on_error_label="stop.distill")
    safe_run(lambda: _mark_idle(root), on_error_label="stop.mark_idle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
