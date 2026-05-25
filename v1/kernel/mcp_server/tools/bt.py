"""mcp_server/tools/bt.py — MCP tools for CBIM behavior-tree engine.

Thin shim over engine.execution.api.bt_tick — all real logic lives in the engine.
Exposes 4 tools:
  - bt_tick(user_request, context=None)
  - bt_tick_resume(tick_id, dispatch_result)
  - bt_list_running_ticks()
  - bt_abort(tick_id, reason="")
"""

from __future__ import annotations

from engine.execution.api.bt_tick import (
    bt_abort as _bt_abort,
    bt_list_running_ticks as _bt_list_running_ticks,
    bt_tick as _bt_tick,
    bt_tick_resume as _bt_tick_resume,
)


def register(mcp) -> None:
    @mcp.tool()
    def bt_tick(user_request: str, context: dict | None = None) -> dict:
        """Start a new behavior-tree tick for a user prompt.

        Returns a BtResult dict — kind ∈ {"done","yield","error"}. On
        "yield", call bt_tick_resume(tick_id, dispatch_result) after
        invoking the Task tool with dispatch_request.prompt.
        """
        try:
            return _bt_tick(user_request, context).to_dict()
        except Exception as e:
            return {
                "kind": "error",
                "error_code": "engine_internal",
                "error_message": f"{type(e).__name__}: {e}",
            }

    @mcp.tool()
    def bt_tick_resume(tick_id: str, dispatch_result) -> dict:
        """Resume a yielded tick with the Task-tool result.

        `dispatch_result` may be a string (raw agent output) or a dict
        (structured payload). The engine routes it to the path-tail
        Action's on_resume() handler.
        """
        try:
            return _bt_tick_resume(tick_id, dispatch_result).to_dict()
        except Exception as e:
            return {
                "kind": "error",
                "error_code": "engine_internal",
                "error_message": f"{type(e).__name__}: {e}",
            }

    @mcp.tool()
    def bt_list_running_ticks() -> list[dict]:
        """List unfinished ticks under .cbim/scheduler/bt/.

        Returns one TickStatus per tick where bb_status=="running".
        """
        try:
            return [t.to_dict() for t in _bt_list_running_ticks()]
        except Exception:
            return []

    @mcp.tool()
    def bt_abort(tick_id: str, reason: str = "") -> dict:
        """Archive a running tick without resume.

        Marks bb_status=error and writes interrupt_reason. Returns
        {ok: bool, ...}.
        """
        return _bt_abort(tick_id, reason)
