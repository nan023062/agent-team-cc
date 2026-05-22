"""
log_post_tool.py — PostToolUse hook.

Logs a [RET] preview for every tool result to the session log.
  [RET]        Regular tools — status + content preview (300 chars)
  [RET:domain] CBIM bash results — matched to the corresponding [CBIM:domain] call
  [RET]        Agent results — extended preview (600 chars)
"""

import json
import sys

from cbim_kernel.context import cbim_dir


def main(event: dict | None = None) -> int:
    if event is None:
        raw = sys.stdin.buffer.read().decode("utf-8").strip()
        if not raw:
            return 0
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return 0

    tool = event.get("tool_name", "?")
    inp = event.get("tool_input", {}) or {}
    response = event.get("tool_response", {}) or {}
    transcript_path = event.get("transcript_path", "") or ""
    try:
        from cbim_kernel.engine.logger import log_ret
        log_ret(tool, inp, response, cbim=cbim_dir(), transcript_path=transcript_path)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
