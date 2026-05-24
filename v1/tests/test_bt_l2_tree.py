"""L2 — tree topology / decorator stacking invariants.

Static structural checks on the global ROOT to prevent silent topology drift.
"""
from __future__ import annotations

from engine.bt.actions.aggregate import Aggregate
from engine.bt.actions.decompose import Decompose
from engine.bt.actions.dispatch_parallel import DispatchParallel
from engine.bt.core.decorator import Catch, IterationGuard, LoopUntilConverge, Retry, Timeout, Trace
from engine.bt.tree.main_loop import ROOT, build_root


def _walk(n, acc=None):
    acc = acc if acc is not None else []
    acc.append(n)
    for ch in n.children():
        _walk(ch, acc)
    return acc


def test_root_structure_matches_design():
    """Expected stacking and presence of key nodes."""
    names = [n.name for n in _walk(ROOT)]
    expected = [
        "Root", "GlobalTimeout", "RootSeq",
        "InitTick", "RetryIntent", "IntentAnalyze",
        "ClarifyBranch", "AskClarify",
        "MainBody", "LoopRoot", "LoopSeqGuard", "LoopSeq",
        "Decompose", "RetryArchGate", "ArchGate",
        "RetryCallHR", "CallHR",
        "DispatchParallel", "Aggregate", "RetryConverge", "ConvergeJudge",
        "Respond", "CatchFlush", "FlushMemory",
    ]
    for ex in expected:
        assert ex in names, f"Missing node {ex} in tree"


def test_loop_seq_has_six_nodes_in_order():
    """LoopSeq children = [Decompose, RetryArchGate, RetryCallHR,
    DispatchParallel, Aggregate, RetryConverge]. Order is load-bearing:
    Architect (knowledge) must produce ContextPack before HR (capability)
    can assign agents; HR must finish before WorkAgentLeaf dispatches."""
    loop_seq = None
    for n in _walk(ROOT):
        if n.name == "LoopSeq":
            loop_seq = n
            break
    assert loop_seq is not None, "LoopSeq not found"
    child_names = [c.name for c in loop_seq.children()]
    assert child_names == [
        "Decompose", "RetryArchGate", "RetryCallHR",
        "DispatchParallel", "Aggregate", "RetryConverge",
    ], f"unexpected LoopSeq children: {child_names}"


def test_decorator_stack_outermost_is_trace_then_timeout():
    """Trace > Timeout > everything else per WORKFLOW-EXECUTION §3."""
    assert isinstance(ROOT, Trace)
    inner = ROOT.children()[0]
    assert isinstance(inner, Timeout)


def test_no_retry_around_decompose_dispatch_or_aggregate():
    """These three are non-idempotent — Retry around them is a code-review hard fail."""
    nodes = _walk(ROOT)
    for i, n in enumerate(nodes):
        if not isinstance(n, Retry):
            continue
        # Inspect the wrapped child (Retry has exactly one child).
        child = n.children()[0]
        assert not isinstance(child, Decompose), \
            "Retry must not wrap Decompose (non-idempotent: bumps iteration)"
        assert not isinstance(child, DispatchParallel), \
            "Retry must not wrap DispatchParallel (non-idempotent: dispatches subagents)"
        assert not isinstance(child, Aggregate), \
            "Retry must not wrap Aggregate (would re-derive same verdict)"


def test_loop_until_converge_wraps_iteration_guard():
    """LoopUntilConverge > IterationGuard > LoopSeq is the locked layering."""
    found = False
    for n in _walk(ROOT):
        if isinstance(n, LoopUntilConverge):
            child = n.children()[0]
            assert isinstance(child, IterationGuard), \
                "LoopUntilConverge must directly wrap IterationGuard"
            found = True
            break
    assert found, "LoopUntilConverge missing from tree"


def test_flush_memory_wrapped_in_catch():
    """FlushMemory failures must never break the tick."""
    for n in _walk(ROOT):
        if isinstance(n, Catch):
            child = n.children()[0]
            if child.name == "FlushMemory":
                return
    raise AssertionError("FlushMemory not wrapped in Catch")


def test_build_root_is_pure_factory():
    """build_root() should return a fresh tree on each call (no shared state)."""
    a = build_root()
    b = build_root()
    assert a is not b
    assert a.name == b.name == "Root"
