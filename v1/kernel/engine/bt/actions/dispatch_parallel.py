"""actions/dispatch_parallel.py — fan out one or more Work Agent subtasks.

Composite-style node (children = WorkAgentLeaf per subtask). On each tick
it (re)builds its child list from bb.dispatch_plan (subtasks may differ
across iterations) and delegates to the standard Parallel walk.

Parallel semantics: fail-fast on child FAILURE; RUNNING wins (Runner can
only yield one DispatchRequest per tick — remaining subtasks dispatch on
the next iteration after resume).
"""

from __future__ import annotations

from ..api.result import DispatchRequest
from ..core.node import Node, Status


class WorkAgentLeaf(Node):
    """One leaf per subtask. yields on first tick, completes on resume."""

    def __init__(self, *, subtask_id: str) -> None:
        self.subtask_id = subtask_id
        self.name = f"WorkAgentLeaf#{subtask_id}"

    def tick(self, bb) -> Status:
        result = (bb.subtask_results or {}).get(self.subtask_id)
        if result is not None:
            status = result.get("status")
            if status == "ok":
                return Status.SUCCESS
            if status == "needs_arch":
                # Treat as SUCCESS at the leaf level so the parent moves on
                # to Aggregate / ConvergeJudge, which route to escalation.
                return Status.SUCCESS
            return Status.FAILURE
        subtask = self._find_subtask(bb)
        if subtask is None:
            return Status.FAILURE
        bb.pending_dispatch = DispatchRequest(
            agent_type="work",
            agent_file=subtask.get("target_agent_file"),
            prompt=self._compose_prompt(bb, subtask),
            subtask_id=self.subtask_id,
            timeout_hint_s=subtask.get("timeout_hint_s"),
        )
        return Status.RUNNING

    def on_resume(self, bb, payload) -> None:
        text = payload if isinstance(payload, str) else (
            payload.get("output", "") if isinstance(payload, dict) else str(payload)
        )
        needs_arch = "NEEDS_ARCH_DECISION:" in text
        new_results = dict(bb.subtask_results or {})
        new_results[self.subtask_id] = {
            "status": "needs_arch" if needs_arch else "ok",
            "output": text,
            "needs_arch_decision": needs_arch,
            "raw": payload if not isinstance(payload, str) else None,
        }
        bb.subtask_results = new_results
        bb.pending_dispatch = None

    def _find_subtask(self, bb) -> dict | None:
        for s in (bb.dispatch_plan or []):
            if s.get("id") == self.subtask_id:
                return s
        return None

    def _compose_prompt(self, bb, subtask: dict) -> str:
        arch = bb.arch_context or {}
        ctx = arch.get("output") if isinstance(arch, dict) else str(arch)
        ctx_block = ""
        if ctx:
            ctx_block = (
                "\n\n<!-- BEGIN ContextPack -->\n"
                "## ContextPack\n\n"
                f"{ctx}\n"
                "<!-- END ContextPack -->\n"
            )
        return (
            f"{subtask.get('prompt', '')}"
            f"{ctx_block}"
        )


class DispatchParallel(Node):
    """Container that exposes one WorkAgentLeaf per subtask in dispatch_plan.

    Children are constructed on every tick (and on resume-path lookup)
    from bb.dispatch_plan, so the resume path can always find a leaf
    whose name matches `WorkAgentLeaf#<subtask_id>`. The node holds no
    cross-tick state on self — `_bb_ref` is set by tick() and cleared at
    runner entry; resume_path walking reads it back via the runner's
    walk helpers which call `children()`.
    """

    def __init__(self, *, name: str = "DispatchParallel") -> None:
        self.name = name
        # Holds the most recently seen bb so children() can rebuild leaves
        # on Runner.resume() walks. Not cross-tick durable state — it's a
        # within-process pointer reset on every fresh tick.
        self._bb_ref = None

    def children(self) -> list[Node]:
        bb = self._bb_ref
        if bb is None:
            return []
        return [WorkAgentLeaf(subtask_id=s["id"]) for s in (bb.dispatch_plan or [])]

    def tick(self, bb) -> Status:
        self._bb_ref = bb
        plan = bb.dispatch_plan or []
        if not plan:
            return Status.SUCCESS
        leaves = [WorkAgentLeaf(subtask_id=s["id"]) for s in plan]
        for leaf in leaves:
            status = leaf.tick(bb)
            if status is Status.FAILURE:
                return Status.FAILURE
            if status is Status.RUNNING:
                # First RUNNING wins — bubble up.
                return Status.RUNNING
        return Status.SUCCESS
