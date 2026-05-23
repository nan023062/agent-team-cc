#!/usr/bin/env python3
"""PostToolUse hook — in-process bridge to kernel."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.event_io import read_event
from _lib.paths import project_root_from_cwd
from _lib.bridge import bootstrap_kernel, safe_run


def _log_post(root: Path, tool: str, inp: dict, response: dict, transcript_path: str) -> None:
    from engine.logger import log_ret
    log_ret(tool, inp, response, cbim=root / ".cbim", transcript_path=transcript_path)


def main() -> int:
    event = read_event()
    cwd = event.get("cwd") or "."
    tool = event.get("tool_name", "?") or "?"
    tool_input = event.get("tool_input", {}) or {}
    tool_response = event.get("tool_response", {}) or {}
    transcript_path = event.get("transcript_path", "") or ""
    root = project_root_from_cwd(cwd)

    if not bootstrap_kernel(root):
        return 0

    safe_run(
        lambda: _log_post(root, tool, tool_input, tool_response, transcript_path),
        on_error_label="post_tool_use",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
