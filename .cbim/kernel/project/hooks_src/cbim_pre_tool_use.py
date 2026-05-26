#!/usr/bin/env python3
"""PreToolUse hook — in-process bridge to kernel."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.event_io import read_event
from _lib.paths import project_root_from_cwd
from _lib.bridge import bootstrap_kernel, safe_run


def _log_pre(root: Path, tool: str, inp: dict, transcript_path: str) -> None:
    from engine.logger import log_call
    log_call(tool, inp, cbim=root / ".cbim", transcript_path=transcript_path)


def main() -> int:
    event = read_event()
    cwd = event.get("cwd") or "."
    tool = event.get("tool_name", "?") or "?"
    tool_input = event.get("tool_input", {}) or {}
    transcript_path = event.get("transcript_path", "") or ""
    root = project_root_from_cwd(cwd)

    if not bootstrap_kernel(root):
        return 0

    safe_run(
        lambda: _log_pre(root, tool, tool_input, transcript_path),
        on_error_label="pre_tool_use",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
