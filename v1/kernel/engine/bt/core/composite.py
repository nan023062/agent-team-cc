"""core/composite.py — Composite nodes: Sequence / Selector / Parallel.

All composites are stateless across ticks (README §2 iron rule).
Per-tick walk state (current child index, branch RUNNING set) is reconstructed
each tick by the Runner from `bb.runner_resume_path`; composites themselves
never store it.

Convention used by this engine: composites consult bb.runner_resume_path to
decide where to resume mid-stride, but they DO NOT mutate it directly —
the Runner is the sole writer for runner_resume_path (§ contract).
"""

from __future__ import annotations

from typing import Callable

from .node import Node, Status


class _Composite(Node):
    def __init__(self, children: list[Node], *, name: str) -> None:
        self.name = name
        self._children = list(children)

    def children(self) -> list[Node]:
        return list(self._children)


class Sequence(_Composite):
    """Short-circuit AND. Tick children left-to-right.

    - any FAILURE → return FAILURE (and stop)
    - any RUNNING → return RUNNING (the Runner records the resume path)
    - all SUCCESS → return SUCCESS
    """

    def __init__(self, children: list[Node], *, name: str = "Sequence") -> None:
        super().__init__(children, name=name)

    def tick(self, bb) -> Status:
        # Resume support: if runner_resume_path points into this composite,
        # skip already-completed children. Path segments are node names.
        start_idx = _resume_index(self, bb)
        for i in range(start_idx, len(self._children)):
            child = self._children[i]
            status = _tick_child(self, child, i, bb)
            if status is Status.FAILURE:
                return Status.FAILURE
            if status is Status.RUNNING:
                return Status.RUNNING
            # SUCCESS → continue
        return Status.SUCCESS


class Selector(_Composite):
    """Short-circuit OR. Tick children left-to-right.

    - any SUCCESS → return SUCCESS (and stop)
    - any RUNNING → return RUNNING
    - all FAILURE → return FAILURE
    """

    def __init__(self, children: list[Node], *, name: str = "Selector") -> None:
        super().__init__(children, name=name)

    def tick(self, bb) -> Status:
        start_idx = _resume_index(self, bb)
        for i in range(start_idx, len(self._children)):
            child = self._children[i]
            status = _tick_child(self, child, i, bb)
            if status is Status.SUCCESS:
                return Status.SUCCESS
            if status is Status.RUNNING:
                return Status.RUNNING
        return Status.FAILURE


class Parallel(_Composite):
    """Tick every child sequentially (no real concurrency in the engine).

    Semantics (current build): fail-fast on FAILURE; collect RUNNING and
    yield the FIRST one (Runner can only yield one DispatchRequest per
    tick; remaining RUNNING children resume on the next tick).
    """

    def __init__(self, children: list[Node], *, name: str = "Parallel") -> None:
        super().__init__(children, name=name)

    def tick(self, bb) -> Status:
        any_running = False
        for i, child in enumerate(self._children):
            status = _tick_child(self, child, i, bb)
            if status is Status.FAILURE:
                return Status.FAILURE
            if status is Status.RUNNING:
                # First RUNNING wins: bubble up so Runner can yield.
                return Status.RUNNING
        if any_running:
            return Status.RUNNING
        return Status.SUCCESS


class ClarifyBranch(Node):
    """Two-way branch on `bb.intent['clarification_needed']`.

    Not a Selector — we don't route on child return values; we route on a
    bb predicate. This keeps Selector's "try until SUCCESS" semantics clean.
    """

    def __init__(self, *, yes: Node, no: Node, name: str = "ClarifyBranch") -> None:
        self.name = name
        self._yes = yes
        self._no = no

    def children(self) -> list[Node]:
        return [self._yes, self._no]

    def tick(self, bb) -> Status:
        intent = bb.intent or {}
        if intent.get("clarification_needed"):
            return self._yes.tick(bb)
        return self._no.tick(bb)


# ---------------------------------------------------------------------------
# Resume-path helpers
# ---------------------------------------------------------------------------

def _resume_index(composite: _Composite, bb) -> int:
    """If runner_resume_path goes through `composite`, return the child
    index to resume at; otherwise 0.

    The path is a flat list of node names from root to the RUNNING leaf.
    """
    path = bb.runner_resume_path
    if not path:
        return 0
    # Find composite's own name in path; the next segment is the child name.
    try:
        idx = path.index(composite.name)
    except ValueError:
        return 0
    if idx + 1 >= len(path):
        return 0
    next_name = path[idx + 1]
    # Allow `#suffix` (used by Parallel children like WorkAgentLeaf#t1) — the
    # composite holds the BASE child object; resume needs to find which child
    # contains the path-target subtree. We match by child.name OR by name+'#'.
    for i, child in enumerate(composite._children):
        if child.name == next_name:
            return i
        if "#" in next_name and next_name.split("#", 1)[0] == child.name:
            return i
    return 0


def _tick_child(parent: _Composite, child: Node, index: int, bb) -> Status:
    """Tick a child; the Runner separately maintains the resume path. We
    don't touch bb.runner_resume_path here — that's the Runner's job after
    the leaf returns RUNNING (it walks the call stack to build the path)."""
    return child.tick(bb)
