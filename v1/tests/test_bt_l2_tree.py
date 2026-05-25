"""L2 — tree topology / decorator stacking invariants (v3).

Static structural checks on the global ROOT to prevent silent topology drift.
"""
from __future__ import annotations

from engine.bt.actions.dispatch_work import DispatchWork
from engine.bt.core.decorator import Catch, Retry, Timeout, Trace
from engine.bt.tree.main_loop import ROOT, build_root


def _walk(n, acc=None):
    acc = acc if acc is not None else []
    acc.append(n)
    for ch in n.children():
        _walk(ch, acc)
    return acc


def test_root_structure_matches_design():
    """Expected stacking and presence of key v3 nodes."""
    names = [n.name for n in _walk(ROOT)]
    expected = [
        "Root", "GlobalTimeout", "RootSeq",
        "InitTick", "ModeClassify",
        "ModeBranch",
        "DirectReply",
        "ExecutionSeq",
        "RetryDispatchArchitect", "DispatchArchitect",
        "RetryDispatchHR", "DispatchHR",
        "DispatchWork",
        "Respond",
        "CatchFlush", "FlushMemory",
    ]
    for ex in expected:
        assert ex in names, f"Missing node {ex} in tree; got {names}"


def test_execution_seq_has_five_nodes_in_order():
    """ExecutionSeq children = [RetryDispatchArchitect, RetryDispatchHR,
    DispatchWork, Respond, CatchFlush]. Order is load-bearing: Architect
    must produce arch_plan before HR can assign agents; HR must finish
    before WorkAgentLeaf dispatches."""
    exec_seq = None
    for n in _walk(ROOT):
        if n.name == "ExecutionSeq":
            exec_seq = n
            break
    assert exec_seq is not None, "ExecutionSeq not found"
    child_names = [c.name for c in exec_seq.children()]
    assert child_names == [
        "RetryDispatchArchitect", "RetryDispatchHR",
        "DispatchWork", "Respond", "CatchFlush",
    ], f"unexpected ExecutionSeq children: {child_names}"


def test_decorator_stack_outermost_is_trace_then_timeout():
    """Trace > Timeout > everything else per WORKFLOW-EXECUTION §5."""
    assert isinstance(ROOT, Trace)
    inner = ROOT.children()[0]
    assert isinstance(inner, Timeout)


def test_no_retry_around_dispatch_work():
    """DispatchWork is non-idempotent — Retry around it is a code-review hard fail."""
    for n in _walk(ROOT):
        if not isinstance(n, Retry):
            continue
        child = n.children()[0]
        assert not isinstance(child, DispatchWork), \
            "Retry must not wrap DispatchWork (non-idempotent: dispatches subagents)"


def test_flush_memory_wrapped_in_catch():
    """FlushMemory failures must never break the tick."""
    for n in _walk(ROOT):
        if isinstance(n, Catch):
            child = n.children()[0]
            if child.name == "FlushMemory":
                return
    raise AssertionError("FlushMemory not wrapped in Catch")


def test_mode_branch_present_with_two_children():
    """ModeBranch routes between conversation and execution paths."""
    from engine.bt.core.composite import ModeBranch
    for n in _walk(ROOT):
        if isinstance(n, ModeBranch):
            kids = n.children()
            assert len(kids) == 2
            names = {c.name for c in kids}
            assert names == {"DirectReply", "ExecutionSeq"}
            return
    raise AssertionError("ModeBranch not found in tree")


def test_build_root_is_pure_factory():
    """build_root() should return a fresh tree on each call (no shared state)."""
    a = build_root()
    b = build_root()
    assert a is not b
    assert a.name == b.name == "Root"
