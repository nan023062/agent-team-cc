"""dream/core/composite_tolerant.py — SequenceTolerant composite.

The governance loop's three steps (memory / knowledge / capability) are run
in strict order but must NOT short-circuit on a single-step FAILURE — one
broken step should not silently kill the rest. SequenceTolerant captures
this semantics:

  - tick children left-to-right
  - any RUNNING bubbles up immediately (the Runner yields, resume continues
    from the same child on next tick)
  - per-child final status (SUCCESS / FAILURE) is recorded into
    bb.step_results[child.name] before moving to the next child
  - after all children resolved:
      - at least one SUCCESS → composite returns SUCCESS
      - all FAILURE         → composite returns FAILURE

This is the design from `WORKFLOW-DREAM §三` SequenceTolerant section and the
architect's conflict-1 ruling: lives in dream/core because bt's Blackboard
schema does not carry `step_results` (a dream-only field).
"""

from __future__ import annotations

from engine.execution.core.node import Node, Status

# bt.core.composite's base class is module-private (`_Composite`). Re-derive
# the same minimal shape locally rather than reach into a private name —
# this also keeps dream/core self-contained.

class _Composite(Node):
    def __init__(self, children: list[Node], *, name: str) -> None:
        self.name = name
        self._children = list(children)

    def children(self) -> list[Node]:
        return list(self._children)


class SequenceTolerant(_Composite):
    """Sequence variant that records per-child status into bb.step_results
    and does NOT short-circuit on FAILURE.

    Aggregation rule (after all children resolved):
      - at least one SUCCESS → SUCCESS
      - all FAILURE         → FAILURE
    Resume behaviour:
      - obeys bb.runner_resume_path the same way bt.core.composite.Sequence
        does — skip children whose name lies before the resume target
      - on resume, children that already recorded a status in
        bb.step_results are skipped (idempotent re-entry)
    """

    def __init__(self, children: list[Node], *, name: str = "SequenceTolerant") -> None:
        super().__init__(children, name=name)

    def tick(self, bb) -> Status:
        start_idx = _resume_index(self, bb)
        if bb.step_results is None:
            bb.step_results = {}
        results = dict(bb.step_results)

        for i in range(start_idx, len(self._children)):
            child = self._children[i]
            # Idempotent re-entry: if this child already has a recorded
            # terminal status, skip it (we are resuming past it).
            if child.name in results and results[child.name] in ("success", "failure"):
                continue
            status = child.tick(bb)
            if status is Status.RUNNING:
                # Yield. Do NOT record a terminal status; on resume we re-tick
                # this same child.
                return Status.RUNNING
            results[child.name] = status.value  # "success" | "failure"
            bb.step_results = dict(results)

        # All children resolved — aggregate.
        any_success = any(v == "success" for v in results.values())
        return Status.SUCCESS if any_success else Status.FAILURE


def _resume_index(composite: _Composite, bb) -> int:
    """Mirrors bt.core.composite._resume_index — find the child slot to
    resume into based on bb.runner_resume_path.
    """
    path = bb.runner_resume_path
    if not path:
        return 0
    try:
        idx = path.index(composite.name)
    except ValueError:
        return 0
    if idx + 1 >= len(path):
        return 0
    next_name = path[idx + 1]
    for i, child in enumerate(composite._children):
        if child.name == next_name:
            return i
        if "#" in next_name and next_name.split("#", 1)[0] == child.name:
            return i
    return 0
