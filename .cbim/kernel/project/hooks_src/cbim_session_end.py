#!/usr/bin/env python3
"""SessionEnd hook — in-process bridge to kernel."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.event_io import read_event
from _lib.paths import project_root_from_cwd
from _lib.bridge import bootstrap_kernel, safe_run


def _finalize(root: Path, session_id: str, reason: str) -> None:
    from engine.logger import end_session
    end_session(session_id=session_id, reason=reason, cbim=root / ".cbim")


def main() -> int:
    event = read_event()
    cwd = event.get("cwd") or "."
    session_id = event.get("session_id", "") or ""
    reason = event.get("reason", "") or "unknown"
    root = project_root_from_cwd(cwd)

    if not bootstrap_kernel(root):
        return 0

    safe_run(
        lambda: _finalize(root, session_id, reason),
        on_error_label="session_end",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
