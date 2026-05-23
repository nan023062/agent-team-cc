#!/usr/bin/env python3
"""UserPromptSubmit hook — in-process bridge to kernel."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.event_io import read_event
from _lib.paths import project_root_from_cwd
from _lib.bridge import bootstrap_kernel, safe_run


def _mark_busy(root: Path) -> None:
    cbim = root / ".cbim"
    cbim.mkdir(parents=True, exist_ok=True)
    (cbim / ".cc-status").write_text(
        f"busy {datetime.now().isoformat()}\n", encoding="utf-8"
    )


def _log_user(root: Path, prompt: str, transcript_path: str) -> None:
    from engine.logger import log_user
    log_user(prompt, cbim=root / ".cbim", transcript_path=transcript_path)


def main() -> int:
    event = read_event()
    cwd = event.get("cwd") or "."
    prompt = event.get("prompt", "") or ""
    transcript_path = event.get("transcript_path", "") or ""
    root = project_root_from_cwd(cwd)

    if not bootstrap_kernel(root):
        return 0

    safe_run(lambda: _mark_busy(root), on_error_label="user_prompt.mark_busy")
    safe_run(
        lambda: _log_user(root, prompt, transcript_path),
        on_error_label="user_prompt.log_user",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
