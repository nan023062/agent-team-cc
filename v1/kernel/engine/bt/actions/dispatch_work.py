"""actions/dispatch_work.py — fan out one Work Agent per Task in bb.arch_plan.

Composite-style node (children = WorkAgentLeaf per task). On each tick it
(re)builds its child list from bb.arch_plan and walks them sequentially.

Per-tick semantics: any leaf RUNNING bubbles up (Runner can only yield one
DispatchRequest per tick — remaining leaves dispatch on the next tick).
Any leaf FAILURE bubbles up unless wrapped in @Catch.

WorkAgentLeaf is wrapped at construction in @Catch so that a single Work
Agent crash writes a failure marker to bb.work_results[id] instead of
sinking the whole tree.
"""

from __future__ import annotations

from ..api.result import DispatchRequest
from ..core.node import Node, Status


class WorkAgentLeaf(Node):
    """One leaf per task in arch_plan. yields on first tick, completes on resume."""

    def __init__(self, *, task_id: str) -> None:
        self.task_id = task_id
        self.name = f"WorkAgentLeaf#{task_id}"

    def tick(self, bb) -> Status:
        result = (bb.work_results or {}).get(self.task_id)
        if result is not None:
            status = result.get("status")
            if status == "ok":
                return Status.SUCCESS
            return Status.FAILURE
        task = self._find_task(bb)
        if task is None:
            return Status.FAILURE
        bb.pending_dispatch = DispatchRequest(
            agent_type="work",
            agent_file=task.get("agent_file"),
            prompt=self._compose_prompt(bb, task),
            subtask_id=self.task_id,
            timeout_hint_s=task.get("timeout_hint_s"),
        )
        return Status.RUNNING

    def on_resume(self, bb, payload) -> None:
        text = payload if isinstance(payload, str) else (
            payload.get("output", "") if isinstance(payload, dict) else str(payload)
        )
        new_results = dict(bb.work_results or {})
        new_results[self.task_id] = {
            "status": "ok",
            "output": text,
            "raw": payload if not isinstance(payload, str) else None,
        }
        bb.work_results = new_results
        bb.pending_dispatch = None

    def _find_task(self, bb) -> dict | None:
        for t in (bb.arch_plan or []):
            if t.get("id") == self.task_id:
                return t
        return None

    def _compose_prompt(self, bb, task: dict) -> str:
        ctx = task.get("arch_context") or ""
        ctx_block = ""
        if ctx:
            ctx_block = (
                "\n\n<!-- BEGIN ContextPack -->\n"
                "## ContextPack\n\n"
                f"{ctx}\n"
                "<!-- END ContextPack -->\n"
            )
        params = task.get("params") or {}
        params_block = ""
        if params:
            params_block = "\n\n## Params\n" + "\n".join(
                f"- {k}: {v}" for k, v in params.items()
            )
        description = task.get("description") or (bb.user_request or "")
        return (
            f"{description}"
            f"{params_block}"
            f"{ctx_block}"
        )


class DispatchWork(Node):
    """Container that exposes one WorkAgentLeaf per task in bb.arch_plan.

    Children are constructed on every tick (and on resume-path lookup)
    from bb.arch_plan, so the resume path can always find a leaf whose
    name matches `WorkAgentLeaf#<task_id>`. The node holds no cross-tick
    state on self — `_bb_ref` is set by tick() and is a within-process
    pointer reset on every fresh tick.
    """

    def __init__(self, *, name: str = "DispatchWork") -> None:
        self.name = name
        self._bb_ref = None

    def children(self) -> list[Node]:
        bb = self._bb_ref
        if bb is None:
            return []
        return [WorkAgentLeaf(task_id=t["id"]) for t in (bb.arch_plan or [])]

    def tick(self, bb) -> Status:
        self._bb_ref = bb
        plan = bb.arch_plan or []
        if not plan:
            return Status.SUCCESS
        for t in plan:
            leaf = WorkAgentLeaf(task_id=t["id"])
            status = leaf.tick(bb)
            if status is Status.FAILURE:
                return Status.FAILURE
            if status is Status.RUNNING:
                return Status.RUNNING
            # SUCCESS → continue to next task
        return Status.SUCCESS
