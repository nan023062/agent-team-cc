"""
heartbeat.py — Demo Task. Logs a one-line heartbeat every 5 minutes.

Use as a wiring sanity check: see [SCHED] heartbeat ok | tick #N in the session log
to confirm the scheduler loop is alive.
"""

from datetime import datetime

from mcp_server.scheduler import Task


class Heartbeat(Task):
    name = "heartbeat"
    description = "Wiring sanity check — logs a tick every 5 minutes"
    interval_seconds = 300  # 5 minutes
    respect_cc_idle = False  # always fire

    _count = 0

    async def run(self, context: dict) -> str:
        Heartbeat._count += 1
        return f"tick #{Heartbeat._count} at {datetime.now().strftime('%H:%M:%S')}"
