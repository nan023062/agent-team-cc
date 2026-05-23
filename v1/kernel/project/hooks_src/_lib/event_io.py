"""
hooks_src/_lib/event_io.py — stdin/stdout helpers for Claude Code hook scripts.

stdlib-only. No business knowledge. Placeholder surface — Phase 3a rewrites
the seven hook scripts and consumes these helpers.

Public surface:
    read_event() -> dict
    write_additional_context(text)
"""

from __future__ import annotations

import json
import sys


def read_event() -> dict:
    """Read a single Claude Code hook event JSON object from stdin."""
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def write_additional_context(text: str) -> None:
    """Emit a SessionStart additionalContext payload on stdout."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text or "",
        }
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()
