"""PR-C — LoopSeq composite unit tests.

Covers spec §10.2 cases 11-17. Pure structural; no engine integration.
"""
from __future__ import annotations

from types import SimpleNamespace

from engine.core.composite import LoopSeq
from engine.core.node import Node, Status


class _ScriptNode(Node):
    """Returns the next status from a per-iteration script."""

    def __init__(self, name: str, script: list[Status]) -> None:
        self.name = name
        self._script = list(script)
        self.tick_count = 0

    def tick(self, bb) -> Status:
        self.tick_count += 1
        # Repeat the final status if asked more times than script provides.
        idx = min(self.tick_count - 1, len(self._script) - 1)
        return self._script[idx]


def _bb() -> SimpleNamespace:
    bb = SimpleNamespace()
    bb.trace = []
    bb.runner_resume_path = None
    bb.work_loop_iter = None
    return bb


def _reenter_events(bb) -> list[dict]:
    return [e for e in bb.trace if e.get("event") == "loopseq_reenter"]


# ---------------------------------------------------------------------------
# Case 11: all children SUCCESS on first pass → exits cleanly
# ---------------------------------------------------------------------------

def test_all_success_first_pass_exits_clean():
    a = _ScriptNode("A", [Status.SUCCESS])
    b = _ScriptNode("B", [Status.SUCCESS])
    loop = LoopSeq([a, b], max_iters=3, name="WorkLoop")
    bb = _bb()
    assert loop.tick(bb) is Status.SUCCESS
    assert a.tick_count == 1
    assert b.tick_count == 1
    assert bb.work_loop_iter is None  # cleared on exit
    assert _reenter_events(bb) == []


# ---------------------------------------------------------------------------
# Case 12: FAILURE on iter 1, SUCCESS on iter 2 → exits with one reenter
# ---------------------------------------------------------------------------

def test_failure_then_success_logs_one_reenter():
    a = _ScriptNode("A", [Status.SUCCESS, Status.SUCCESS])
    b = _ScriptNode("B", [Status.FAILURE, Status.SUCCESS])
    loop = LoopSeq([a, b], max_iters=3, name="WorkLoop")
    bb = _bb()
    assert loop.tick(bb) is Status.SUCCESS
    # A ticks twice (once per iteration); B ticks twice (fail then succeed).
    assert a.tick_count == 2
    assert b.tick_count == 2
    events = _reenter_events(bb)
    assert len(events) == 1
    assert events[0]["iter"] == 2
    assert events[0]["max_iters"] == 3
    assert bb.work_loop_iter is None


# ---------------------------------------------------------------------------
# Case 13: FAILURE every iter, max_iters=3 → SUCCESS with two reenters
# ---------------------------------------------------------------------------

def test_persistent_failure_exhausts_and_returns_success():
    a = _ScriptNode("A", [Status.SUCCESS] * 3)
    b = _ScriptNode("B", [Status.FAILURE] * 3)
    loop = LoopSeq([a, b], max_iters=3, name="WorkLoop")
    bb = _bb()
    assert loop.tick(bb) is Status.SUCCESS  # exhausted contract — bb signal carries
    assert a.tick_count == 3
    assert b.tick_count == 3
    events = _reenter_events(bb)
    assert len(events) == 2
    assert [e["iter"] for e in events] == [2, 3]
    assert bb.work_loop_iter is None  # cleared after exhaustion exit


# ---------------------------------------------------------------------------
# Case 14: first child RUNNING on iter 1 → LoopSeq returns RUNNING, iter preserved
# ---------------------------------------------------------------------------

def test_running_yields_and_preserves_iter():
    a = _ScriptNode("A", [Status.RUNNING])
    b = _ScriptNode("B", [Status.SUCCESS])
    loop = LoopSeq([a, b], max_iters=3, name="WorkLoop")
    bb = _bb()
    assert loop.tick(bb) is Status.RUNNING
    assert a.tick_count == 1
    assert b.tick_count == 0  # not reached
    assert bb.work_loop_iter == 1
    # Canonical scratch field also set.
    assert getattr(bb, "_loopseq_WorkLoop_iter") == 1


# ---------------------------------------------------------------------------
# Case 15: resume path through LoopSeq advances to the correct child
# ---------------------------------------------------------------------------

def test_resume_path_skips_completed_children():
    a = _ScriptNode("A", [Status.SUCCESS])
    b = _ScriptNode("B", [Status.SUCCESS])
    c = _ScriptNode("C", [Status.SUCCESS])
    loop = LoopSeq([a, b, c], max_iters=3, name="WorkLoop")
    bb = _bb()
    # Simulate the Runner resuming mid-loop: path points into child B.
    bb.runner_resume_path = ["Root", "WorkLoop", "B"]
    bb.work_loop_iter = 1
    bb._loopseq_WorkLoop_iter = 1
    assert loop.tick(bb) is Status.SUCCESS
    # A skipped because resume path lands at B.
    assert a.tick_count == 0
    assert b.tick_count == 1
    assert c.tick_count == 1


# ---------------------------------------------------------------------------
# Case 16: two LoopSeq instances do not share iter state
# ---------------------------------------------------------------------------

def test_independent_iter_state_across_instances():
    a1 = _ScriptNode("A1", [Status.FAILURE, Status.SUCCESS])
    a2 = _ScriptNode("A2", [Status.FAILURE, Status.SUCCESS])
    loop1 = LoopSeq([a1], max_iters=3, name="Loop1")
    loop2 = LoopSeq([a2], max_iters=3, name="Loop2")
    bb = _bb()
    assert loop1.tick(bb) is Status.SUCCESS
    assert loop2.tick(bb) is Status.SUCCESS
    # Iter fields live under distinct keys, no collision.
    assert getattr(bb, "_loopseq_Loop1_iter") is None
    assert getattr(bb, "_loopseq_Loop2_iter") is None
    # work_loop_iter alias only fires for the "WorkLoop"-named instance.
    assert bb.work_loop_iter is None


# ---------------------------------------------------------------------------
# Case 17: non-judge child failing on final iter still returns SUCCESS
# ---------------------------------------------------------------------------

def test_persistent_first_child_failure_returns_success_at_exhaustion():
    # First child always fails (simulating a DispatchWork hard error).
    a = _ScriptNode("A", [Status.FAILURE] * 3)
    b = _ScriptNode("B", [Status.SUCCESS] * 3)
    loop = LoopSeq([a, b], max_iters=3, name="WorkLoop")
    bb = _bb()
    assert loop.tick(bb) is Status.SUCCESS
    assert a.tick_count == 3  # tried in each of three iters
    assert b.tick_count == 0  # never reached because A always fails


# ---------------------------------------------------------------------------
# Extra: max_iters must be >= 1
# ---------------------------------------------------------------------------

def test_max_iters_must_be_positive():
    import pytest
    with pytest.raises(ValueError):
        LoopSeq([_ScriptNode("X", [Status.SUCCESS])], max_iters=0)


# ---------------------------------------------------------------------------
# Extra: alias only updates when name == "WorkLoop"
# ---------------------------------------------------------------------------

def test_alias_only_for_workloop_name():
    a = _ScriptNode("A", [Status.RUNNING])
    loop = LoopSeq([a], max_iters=3, name="OtherLoop")
    bb = _bb()
    loop.tick(bb)
    assert bb.work_loop_iter is None  # alias not touched
    assert getattr(bb, "_loopseq_OtherLoop_iter") == 1
