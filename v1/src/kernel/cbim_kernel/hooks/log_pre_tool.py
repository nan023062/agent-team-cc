"""
log_pre_tool.py — PreToolUse hook.

Records "assistant is about to invoke a tool" — the action point of the agent
loop — into the per-session log under [TOOL]. Always-on (no debug flag).
"""

import json
import sys

from cbim_kernel.context import cbim_dir


def _format(tool: str, inp: dict) -> str:
    if tool in ("Read", "Write", "Edit"):
        return f'path={inp.get("file_path", "?")}'
    if tool == "Glob":
        return f'pattern={inp.get("pattern", "?")}'
    if tool == "Grep":
        return f'pattern={inp.get("pattern", "?")} path={inp.get("path", "")}'
    if tool == "Bash":
        cmd = str(inp.get("command", "?"))
        return f'cmd={cmd[:200]}'
    if tool == "Agent":
        return f'subagent={inp.get("subagent_type", "default")} desc={inp.get("description", "")[:80]!r}'
    return f'params_keys={len(inp)}'


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
        from cbim_kernel.engine.session_log import append
        append("TOOL", f"{tool} | {_format(tool, inp)}", cbim=cbim_dir())
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
