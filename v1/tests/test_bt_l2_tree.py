"""L2 — tree topology / decorator stacking invariants (v3.6).

Static structural checks on the global ROOT to prevent silent topology drift.

Post-t? (5-mode): the root branch is now a SwitchBranch with five cases
(conversation / architect / hr / audit / execution). The three core-agent
branches each dispatch one core agent (architect / hr / auditor) and run
Respond on the result. v3.6 removed the HrExecution sub-loop: the execution
branch is now a straight Architect → Work pipeline; main agent maps
required_capability → agent_file via MCP agent_list at dispatch time.
"""
from __future__ import annotations

from engine.execution.actions.dispatch_core_agent import DispatchCoreAgent
from engine.execution.actions.dispatch_work import DispatchWork
from engine.core.composite import Sequence, SwitchBranch
from engine.core.decorator import Catch, Retry, Timeout, Trace
from engine.execution.tree.main_loop import ROOT, build_root


def _walk(n, acc=None):
    acc = acc if acc is not None else []
    acc.append(n)
    for ch in n.children():
        _walk(ch, acc)
    return acc


def test_root_structure_matches_design():
    """Expected stacking and presence of key v3.5 nodes.

    Five-mode topology: the legacy ModeBranch was replaced by a
    SwitchBranch (`ModeSwitch`) with five case branches, three of which
    are the new core-agent branches (Architect / HR / Audit).
    """
    names = [n.name for n in _walk(ROOT)]
    expected = [
        "Root", "GlobalTimeout", "RootSeq",
        "InitTick", "ModeClassify",
        "ModeSwitch",
        # Conversation branch
        "DirectReply",
        # Three core-agent branches (peer to Work Agent)
        "ArchitectBranch", "DispatchCoreAgent#architect", "Respond#architect",
        "HrBranch",        "DispatchCoreAgent#hr",        "Respond#hr",
        "AuditBranch",     "DispatchCoreAgent#auditor",   "Respond#audit",
        # Execution branch
        "ExecutionSeq",
        "ArchitectExecution",
        "DispatchWork",
        "Respond",
        "CatchFlush", "FlushMemory",
    ]
    for ex in expected:
        assert ex in names, f"Missing node {ex} in tree; got {names}"
    # v3.6 removed the HrExecution sub-loop — required_capability → agent_file
    # lookup moved out of the engine into the main agent (MCP agent_list).
    assert "HrExecution" not in names, \
        f"HrExecution must NOT appear in ROOT walk post-v3.6; got {names}"


def test_execution_seq_has_four_nodes_in_order():
    """ExecutionSeq children = [ArchitectExecution, DispatchWork,
    Respond, CatchFlush]. Order is load-bearing: the Architect subtree
    must produce arch_plan (with required_capability per task) before
    WorkAgentLeaf dispatches."""
    exec_seq = None
    for n in _walk(ROOT):
        if n.name == "ExecutionSeq":
            exec_seq = n
            break
    assert exec_seq is not None, "ExecutionSeq not found"
    child_names = [c.name for c in exec_seq.children()]
    assert child_names == [
        "ArchitectExecution",
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


def test_mode_switch_present_with_five_cases():
    """ModeSwitch is a SwitchBranch routing the five mode strings to
    five distinct subtrees. Default falls back to the execution branch
    (defensive — unknown mode behaves like execution)."""
    switch = None
    for n in _walk(ROOT):
        if isinstance(n, SwitchBranch) and n.name == "ModeSwitch":
            switch = n
            break
    assert switch is not None, "ModeSwitch (SwitchBranch) not found in tree"

    cases = switch._cases  # noqa: SLF001 — structural assertion
    assert set(cases.keys()) == {
        "conversation", "architect", "hr", "audit", "execution",
    }, f"unexpected ModeSwitch cases: {sorted(cases)}"

    assert cases["conversation"].name == "DirectReply"
    assert cases["architect"].name == "ArchitectBranch"
    assert cases["hr"].name == "HrBranch"
    assert cases["audit"].name == "AuditBranch"
    assert cases["execution"].name == "ExecutionSeq"

    # Default must be defined (defensive fallback to execution).
    assert switch._default is not None, "ModeSwitch must declare a default"
    assert switch._default.name == "ExecutionSeq"


def test_core_agent_branches_are_dispatch_then_respond():
    """Each of the three core-agent branches must be a 2-node Sequence:
    DispatchCoreAgent#<type> followed by Respond#<label>. The
    DispatchCoreAgent leaf carries the correct agent_type AND the
    matching `.claude/agents/<x>/<x>.md` agent_file."""
    expected = {
        "ArchitectBranch": ("architect", ".claude/agents/architect/architect.md",
                            "Respond#architect"),
        "HrBranch":        ("hr",        ".claude/agents/hr/hr.md",
                            "Respond#hr"),
        "AuditBranch":     ("auditor",   ".claude/agents/auditor/auditor.md",
                            "Respond#audit"),
    }
    found: dict[str, Sequence] = {}
    for n in _walk(ROOT):
        if n.name in expected and isinstance(n, Sequence):
            found[n.name] = n
    assert set(found) == set(expected), \
        f"missing core-agent branches: {set(expected) - set(found)}"

    for branch_name, (agent_type, agent_file, respond_name) in expected.items():
        kids = found[branch_name].children()
        assert len(kids) == 2, \
            f"{branch_name} must have exactly [DispatchCoreAgent, Respond]"
        dispatch, respond = kids
        assert isinstance(dispatch, DispatchCoreAgent), \
            f"{branch_name}[0] must be DispatchCoreAgent, got {type(dispatch).__name__}"
        assert dispatch.agent_type == agent_type
        assert dispatch.agent_file == agent_file
        assert dispatch.name == f"DispatchCoreAgent#{agent_type}"
        assert respond.name == respond_name


def test_build_root_is_pure_factory():
    """build_root() should return a fresh tree on each call (no shared state)."""
    a = build_root()
    b = build_root()
    assert a is not b
    assert a.name == b.name == "Root"
