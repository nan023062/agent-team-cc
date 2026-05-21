"""
services/log_service.py - read-only session log tail service.

Reads the active session log file via `engine.session_log.current_log_path()`
and returns new content since a byte offset. The dashboard polls this
endpoint every 2 seconds to render a live log tail.

Always re-resolves the current log path per call - sessions can change
during a long-lived browser tab, and we want the tail to follow.
"""

from __future__ import annotations

from pathlib import Path


def read_log(cbim: Path | None = None, since: int = 0) -> dict:
    """Return new log content beyond `since` bytes, plus the new offset.

    Args:
        cbim:  The `.cbim/` directory. Passed through to session_log so it
               can locate `logs/.current`. If None, session_log walks up
               from cwd.
        since: Byte offset returned by a previous call. Use 0 on first call;
               the server has no per-client memory.

    Returns:
        dict shaped like::

            {
              "lines":  ["[2026-05-21 10:00:01] [USER] ...", ...],
              "offset": <int new byte offset to send next time>,
              "path":   <str absolute log path, or "" if no session active>,
              "rotated": <bool true if log shrank (new session) - client
                          should reset its in-memory buffer>,
            }

    A shorter file than `since` indicates the log was rotated (new session
    started). In that case we restart from offset 0 and signal `rotated`.
    """
    # Lazy import so any failure during package discovery doesn't break
    # the whole services package.
    from cbim_kernel.engine import session_log

    log_path = session_log.current_log_path(cbim)
    if log_path is None or not log_path.exists():
        return {"lines": [], "offset": 0, "path": "", "rotated": False}

    try:
        size = log_path.stat().st_size
    except OSError:
        return {"lines": [], "offset": since, "path": str(log_path), "rotated": False}

    rotated = False
    if since > size:
        # File shrank - log rotated (new session). Replay from start.
        since = 0
        rotated = True

    if since == size:
        return {"lines": [], "offset": size, "path": str(log_path), "rotated": rotated}

    try:
        with log_path.open("rb") as f:
            f.seek(since)
            chunk = f.read()
    except OSError:
        return {"lines": [], "offset": since, "path": str(log_path), "rotated": rotated}

    new_offset = since + len(chunk)
    # Decode tolerantly - log content can include arbitrary tool output.
    text = chunk.decode("utf-8", errors="replace")
    # Drop a trailing partial line: if the chunk doesn't end with newline,
    # the last line is incomplete and we'll see the rest next poll.
    # We DO emit it anyway and rewind offset, otherwise a slow writer
    # could starve the tail. Simpler: split on newline, keep all lines.
    lines = text.splitlines()
    return {
        "lines": lines,
        "offset": new_offset,
        "path": str(log_path),
        "rotated": rotated,
    }
