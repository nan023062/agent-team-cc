"""call_log.py — engine CLI invocation logger (writes [ENG] lines to session log)."""

from pathlib import Path


def log_call(argv: list, exit_code: int) -> None:
    from .debug import is_debug
    if not is_debug():
        return
    try:
        from .session_log import append
        cmd = " ".join(str(a) for a in argv)
        append("ENG", f"argv={cmd} | cwd={Path.cwd()} | exit={exit_code}")
    except Exception:
        pass
