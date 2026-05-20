"""
log_pre_tool.py — PreToolUse hook.

Records "assistant is about to invoke a tool" — the action point of the agent
loop — into the per-session log under [TOOL]. Always-on (no debug flag).
"""

import json
import sys
from pathlib import Path


def _cbim_root() -> Path:
    return Path(__file__).resolve().parent.parent


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


def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    tool = event.get("tool_name", "?")
    inp = event.get("tool_input", {}) or {}

    try:
        sys.path.insert(0, str(_cbim_root()))
        from engine.session_log import append
        append("TOOL", f"{tool} | {_format(tool, inp)}", cbim=_cbim_root())
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
