"""end_session.py — SessionEnd hook. Writes the paired [SESSION] end marker."""
import json, sys
from pathlib import Path


def _cbim_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> None:
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
        sys.path.insert(0, str(_cbim_root()))
        from engine.session_log import end_session
        end_session(session_id=session_id, reason=reason, cbim=_cbim_root())
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
