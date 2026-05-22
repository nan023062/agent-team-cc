"""
log_pre_tool.py — PreToolUse hook.

Records CBIM-specific tool calls into the session log. All other tool
calls are silently ignored — the full conversation is already visible
in Claude Code itself.

Tags emitted:
  [CBIM:<domain>]  cbim CLI call   (Bash cmd starting with "cbim <domain> ...")
  [CBIM:skill]     Skill tool invocation
  [CBIM:agent]     Agent tool dispatch

CBIM domain examples:
  dna      → architecture / module knowledge CRUD
  agent    → capability roster management
  skill    → capability catalogue show/list
  memory   → short-term / long-term memory CRUD
  workflow → (future) workflow execution
"""

import json
import sys

from cbim_kernel.context import cbim_dir

_MAX_CMD_CHARS = 400  # cap logged command length


def _parse_cbim_bash(cmd: str) -> tuple[str, str] | None:
    """Return (tag, message) if this Bash call is a 'cbim ...' command, else None."""
    stripped = cmd.strip()
    # Accept "cbim <args>" or bare "cbim" (unlikely but safe)
    if not (stripped == "cbim" or stripped.startswith("cbim ")):
        return None
    parts = stripped.split()
    domain = parts[1] if len(parts) > 1 else ""
    tag = f"CBIM:{domain}" if domain else "CBIM"
    display = stripped if len(stripped) <= _MAX_CMD_CHARS else stripped[:_MAX_CMD_CHARS] + "…"
    return tag, display


def _classify(tool: str, inp: dict) -> tuple[str, str] | None:
    """Return (tag, message) for CBIM-relevant tools, or None to skip."""
    if tool == "Bash":
        return _parse_cbim_bash(str(inp.get("command", "")))

    if tool == "Skill":
        skill = inp.get("skill", "?")
        args = (inp.get("args", "") or "").strip()
        msg = f"skill={skill!r}"
        if args:
            msg += f" args={args!r}"
        return "CBIM:skill", msg

    if tool == "Agent":
        subagent = inp.get("subagent_type", "default")
        desc = str(inp.get("description", "") or "")[:120]
        return "CBIM:agent", f"subagent={subagent} desc={desc!r}"

    return None


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
    result = _classify(tool, inp)
    if result is None:
        return 0  # not a CBIM call — skip

    tag, message = result
    try:
        from cbim_kernel.engine.logger import log_cbim_call
        log_cbim_call(tag, message, cbim=cbim_dir())
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
