"""L2 — dream tree topology + decorator stacking tests.

Builds the static root via build_dream_root() and asserts shape:
  - exactly the children listed in WORKFLOW-DREAM §三
  - decorator stacking order: Trace > Timeout > Catch
  - SequenceTolerant placement (not Sequence) for governance steps
"""
from __future__ import annotations

from pathlib import Path

import pytest

from engine.bt.core.composite import Sequence
from engine.bt.core.decorator import Catch, Timeout, Trace
from engine.dream.core.composite_tolerant import SequenceTolerant
from engine.dream.tree.dream_loop import build_dream_root


@pytest.fixture
def root(tmp_path: Path):
    return build_dream_root(
        scheduler_root=tmp_path / "scheduler",
        memory_store_dir=tmp_path / "memory",
    )


def _names(nodes):
    return [n.name for n in nodes]


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------

def test_root_is_trace_wrapped_timeout(root):
    assert isinstance(root, Trace)
    assert root.name == "DreamRoot"
    inner = root.children()[0]
    assert isinstance(inner, Timeout)
    assert inner.name == "DreamGlobalTimeout"


def test_body_has_four_children_in_locked_order(root):
    body = root.children()[0].children()[0]  # Trace → Timeout → Sequence
    assert isinstance(body, Sequence)
    assert body.name == "DreamBody"
    assert _names(body.children()) == [
        "InitDreamTick",
        "GovernanceSteps",
        "EmitReport",
        "FinalizeDreamTick",
    ]


def test_governance_steps_uses_sequence_tolerant(root):
    body = root.children()[0].children()[0]
    steps = body.children()[1]
    assert isinstance(steps, SequenceTolerant)
    # Three governance step wrappers, NOT raw sequences.
    assert _names(steps.children()) == [
        "MemoryStepCatch",
        "ArchStepCatch",
        "HRStepCatch",
    ]


def test_each_step_is_catch_over_timeout(root):
    body = root.children()[0].children()[0]
    steps = body.children()[1]
    for child in steps.children():
        assert isinstance(child, Catch), f"{child.name} is not Catch-wrapped"
        # Catch wraps Timeout
        inner = child.children()[0]
        assert isinstance(inner, Timeout), f"{child.name} inner is not Timeout"


def test_memory_step_has_four_action_children(root):
    body = root.children()[0].children()[0]
    steps = body.children()[1]
    mem_catch = steps.children()[0]
    mem_timeout = mem_catch.children()[0]
    mem_seq = mem_timeout.children()[0]
    assert isinstance(mem_seq, Sequence)
    assert _names(mem_seq.children()) == [
        "MemHealthScan",
        "MemCompact",
        "MemSweepExpired",
        "MemRebuildIndex",
    ]


def test_arch_and_hr_steps_have_dispatch_then_collect(root):
    body = root.children()[0].children()[0]
    steps = body.children()[1]
    arch_seq = steps.children()[1].children()[0].children()[0]
    hr_seq = steps.children()[2].children()[0].children()[0]
    assert _names(arch_seq.children()) == ["DispatchArchGovern", "CollectArchAdvice"]
    assert _names(hr_seq.children()) == ["DispatchHRGovern", "CollectHRAdvice"]


def test_emit_and_finalize_live_outside_governance_steps(root):
    """Critical invariant: EmitReport + FinalizeDreamTick must always run,
    even if all three governance steps failed → they are siblings of
    GovernanceSteps, not children of it."""
    body = root.children()[0].children()[0]
    sibling_names = _names(body.children())
    assert "EmitReport" in sibling_names
    assert "FinalizeDreamTick" in sibling_names
    # And they are NOT inside the SequenceTolerant.
    steps = body.children()[1]
    descendants: list[str] = []
    stack = list(steps.children())
    while stack:
        n = stack.pop()
        descendants.append(n.name)
        stack.extend(n.children())
    assert "EmitReport" not in descendants
    assert "FinalizeDreamTick" not in descendants
