"""
log_pre_tool.py — PreToolUse hook.

Logs every tool invocation to the session log.
  [CBIM:<domain>]  cbim CLI call (Bash starting with "cbim <domain> ...")
  [CBIM:skill]     Skill tool invocation
  [CBIM:agent]     Agent tool dispatch
  [CALL]           All other tool calls (Read, Write, Edit, Glob, Grep, …)

Tag routing is handled by logger.format_tool_call — hooks are thin adapters.
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
    try:
        from cbim_kernel.engine.logger import log_call
        log_call(tool, inp, cbim=cbim_dir())
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
