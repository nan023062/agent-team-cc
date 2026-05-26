"""mcp_server/tools/dream.py — MCP tools for the CBIM dream governance loop.

Thin shim over engine.dream.api.dream_tick — all real logic lives in the
engine. Exposes 4 tools:
  - dream_tick(reason, run_id=None)
  - dream_tick_resume(run_id, dispatch_result)
  - dream_list_runs(limit=10)
  - dream_abort(run_id, reason)
"""

from __future__ import annotations

from engine.dream.api.dream_tick import (
    dream_abort as _dream_abort,
    dream_list_runs as _dream_list_runs,
    dream_tick as _dream_tick,
    dream_tick_resume as _dream_tick_resume,
)


def register(mcp) -> None:
    @mcp.tool()
    def dream_tick(reason: str, run_id: str | None = None) -> dict:
        """Start a new governance tick.

        `reason` ∈ {"catchup","manual","forced"}. SessionStart hook injects
        the catchup trigger; "manual" and "forced" bypass the 20-hour
        window. Returns a DreamResult dict — kind ∈ {"done","yield","error","skipped"}.
        On "yield", call dream_tick_resume(run_id, dispatch_result) after the
        Task tool returns.
        """
        try:
            return _dream_tick(reason, run_id).to_dict()
        except Exception as e:
            return {
                "kind": "error",
                "error_code": "engine_internal",
                "error_message": f"{type(e).__name__}: {e}",
            }

    @mcp.tool()
    def dream_tick_resume(run_id: str, dispatch_result) -> dict:
        """Resume a yielded governance tick with the Task-tool result.

        `dispatch_result` may be a string (raw agent output) or a dict
        (structured payload). Engine routes it to the path-tail Collect*Advice
        node's on_resume() handler.
        """
        try:
            return _dream_tick_resume(run_id, dispatch_result).to_dict()
        except Exception as e:
            return {
                "kind": "error",
                "error_code": "engine_internal",
                "error_message": f"{type(e).__name__}: {e}",
            }

    @mcp.tool()
    def dream_list_runs(limit: int = 10) -> list[dict]:
        """List recent dream runs under `.cbim/scheduler/dream/`.

        Returns one DreamRunSummary per run, most recent first.
        """
        try:
            return [s.to_dict() for s in _dream_list_runs(limit)]
        except Exception:
            return []

    @mcp.tool()
    def dream_abort(run_id: str, reason: str) -> dict:
        """Mark a RUNNING governance tick as abandoned.

        Writes `abandoned.json`, flips bb_status, clears current.json. Does
        NOT touch last_success.json — abandoned ≠ success. Returns AbortResult.
        """
        try:
            return _dream_abort(run_id, reason).to_dict()
        except Exception as e:
            return {
                "aborted": False,
                "run_id": run_id,
                "reason": reason,
                "abandoned_at": "",
                "error": f"{type(e).__name__}: {e}",
            }
