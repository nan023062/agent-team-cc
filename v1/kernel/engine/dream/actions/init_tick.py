"""actions/init_tick.py — first Action of every dream tick.

Idempotent: dream_tick() already wrote run_id / trigger_reason / started_at /
bb_status before the Runner started. InitDreamTick exists so the canonical
"first node" slot in the tree is filled and the trace records an explicit
"init" anchor. Never fails.
"""

from __future__ import annotations

from datetime import datetime, timezone

from engine.bt.core.node import Node, Status


class InitDreamTick(Node):
    def __init__(self, *, name: str = "InitDreamTick") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        if bb.step_results is None:
            bb.step_results = {}
        if bb.bb_status is None:
            bb.bb_status = "running"
        if bb.started_at is None:
            bb.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return Status.SUCCESS
