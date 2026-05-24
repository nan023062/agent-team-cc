"""actions/init_tick.py — first Action of every tick.

Idempotent: bt_tick already wrote tick_id / user_request / iteration_cap /
subtask_results / bb_status before the runner started. InitTick exists so
that the canonical "first node" slot in the tree is filled, the trace
records an explicit "init" anchor, and a future change-of-defaults can be
made in one place. Never fails.
"""

from __future__ import annotations

from ..core.node import Node, Status


class InitTick(Node):
    def __init__(self, *, name: str = "InitTick") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        # bt_tick() set all of these — re-affirm defaults only if missing.
        if bb.iteration is None:
            bb.iteration = 0
        if bb.iteration_cap is None:
            bb.iteration_cap = 5
        if bb.subtask_results is None:
            bb.subtask_results = {}
        if bb.bb_status is None:
            bb.bb_status = "running"
        return Status.SUCCESS
