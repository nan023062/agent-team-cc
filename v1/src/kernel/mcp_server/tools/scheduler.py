"""
mcp_server/tools/scheduler.py — MCP tools to introspect and drive the scheduler.

Exposes:
  scheduler_status()         — all registered tasks + last-run state
  scheduler_trigger(name)    — manually fire a task right now
"""

from __future__ import annotations

import json


# The scheduler instance is injected by server.py at registration time.
_scheduler = None


def set_scheduler(scheduler) -> None:
    global _scheduler
    _scheduler = scheduler


def register(mcp) -> None:
    @mcp.tool()
    def scheduler_status() -> str:
        """List all registered scheduler tasks and their last-run state.

        Returns:
            JSON array of tasks with name, description, interval_seconds,
            respect_cc_idle, last_run_at, last_ok, last_result.
        """
        if _scheduler is None:
            return "ERROR: scheduler not initialized"
        return json.dumps(_scheduler.list_tasks(), indent=2, ensure_ascii=False)

    @mcp.tool()
    async def scheduler_trigger(name: str) -> str:
        """Manually fire the named scheduler task right now (bypasses schedule + idle gate).

        Args:
            name: Task name (see scheduler_status for available keys).
        """
        if _scheduler is None:
            return "ERROR: scheduler not initialized"
        return await _scheduler.trigger(name)
