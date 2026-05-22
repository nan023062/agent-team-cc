"""end_session.py — SessionEnd hook.

Finalises the session log via logger.end_session(). The [SESSION] end
marker is written only when .cbim/.debug is present.
"""
import json
import sys

from cbim_kernel.context import cbim_dir


def main(event: dict | None = None) -> int:
    if event is None:
        raw = sys.stdin.buffer.read().decode("utf-8").strip()
        event = {}
        if raw:
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                event = {}
    session_id = event.get("session_id", "")
    reason = event.get("reason", "") or "unknown"
    try:
        from cbim_kernel.engine.logger import end_session
        end_session(session_id=session_id, reason=reason, cbim=cbim_dir())
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
