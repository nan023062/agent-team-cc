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

from ._trace_utils import _append_trace_event, _now_iso_ms
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
        # Per-tick decision log; do NOT hang this on self (composites are
        # stateless across ticks per README §2 iron rule).
        child_results: list[dict] = []
        for i in range(start_idx, len(self._children)):
            child = self._children[i]
            status = _tick_child(self, child, i, bb)
            child_results.append({
                "name": child.name,
                "status": status.value if hasattr(status, "value") else str(status),
            })
            if status is Status.SUCCESS:
                _append_trace_event(bb, {
                    "event": "selector_decision",
                    "node": self.name,
                    "chosen_child": child.name,
                    "outcome": "success",
                    "child_results": child_results,
                    "ts": _now_iso_ms(),
                })
                return Status.SUCCESS
            if status is Status.RUNNING:
                _append_trace_event(bb, {
                    "event": "selector_decision",
                    "node": self.name,
                    "chosen_child": child.name,
                    "outcome": "running",
                    "child_results": child_results,
                    "ts": _now_iso_ms(),
                })
                return Status.RUNNING
        _append_trace_event(bb, {
            "event": "selector_decision",
            "node": self.name,
            "chosen_child": None,
            "outcome": "all_failure",
            "child_results": child_results,
            "ts": _now_iso_ms(),
        })
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


class SwitchBranch(Node):
    """N-way branch on a bb-derived key.

    Routes to the child registered under ``key_fn(bb)``. When the key has
    no match in ``cases``, falls back to ``default`` (or returns FAILURE if
    no default supplied).

    Like ModeBranch, this is NOT a Selector — we route on a bb predicate,
    not on child return values. The chosen child's status bubbles up
    unchanged.
    """

    def __init__(
        self,
        *,
        key_fn: Callable[[object], str],
        cases: dict[str, Node],
        default: Node | None = None,
        name: str = "SwitchBranch",
    ) -> None:
        self.name = name
        self._key_fn = key_fn
        self._cases = dict(cases)
        self._default = default

    def children(self) -> list[Node]:
        kids = list(self._cases.values())
        if self._default is not None:
            kids.append(self._default)
        return kids

    def tick(self, bb) -> Status:
        # Four decision paths, each emits exactly one switch_decision event
        # BEFORE the chosen child (if any) ticks. This keeps the trace
        # chronological: decision → child_enter → child_exit.
        try:
            key = self._key_fn(bb)
        except Exception as e:
            _append_trace_event(bb, {
                "event": "switch_decision",
                "node": self.name,
                "key": None,
                "matched_case": "__error__",
                "chosen_child": None,
                "error": f"{type(e).__name__}: {e}",
                "ts": _now_iso_ms(),
            })
            return Status.FAILURE

        child = self._cases.get(key) if key is not None else None
        if child is not None:
            _append_trace_event(bb, {
                "event": "switch_decision",
                "node": self.name,
                "key": key,
                "matched_case": key,
                "chosen_child": child.name,
                "ts": _now_iso_ms(),
            })
            return child.tick(bb)

        if self._default is not None:
            _append_trace_event(bb, {
                "event": "switch_decision",
                "node": self.name,
                "key": key,
                "matched_case": "__default__",
                "chosen_child": self._default.name,
                "ts": _now_iso_ms(),
            })
            return self._default.tick(bb)

        _append_trace_event(bb, {
            "event": "switch_decision",
            "node": self.name,
            "key": key,
            "matched_case": "__no_match__",
            "chosen_child": None,
            "ts": _now_iso_ms(),
        })
        return Status.FAILURE


class AlwaysSuccess(Node):
    """No-op leaf that always returns SUCCESS.

    Useful as a SwitchBranch fallback for "do nothing on this branch".
    """

    def __init__(self, *, name: str = "AlwaysSuccess") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        return Status.SUCCESS


class ForEach(Node):
    """Iterate a bb list field, ticking the child once per item.

    For each item in ``bb.<items_field>``:
      1. Write the item to ``bb.<item_var>``.
      2. Tick ``child``.
      3. If child returns FAILURE → return FAILURE (abort iteration; progress
         stays so a follow-up tick resumes at the same index after the
         caller fixes the upstream issue).
      4. If child returns RUNNING → return RUNNING (yielded to Runner;
         progress stays so the next tick resumes at the same index).
      5. If child returns SUCCESS → advance progress, continue.

    On full traversal: clear ``bb.<progress_field>`` and ``bb.<item_var>``
    so a re-tick starts clean, and return SUCCESS.

    Resumable: progress lives on bb under ``progress_field`` (default
    ``f"_foreach_{items_field}_idx"``). If present at tick entry, iteration
    starts there; otherwise it starts at 0.

    Missing or non-list ``bb.<items_field>`` → SUCCESS (treat as empty).
    """

    def __init__(
        self,
        *,
        items_field: str,
        item_var: str,
        child: Node,
        progress_field: str | None = None,
        name: str = "ForEach",
    ) -> None:
        self.name = name
        self._items_field = items_field
        self._item_var = item_var
        self._child = child
        self._progress_field = progress_field or f"_foreach_{items_field}_idx"

    def children(self) -> list[Node]:
        return [self._child]

    def tick(self, bb) -> Status:
        items = getattr(bb, self._items_field, None)
        if not isinstance(items, list) or not items:
            self._clear(bb)
            return Status.SUCCESS

        idx = getattr(bb, self._progress_field, None)
        if not isinstance(idx, int) or idx < 0:
            idx = 0

        n = len(items)
        while idx < n:
            setattr(bb, self._item_var, items[idx])
            setattr(bb, self._progress_field, idx)
            status = self._child.tick(bb)
            if status is Status.FAILURE:
                return Status.FAILURE
            if status is Status.RUNNING:
                return Status.RUNNING
            idx += 1

        self._clear(bb)
        return Status.SUCCESS

    def _clear(self, bb) -> None:
        # Best-effort cleanup; tolerate blackboards that pin a __slots__ schema
        # and refuse arbitrary attribute deletes.
        try:
            setattr(bb, self._progress_field, None)
        except (AttributeError, TypeError):
            pass
        try:
            setattr(bb, self._item_var, None)
        except (AttributeError, TypeError):
            pass


class ModeBranch(Node):
    """Two-way branch on `bb.mode` (v3).

    .. deprecated:: v3.5
       Superseded by :class:`SwitchBranch` once the execution root grew
       to five modes (``conversation`` / ``architect`` / ``hr`` /
       ``audit`` / ``execution``). New code should use ``SwitchBranch``
       directly. The class is retained for backward compatibility with
       any external callers and for unit tests that still exercise the
       two-mode shape; it is no longer wired into the v3.5 main loop
       (see ``engine/execution/tree/main_loop.py``).

    Routes to the `conversation` child when `bb.mode == "conversation"`,
    to the `execution` child otherwise (default fallback: execution).

    Not a Selector — we don't route on child return values; we route on a
    bb predicate. This keeps Selector's "try until SUCCESS" semantics clean.
    """

    def __init__(self, *, conversation: Node, execution: Node,
                 name: str = "ModeBranch") -> None:
        self.name = name
        self._conversation = conversation
        self._execution = execution

    def children(self) -> list[Node]:
        return [self._conversation, self._execution]

    def tick(self, bb) -> Status:
        mode = bb.mode or "execution"
        if mode == "conversation":
            return self._conversation.tick(bb)
        return self._execution.tick(bb)


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
