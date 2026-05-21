"""
log_post_tool.py — PostToolUse hook.

Records the "reflection point" — assistant just got a tool result and is
deciding what to do next — into the per-session log under [RESULT].
"""

import json
import sys
from pathlib import Path


def _cbim_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> None:
    raw = sys.stdin.buffer.read().decode("utf-8").strip()
    if not raw:
        sys.exit(0)
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

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
        sys.path.insert(0, str(_cbim_root()))
        from engine.session_log import append
        append("RESULT", f"{tool} status={status} size={size}", cbim=_cbim_root())
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
