"""
mcp_server/_logging.py — Wrap every @mcp.tool() registration so each call
emits [MCP] entries to the per-session log.

Used by server.py:

    from ._logging import patch_tool_logging
    patch_tool_logging(mcp)            # MUST run before tool modules are imported
"""

from __future__ import annotations

import functools
import inspect
from typing import Any


_MAX_ARG_PREVIEW = 80
_MAX_RESULT_PREVIEW = 200


def _preview(value: Any, limit: int) -> str:
    s = str(value)
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."


def _args_preview(kwargs: dict) -> str:
    if not kwargs:
        return "()"
    parts = [f"{k}={_preview(v, _MAX_ARG_PREVIEW)!r}" for k, v in kwargs.items()]
    return "(" + ", ".join(parts) + ")"


def _log(msg: str) -> None:
    try:
        from engine.session_log import append
        append("MCP", msg)
    except Exception:
        pass


def _wrap_sync(fn, tool_name: str):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        _log(f"call {tool_name} {_args_preview(kwargs)}")
        try:
            result = fn(*args, **kwargs)
            _log(f"done {tool_name} size={len(str(result)) if result is not None else 0}")
            return result
        except Exception as exc:
            _log(f"error {tool_name} {type(exc).__name__}: {exc}")
            raise
    return wrapper


def _wrap_async(fn, tool_name: str):
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        _log(f"call {tool_name} {_args_preview(kwargs)}")
        try:
            result = await fn(*args, **kwargs)
            _log(f"done {tool_name} size={len(str(result)) if result is not None else 0}")
            return result
        except Exception as exc:
            _log(f"error {tool_name} {type(exc).__name__}: {exc}")
            raise
    return wrapper


def patch_tool_logging(mcp) -> None:
    """Monkey-patch mcp.tool so every registered tool emits [MCP] log entries."""
    original = mcp.tool

    def patched_tool(*tool_args, **tool_kwargs):
        decorator = original(*tool_args, **tool_kwargs)

        def wrap(fn):
            name = tool_kwargs.get("name") or fn.__name__
            wrapped = _wrap_async(fn, name) if inspect.iscoroutinefunction(fn) else _wrap_sync(fn, name)
            return decorator(wrapped)

        return wrap

    mcp.tool = patched_tool
