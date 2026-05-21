"""
log_post_tool.py — PostToolUse hook.

Records the "reflection point" — assistant just got a tool result and is
deciding what to do next — into the per-session log under [RESULT].
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
    response = event.get("tool_response", {}) or {}
    is_error = bool(response.get("is_error") or response.get("error"))
    status = "error" if is_error else "ok"

    # Try to capture an output size or short snippet
    out = response.get("content") or response.get("stdout") or ""
    if isinstance(out, list):
        out = " ".join(str(x.get("text", "")) for x in out if isinstance(x, dict))
    size = len(str(out))

    try:
        from cbim_kernel.engine.session_log import append
        append("RESULT", f"{tool} status={status} size={size}", cbim=cbim_dir())
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
