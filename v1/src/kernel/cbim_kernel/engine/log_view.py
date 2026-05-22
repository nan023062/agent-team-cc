"""log_view.py — view per-session log files.

`log show [--lines N] [--session SLUG]` — print the last N lines of the
current (or specified) session log, expanding \\n escapes for readability.

`log tail` — follow the current session log as it grows.
"""

import time
from pathlib import Path


def _logs_dir() -> Path:
    from .logger import logs_dir
    return logs_dir()


def _resolve_log(session_slug: str | None) -> Path | None:
    logs = _logs_dir()
    if session_slug:
        exact = logs / session_slug
        if exact.exists():
            return exact
        matches = sorted(logs.glob(f"session_*{session_slug}*.log"))
        if matches:
            return matches[-1]
        return None
    from .logger import current_log_path
    return current_log_path()


def _expand(line: str) -> str:
    """Expand \\n escapes back to real newlines for display."""
    return line.replace("\\n", "\n")


def cmd_log_show(args) -> int:
    lines = getattr(args, "lines", 50)
    slug = getattr(args, "session", None)
    log = _resolve_log(slug)
    if log is None or not log.exists():
        print("(no session log yet)")
        return 0
    content = log.read_text(encoding="utf-8", errors="replace").splitlines()
    print(f"# {log}")
    for line in content[-lines:]:
        print(_expand(line))
    return 0


def cmd_log_tail(args) -> int:
    interval = getattr(args, "interval", 1.0)
    slug = getattr(args, "session", None)
    log = _resolve_log(slug)
    if log is None:
        print("(no session log yet; nothing to tail)")
        return 0
    log.touch()
    print(f"Tailing {log} (Ctrl+C to stop)...")
    try:
        with log.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(0, 2)
            while True:
                line = fh.readline()
                if not line:
                    time.sleep(interval)
                    continue
                print(_expand(line.rstrip()), flush=True)
    except KeyboardInterrupt:
        pass
    return 0
