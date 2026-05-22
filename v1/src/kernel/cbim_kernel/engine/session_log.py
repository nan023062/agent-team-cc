"""
session_log.py — backward-compatibility shim.

All log logic has moved to cbim_kernel.engine.logger.
This module re-exports the public API so existing callers
(mcp_server, scheduler, etc.) keep working without changes.
"""

from cbim_kernel.engine.logger import (  # noqa: F401
    logs_dir,
    current_log_path,
    start_session,
    end_session,
    append,
    cbim_root_from_cwd,
    log_user,
    log_cbim_call,
    log_assist,
)

__all__ = [
    "logs_dir",
    "current_log_path",
    "start_session",
    "end_session",
    "append",
    "cbim_root_from_cwd",
    "log_user",
    "log_cbim_call",
    "log_assist",
]
