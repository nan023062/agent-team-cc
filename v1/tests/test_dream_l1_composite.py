"""L1 — DreamBlackboard + SequenceTolerant unit tests.

No persistence, no MCP — pure in-memory.
"""
from __future__ import annotations

from engine.execution.core.node import Node, Status
from engine.dream.core.blackboard import DreamBlackboard, FIELDS
from engine.dream.core.composite_tolerant import SequenceTolerant


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _StubNode(Node):
    def __init__(self, name: str, ret: Status) -> None:
        self.name = name
        self._ret = ret
        self.ticks = 0

    def tick(self, bb) -> Status:
        self.ticks += 1
        return self._ret


class _YieldOnce(Node):
    """First tick → RUNNING; second tick → terminal_ret."""

    def __init__(self, name: str, terminal_ret: Status) -> None:
        self.name = name
        self._terminal = terminal_ret
        self.ticks = 0

    def tick(self, bb) -> Status:
        self.ticks += 1
        if self.ticks == 1:
            return Status.RUNNING
        return self._terminal


def _bb() -> DreamBlackboard:
    bb = DreamBlackboard()
    bb.run_id = "dream-test"
    return bb


# ---------------------------------------------------------------------------
# DreamBlackboard tests
# ---------------------------------------------------------------------------

def test_dream_bb_field_count_is_19():
    assert len(FIELDS) == 19


def test_dream_bb_setattr_marks_dirty():
    bb = DreamBlackboard()
    assert bb.dirty is False
    bb.run_id = "r1"
    assert bb.dirty is True
    bb.clear_dirty()
    assert bb.dirty is False


def test_dream_bb_identifier_protocol():
    bb = DreamBlackboard()
    assert bb.identifier is None
    bb.run_id = "abc123"
    assert bb.identifier == "abc123"


def test_dream_bb_roundtrip_preserves_fields():
    bb = DreamBlackboard()
    bb.run_id = "r1"
    bb.trigger_reason = "catchup"
    bb.step_results = {"memory": "success"}
    bb.bb_status = "running"
    d = bb.to_dict()
    bb2 = DreamBlackboard.from_dict(d)
    assert bb2.run_id == "r1"
    assert bb2.trigger_reason == "catchup"
    assert bb2.step_results == {"memory": "success"}
    assert bb2.bb_status == "running"
    assert bb2.dirty is False


# ---------------------------------------------------------------------------
# SequenceTolerant tests
# ---------------------------------------------------------------------------

def test_seq_tolerant_all_success_returns_success_and_records_each():
    a = _StubNode("memory", Status.SUCCESS)
    b = _StubNode("knowledge", Status.SUCCESS)
    c = _StubNode("capability", Status.SUCCESS)
    st = SequenceTolerant([a, b, c], name="DreamStepsTolerant")
    bb = _bb()
    assert st.tick(bb) is Status.SUCCESS
    assert bb.step_results == {
        "memory": "success",
        "knowledge": "success",
        "capability": "success",
    }
    assert (a.ticks, b.ticks, c.ticks) == (1, 1, 1)


def test_seq_tolerant_does_not_short_circuit_on_failure():
    a = _StubNode("memory", Status.FAILURE)
    b = _StubNode("knowledge", Status.SUCCESS)
    c = _StubNode("capability", Status.FAILURE)
    st = SequenceTolerant([a, b, c], name="T")
    bb = _bb()
    # at least one SUCCESS → overall SUCCESS
    assert st.tick(bb) is Status.SUCCESS
    assert bb.step_results == {
        "memory": "failure",
        "knowledge": "success",
        "capability": "failure",
    }
    # All three children must have been ticked.
    assert (a.ticks, b.ticks, c.ticks) == (1, 1, 1)


def test_seq_tolerant_all_failure_returns_failure():
    a = _StubNode("memory", Status.FAILURE)
    b = _StubNode("knowledge", Status.FAILURE)
    c = _StubNode("capability", Status.FAILURE)
    st = SequenceTolerant([a, b, c], name="T")
    bb = _bb()
    assert st.tick(bb) is Status.FAILURE
    assert bb.step_results == {
        "memory": "failure",
        "knowledge": "failure",
        "capability": "failure",
    }


def test_seq_tolerant_running_yields_without_recording_terminal():
    a = _StubNode("memory", Status.SUCCESS)
    b = _YieldOnce("knowledge", Status.SUCCESS)
    c = _StubNode("capability", Status.SUCCESS)
    st = SequenceTolerant([a, b, c], name="T")
    bb = _bb()
    # First tick: a SUCCESS, b RUNNING → return RUNNING; c untouched.
    assert st.tick(bb) is Status.RUNNING
    assert bb.step_results == {"memory": "success"}
    assert (a.ticks, b.ticks, c.ticks) == (1, 1, 0)


def test_seq_tolerant_resume_skips_recorded_children():
    # Simulate post-yield resume: bb already has memory=success recorded.
    a = _StubNode("memory", Status.SUCCESS)
    b = _StubNode("knowledge", Status.SUCCESS)
    c = _StubNode("capability", Status.SUCCESS)
    st = SequenceTolerant([a, b, c], name="T")
    bb = _bb()
    bb.step_results = {"memory": "success"}
    assert st.tick(bb) is Status.SUCCESS
    # a should NOT have been re-ticked (already recorded).
    assert a.ticks == 0
    assert (b.ticks, c.ticks) == (1, 1)
    assert bb.step_results == {
        "memory": "success",
        "knowledge": "success",
        "capability": "success",
    }
