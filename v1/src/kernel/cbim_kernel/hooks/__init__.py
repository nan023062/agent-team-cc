"""
Hook event dispatcher for CBIM.

Called via: cbim hook <event-name>

Reads the Claude Code hook JSON payload from stdin once, dispatches to the
matching handler in cbim_kernel.hooks.*. Each handler receives the parsed
event dict and uses cbim_kernel.context for path resolution.

Hooks must NEVER block Claude Code on failure — any exception in a handler
is swallowed and dispatch returns 0.
"""
from __future__ import annotations

import json
import sys

EVENT_MAP = {
    "session-start": "run_session_start",
    "session-end":   "run_session_end",
    "stop":          "run_stop",
    "log-prompt":    "run_log_prompt",
    "log-pre-tool":  "run_log_pre_tool",
    "log-post-tool": "run_log_post_tool",
}


def dispatch(event_name: str) -> int:
    """Entry point from `cbim hook <event>`. Reads stdin JSON, calls handler."""
    handler_name = EVENT_MAP.get(event_name)
    if not handler_name:
        print(f"[cbim] unknown hook event: {event_name}", file=sys.stderr)
        print(f"[cbim] known events: {', '.join(EVENT_MAP)}", file=sys.stderr)
        return 1

    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
        event = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, OSError):
        event = {}

    handler = globals()[handler_name]
    try:
        return handler(event) or 0
    except Exception as e:
        # Hooks are fire-and-forget from Claude Code's perspective; never block.
        print(f"[cbim] hook {event_name} error: {e}", file=sys.stderr)
        return 0


# ---------------------------------------------------------------------------
# Handlers — thin wrappers around the per-event modules. Each accepts the
# parsed event dict; modules implement the real logic.
# ---------------------------------------------------------------------------

def run_session_start(event: dict) -> int:
    """SessionStart consolidates two legacy hooks: load_memory + auto_preview.
    Running them sequentially under one handler avoids racing SessionStart
    invocations and keeps stdout ordering predictable.
    """
    from cbim_kernel.hooks.load_memory import main as load_memory
    from cbim_kernel.hooks.auto_preview import main as auto_preview
    try:
        load_memory(event)
    except Exception as e:
        print(f"[cbim] session-start.load_memory error: {e}", file=sys.stderr)
    try:
        auto_preview(event)
    except Exception as e:
        print(f"[cbim] session-start.auto_preview error: {e}", file=sys.stderr)
    return 0


def run_session_end(event: dict) -> int:
    from cbim_kernel.hooks.end_session import main as end_session
    return end_session(event) or 0


def run_stop(event: dict) -> int:
    from cbim_kernel.hooks.write_memory import main as write_memory
    return write_memory(event) or 0


def run_log_prompt(event: dict) -> int:
    from cbim_kernel.hooks.log_user_prompt import main as log_user_prompt
    return log_user_prompt(event) or 0


def run_log_pre_tool(event: dict) -> int:
    from cbim_kernel.hooks.log_pre_tool import main as log_pre_tool
    return log_pre_tool(event) or 0


def run_log_post_tool(event: dict) -> int:
    from cbim_kernel.hooks.log_post_tool import main as log_post_tool
    return log_post_tool(event) or 0
