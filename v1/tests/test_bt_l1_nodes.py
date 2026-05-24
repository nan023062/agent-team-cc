"""L1 — node-level unit tests for engine.bt.

Covers core composites/decorators + each Action's tick/on_resume contract.
No persistence, no MCP — pure in-memory.
"""
from __future__ import annotations

import pytest

from engine.bt.actions.aggregate import Aggregate
from engine.bt.actions.arch_gate import ArchGate
from engine.bt.actions.ask_clarify import AskClarify
from engine.bt.actions.call_hr import CallHR
from engine.bt.actions.converge_judge import ConvergeJudge
from engine.bt.actions.decompose import Decompose
from engine.bt.actions.dispatch_parallel import DispatchParallel, WorkAgentLeaf
from engine.bt.actions.init_tick import InitTick
from engine.bt.actions.intent_analyze import IntentAnalyze, IntentRules, NullLLM
from engine.bt.core.blackboard import Blackboard
from engine.bt.core.composite import Parallel, Selector, Sequence
from engine.bt.core.node import Node, Status


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


def _bb(**overrides) -> Blackboard:
    bb = Blackboard()
    bb.tick_id = "test"
    bb.user_request = overrides.get("user_request", "")
    bb.iteration_cap = overrides.get("iteration_cap", 5)
    for k, v in overrides.items():
        setattr(bb, k, v)
    return bb


# ---------------------------------------------------------------------------
# Composites
# ---------------------------------------------------------------------------

def test_sequence_short_circuits_on_failure():
    a = _StubNode("A", Status.SUCCESS)
    b = _StubNode("B", Status.FAILURE)
    c = _StubNode("C", Status.SUCCESS)
    seq = Sequence([a, b, c], name="S")
    assert seq.tick(_bb()) is Status.FAILURE
    assert (a.ticks, b.ticks, c.ticks) == (1, 1, 0)


def test_selector_short_circuits_on_success():
    a = _StubNode("A", Status.FAILURE)
    b = _StubNode("B", Status.SUCCESS)
    c = _StubNode("C", Status.FAILURE)
    sel = Selector([a, b, c], name="Sel")
    assert sel.tick(_bb()) is Status.SUCCESS
    assert (a.ticks, b.ticks, c.ticks) == (1, 1, 0)


def test_parallel_first_running_wins():
    a = _StubNode("A", Status.SUCCESS)
    b = _StubNode("B", Status.RUNNING)
    c = _StubNode("C", Status.SUCCESS)
    p = Parallel([a, b, c], name="P")
    assert p.tick(_bb()) is Status.RUNNING
    # c not ticked because b's RUNNING bubbled up
    assert (a.ticks, b.ticks, c.ticks) == (1, 1, 0)


# ---------------------------------------------------------------------------
# IntentAnalyze
# ---------------------------------------------------------------------------

def test_intent_analyze_rule_hit():
    bb = _bb(user_request="实现 login API 模块")
    node = IntentAnalyze(rules=IntentRules.default(), llm=NullLLM())
    assert node.tick(bb) is Status.SUCCESS
    assert bb.intent["kind"] == "execution"
    assert bb.intent["target_agent"] == "programmer"


def test_intent_analyze_llm_fallback_unavailable():
    # Unknown free-form request → no rule hit → NullLLM raises → FAILURE.
    bb = _bb(user_request="zzz qrx blarp 玳瑁")
    node = IntentAnalyze(rules=IntentRules.default(), llm=NullLLM())
    assert node.tick(bb) is Status.FAILURE
    assert bb.interrupt_reason == "llm_fallback_required_but_unavailable"


def test_intent_analyze_empty_request_clarifies():
    bb = _bb(user_request="")
    node = IntentAnalyze(rules=IntentRules.default(), llm=NullLLM())
    assert node.tick(bb) is Status.SUCCESS
    assert bb.intent["clarification_needed"] is True
    assert bb.intent["clarifying_question"]


# ---------------------------------------------------------------------------
# Decompose
# ---------------------------------------------------------------------------

def test_decompose_writes_dispatch_plan_execution():
    bb = _bb(user_request="实现 login API",
             intent={"kind": "execution", "target_agent": "programmer"})
    node = Decompose(llm=None)
    assert node.tick(bb) is Status.SUCCESS
    plan = bb.dispatch_plan
    assert len(plan) == 1
    assert plan[0]["target_agent"] == "programmer"
    assert "arch_context" in plan[0]["depends_on"]
    assert bb.iteration == 1


def test_decompose_pure_query_skips_arch_gate():
    bb = _bb(user_request="查询模块",
             intent={"kind": "pure_query", "target_agent": "architect"})
    node = Decompose(llm=None)
    assert node.tick(bb) is Status.SUCCESS
    assert bb.dispatch_plan[0]["depends_on"] == []


def test_decompose_resets_subtask_results_per_iteration():
    bb = _bb(user_request="实现 login API",
             intent={"kind": "execution"})
    bb.subtask_results = {"old": {"status": "needs_arch"}}
    node = Decompose(llm=None)
    node.tick(bb)
    assert bb.subtask_results == {}


# ---------------------------------------------------------------------------
# ArchGate
# ---------------------------------------------------------------------------

def test_arch_gate_yields_then_resumes():
    bb = _bb(user_request="x",
             dispatch_plan=[{"id": "t1", "depends_on": ["arch_context"]}])
    node = ArchGate()
    assert node.tick(bb) is Status.RUNNING
    assert bb.pending_dispatch is not None
    assert bb.pending_dispatch.agent_type == "architect"
    node.on_resume(bb, "CTX-PACK-1")
    assert bb.arch_context["output"] == "CTX-PACK-1"
    assert bb.pending_dispatch is None
    # Second tick should pass through.
    assert node.tick(bb) is Status.SUCCESS


def test_arch_gate_skips_when_plan_doesnt_need_it():
    bb = _bb(dispatch_plan=[{"id": "t1", "depends_on": []}])
    assert ArchGate().tick(bb) is Status.SUCCESS
    assert bb.pending_dispatch is None


# ---------------------------------------------------------------------------
# CallHR
# ---------------------------------------------------------------------------

def test_call_hr_yields_then_resumes():
    bb = _bb(user_request="x",
             dispatch_plan=[{"id": "t1", "depends_on": ["arch_context"],
                             "module_path": "engine/foo", "prompt": "do it"}],
             arch_context={"output": "ContextPack-A", "kind": "context_pack_raw"})
    node = CallHR()
    assert node.tick(bb) is Status.RUNNING
    assert bb.pending_dispatch is not None
    assert bb.pending_dispatch.agent_type == "hr"
    assert bb.pending_dispatch.agent_file == ".claude/agents/hr/hr.md"
    reply = "subtask_id=t1 agent_file=.claude/agents/programmer/programmer.md capability=py"
    node.on_resume(bb, reply)
    assert bb.agent_list == [{
        "subtask_id": "t1",
        "target_agent_file": ".claude/agents/programmer/programmer.md",
        "agent_capability": "py",
    }]
    assert bb.pending_dispatch is None
    # Second tick — required subset of existing → SUCCESS without re-dispatch.
    assert node.tick(bb) is Status.SUCCESS


def test_call_hr_skips_when_no_execution_subtasks():
    # All subtasks are pure_query (no arch_context dep) → HR not consulted.
    bb = _bb(dispatch_plan=[{"id": "t1", "depends_on": []}])
    node = CallHR()
    assert node.tick(bb) is Status.SUCCESS
    assert bb.pending_dispatch is None
    assert bb.agent_list is None


def test_call_hr_gap_sets_interrupt():
    bb = _bb(dispatch_plan=[{"id": "t1", "depends_on": ["arch_context"],
                             "prompt": "p"}])
    node = CallHR()
    assert node.tick(bb) is Status.RUNNING
    node.on_resume(bb, "agent_gap: no agent for engine/foo\nplease recruit")
    assert bb.interrupt_reason and "agent_gap" in bb.interrupt_reason
    # Next tick sees the interrupt token → FAILURE (LoopSeq Sequence stops).
    assert node.tick(bb) is Status.FAILURE


# ---------------------------------------------------------------------------
# WorkAgentLeaf + DispatchParallel
# ---------------------------------------------------------------------------

def test_work_agent_leaf_yields_with_subtask_id():
    bb = _bb(dispatch_plan=[
        {"id": "t1", "target_agent_file": ".claude/agents/programmer/programmer.md",
         "prompt": "do stuff", "depends_on": []}
    ])
    leaf = WorkAgentLeaf(subtask_id="t1")
    assert leaf.tick(bb) is Status.RUNNING
    assert bb.pending_dispatch.subtask_id == "t1"
    assert bb.pending_dispatch.agent_type == "work"


def test_work_agent_leaf_prefers_agent_list_over_subtask_file():
    """HR's bb.agent_list wins over the subtask's own target_agent_file."""
    bb = _bb(dispatch_plan=[
        {"id": "t1", "target_agent_file": ".claude/agents/old/old.md",
         "prompt": "p", "depends_on": ["arch_context"]}
    ])
    bb.agent_list = [{"subtask_id": "t1",
                      "target_agent_file": ".claude/agents/hr-picked/x.md",
                      "agent_capability": "py"}]
    leaf = WorkAgentLeaf(subtask_id="t1")
    assert leaf.tick(bb) is Status.RUNNING
    assert bb.pending_dispatch.agent_file == ".claude/agents/hr-picked/x.md"


def test_work_agent_leaf_parses_needs_arch_marker():
    bb = _bb(dispatch_plan=[
        {"id": "t1", "target_agent_file": "x", "prompt": "p", "depends_on": []}
    ])
    leaf = WorkAgentLeaf(subtask_id="t1")
    leaf.tick(bb)
    leaf.on_resume(bb, "stuff\nNEEDS_ARCH_DECISION: conflict\n- context: x")
    r = bb.subtask_results["t1"]
    assert r["needs_arch_decision"] is True
    assert r["status"] == "needs_arch"


def test_dispatch_parallel_completes_when_all_results_present():
    bb = _bb(dispatch_plan=[{"id": "t1", "target_agent_file": "x", "prompt": "p", "depends_on": []}])
    bb.subtask_results = {"t1": {"status": "ok", "output": "done"}}
    dp = DispatchParallel()
    assert dp.tick(bb) is Status.SUCCESS


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

def test_aggregate_passes_on_normal_results():
    bb = _bb()
    bb.subtask_results = {"t1": {"status": "ok", "output": "ok"}}
    bb.iteration = 1
    assert Aggregate().tick(bb) is Status.SUCCESS
    assert bb.interrupt_reason is None


def test_aggregate_detects_no_progress():
    bb = _bb()
    bb.subtask_results = {"t1": {"status": "error", "output": "fail"}}
    bb.iteration = 2  # > 1 triggers no-progress check
    assert Aggregate().tick(bb) is Status.FAILURE
    assert "no_progress" in (bb.interrupt_reason or "")


def test_aggregate_detects_conflict():
    bb = _bb()
    bb.subtask_results = {
        "t1": {"status": "ok", "output": "CONFLICT: choose A"},
        "t2": {"status": "ok", "output": "CONFLICT: choose B"},
    }
    bb.iteration = 1
    assert Aggregate().tick(bb) is Status.FAILURE
    assert "conflict" in (bb.interrupt_reason or "")


# ---------------------------------------------------------------------------
# ConvergeJudge
# ---------------------------------------------------------------------------

def test_converge_judge_rule_done():
    bb = _bb()
    bb.subtask_results = {"t1": {"status": "ok", "output": "x"}}
    bb.iteration = 1
    assert ConvergeJudge(llm=None).tick(bb) is Status.SUCCESS
    assert bb.converge_signal == "done"
    assert bb.final_response


def test_converge_judge_rule_loop_on_needs_arch():
    bb = _bb()
    bb.subtask_results = {"t1": {"status": "needs_arch",
                                 "output": "NEEDS_ARCH_DECISION: x",
                                 "needs_arch_decision": True}}
    bb.arch_context = {"old": True}
    assert ConvergeJudge(llm=None).tick(bb) is Status.SUCCESS
    assert bb.converge_signal == "loop"
    assert bb.arch_context is None  # reset so ArchGate yields again


def test_converge_judge_rule_interrupt_on_fatal():
    bb = _bb()
    bb.subtask_results = {
        "t1": {"status": "error", "output": "boom", "retryable": False}
    }
    assert ConvergeJudge(llm=None).tick(bb) is Status.SUCCESS
    assert bb.converge_signal == "interrupt"
    assert "fatal_subtask_error" in (bb.interrupt_reason or "")


def test_converge_judge_rule_interrupt_from_existing_reason():
    bb = _bb(interrupt_reason="iteration_cap_exceeded")
    assert ConvergeJudge(llm=None).tick(bb) is Status.SUCCESS
    assert bb.converge_signal == "interrupt"


# ---------------------------------------------------------------------------
# InitTick + AskClarify
# ---------------------------------------------------------------------------

def test_init_tick_never_fails():
    bb = _bb()
    assert InitTick().tick(bb) is Status.SUCCESS


def test_ask_clarify_terminates_loop():
    bb = _bb(intent={"clarifying_question": "Which module?"})
    assert AskClarify().tick(bb) is Status.SUCCESS
    assert bb.final_response == "Which module?"
    assert bb.converge_signal == "done"
