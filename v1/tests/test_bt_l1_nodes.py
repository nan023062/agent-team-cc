"""L1 — node-level unit tests for engine.execution (v3).

Covers core composites/decorators + each v3 Action's tick/on_resume contract.
No persistence, no MCP — pure in-memory.
"""
from __future__ import annotations

from engine.execution.actions.direct_reply import DirectReply
from engine.execution.actions.dispatch_work import DispatchWork, WorkAgentLeaf
from engine.execution.actions.init_tick import InitTick
from engine.execution.actions.mode_classify import ModeClassify
from engine.execution.actions.respond import Respond
from engine.core.blackboard import Blackboard
from engine.core.composite import (
    AlwaysSuccess,
    ModeBranch,
    Parallel,
    Selector,
    Sequence,
    SwitchBranch,
)
from engine.core.node import Node, Status


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


def test_mode_branch_routes_on_bb_mode():
    yes = _StubNode("Y", Status.SUCCESS)
    no = _StubNode("N", Status.SUCCESS)
    branch = ModeBranch(conversation=yes, execution=no, name="MB")
    bb = _bb()
    bb.mode = "conversation"
    branch.tick(bb)
    assert (yes.ticks, no.ticks) == (1, 0)
    bb.mode = "execution"
    branch.tick(bb)
    assert (yes.ticks, no.ticks) == (1, 1)


def test_mode_branch_defaults_to_execution_when_unset():
    yes = _StubNode("Y", Status.SUCCESS)
    no = _StubNode("N", Status.SUCCESS)
    branch = ModeBranch(conversation=yes, execution=no, name="MB")
    bb = _bb()  # bb.mode is None
    branch.tick(bb)
    assert (yes.ticks, no.ticks) == (0, 1)


# ---------------------------------------------------------------------------
# InitTick
# ---------------------------------------------------------------------------

def test_init_tick_never_fails():
    bb = _bb()
    assert InitTick().tick(bb) is Status.SUCCESS


# ---------------------------------------------------------------------------
# ModeClassify
# ---------------------------------------------------------------------------

def test_mode_classify_empty_request_is_conversation():
    bb = _bb(user_request="")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "conversation"


def test_mode_classify_question_is_conversation():
    bb = _bb(user_request="What is CBIM?")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "conversation"


def test_mode_classify_chinese_question_is_conversation():
    bb = _bb(user_request="什么是 CBIM？")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "conversation"


def test_mode_classify_implement_verb_is_execution():
    bb = _bb(user_request="实现 login API 模块")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


def test_mode_classify_english_implement_is_execution():
    bb = _bb(user_request="implement the login API module")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


def test_mode_classify_rule_miss_defaults_to_execution_under_null_llm():
    bb = _bb(user_request="zzz qrx blarp 玳瑁")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


def test_mode_classify_english_design_is_architect():
    bb = _bb(user_request="design a new login module")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "architect"


def test_mode_classify_chinese_design_is_architect():
    bb = _bb(user_request="给登录功能做一份设计")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "architect"


def test_mode_classify_english_recruit_is_hr():
    bb = _bb(user_request="recruit a python backend engineer agent")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "hr"


def test_mode_classify_chinese_recruit_is_hr():
    bb = _bb(user_request="招一个会写 Rust 的工作 agent")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "hr"


def test_mode_classify_english_audit_is_audit():
    bb = _bb(user_request="please audit the dispatcher implementation")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "audit"


def test_mode_classify_chinese_audit_is_audit():
    bb = _bb(user_request="对最近的改动做一次独立审查")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "audit"


def test_mode_classify_execution_verb_wins_over_design_keyword():
    # v3.7: precedence is execution-verb > architect-request. With both
    # "design" and "implement" present the user has explicitly said they
    # want it implemented — that's execution. The architect step happens
    # automatically inside ExecutionSeq via the ArchitectExecution subtree.
    bb = _bb(user_request="design and implement a new auth module")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


# v3.7 anti-regression — bare topic words must NOT hijack execution requests.

def test_mode_classify_implement_audit_logging_is_execution():
    bb = _bb(user_request="implement audit logging")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


def test_mode_classify_refactor_architecture_module_is_execution():
    bb = _bb(user_request="refactor the architecture module")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


def test_mode_classify_add_agent_recruitment_endpoint_is_execution():
    bb = _bb(user_request="add agent recruitment endpoint")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


def test_mode_classify_fix_design_doc_typo_is_execution():
    bb = _bb(user_request="fix the design doc typo")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


def test_mode_classify_build_code_review_pipeline_is_execution():
    bb = _bb(user_request="build a code review pipeline")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


def test_mode_classify_chinese_refactor_recruitment_flow_is_execution():
    bb = _bb(user_request="重构招聘流程代码")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


# v3.7 architect-preempt — split/merge/deprecate a module, update .dna.

def test_mode_classify_chinese_split_module_is_architect_preempt():
    bb = _bb(user_request="拆分 auth 模块")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "architect"


def test_mode_classify_english_update_dna_is_architect_preempt():
    bb = _bb(user_request="update .dna for auth module")
    assert ModeClassify().tick(bb) is Status.SUCCESS
    assert bb.mode == "architect"


# PR-D: ModeClassify no longer has an LLM fallback branch. Rule miss
# defaults to "execution"; the architect agent itself may reroute via
# status="needs_user_input" if the request turns out conversational.
# The historical _StubModeLLM tests (LLM verdict round-trip) are gone.


# ---------------------------------------------------------------------------
# DirectReply (PR-D: passthrough only, no LLM hook)
# ---------------------------------------------------------------------------

def test_direct_reply_writes_final_response_passthrough():
    bb = _bb(user_request="什么是 CBIM？")
    assert DirectReply().tick(bb) is Status.SUCCESS
    assert bb.final_response == "（对话模式）什么是 CBIM？"


def test_direct_reply_empty_request_writes_prompt_hint():
    bb = _bb(user_request="")
    assert DirectReply().tick(bb) is Status.SUCCESS
    assert bb.final_response == "请描述你的需求。"


# ---------------------------------------------------------------------------
# WorkAgentLeaf + DispatchWork
# ---------------------------------------------------------------------------

def test_work_agent_leaf_yields_with_task_id():
    """v3.6: work yield carries agent_file=None; required_capability is
    forwarded from arch_plan task and main agent does the lookup."""
    bb = _bb(arch_plan=[
        {"id": "a1", "description": "do stuff",
         "required_capability": "programmer"},
    ])
    leaf = WorkAgentLeaf(task_id="a1")
    assert leaf.tick(bb) is Status.RUNNING
    assert bb.pending_dispatch.subtask_id == "a1"
    assert bb.pending_dispatch.agent_type == "work"
    assert bb.pending_dispatch.agent_file is None
    assert bb.pending_dispatch.required_capability == "programmer"


def test_work_agent_leaf_forwards_required_capability_verbatim():
    """Focused: whatever string the arch_plan task puts in
    required_capability must land verbatim on the DispatchRequest."""
    for cap in ("programmer", "tester", "doc_writer", "generalist"):
        bb = _bb(arch_plan=[
            {"id": "t1", "description": "d", "required_capability": cap},
        ])
        leaf = WorkAgentLeaf(task_id="t1")
        assert leaf.tick(bb) is Status.RUNNING
        assert bb.pending_dispatch.required_capability == cap, \
            f"expected required_capability={cap!r}, got {bb.pending_dispatch.required_capability!r}"
        assert bb.pending_dispatch.agent_file is None


def test_work_agent_leaf_missing_capability_yields_none():
    """When arch_plan task omits required_capability, the DispatchRequest
    carries None (main agent then falls back to the default programmer
    agent_file). The leaf must NOT raise."""
    bb = _bb(arch_plan=[{"id": "t1", "description": "d"}])
    leaf = WorkAgentLeaf(task_id="t1")
    assert leaf.tick(bb) is Status.RUNNING
    assert bb.pending_dispatch.required_capability is None
    assert bb.pending_dispatch.agent_file is None


def test_work_agent_leaf_resume_writes_work_results():
    bb = _bb(arch_plan=[
        {"id": "a1", "description": "d", "required_capability": "programmer"},
    ])
    leaf = WorkAgentLeaf(task_id="a1")
    leaf.tick(bb)
    leaf.on_resume(bb, "Implemented in src/x.py")
    assert bb.work_results["a1"]["status"] == "ok"
    assert "Implemented" in bb.work_results["a1"]["output"]


def test_work_agent_leaf_skips_when_result_present():
    bb = _bb(arch_plan=[{"id": "a1", "description": "d"}])
    bb.work_results = {"a1": {"status": "ok", "output": "done"}}
    leaf = WorkAgentLeaf(task_id="a1")
    assert leaf.tick(bb) is Status.SUCCESS
    assert bb.pending_dispatch is None


def test_dispatch_work_completes_when_all_results_present():
    bb = _bb(arch_plan=[
        {"id": "a1", "description": "d", "required_capability": "programmer"},
        {"id": "a2", "description": "d", "required_capability": "programmer"},
    ])
    bb.work_results = {
        "a1": {"status": "ok", "output": "done"},
        "a2": {"status": "ok", "output": "done"},
    }
    assert DispatchWork().tick(bb) is Status.SUCCESS


def test_dispatch_work_yields_first_pending_leaf():
    bb = _bb(arch_plan=[
        {"id": "a1", "description": "d", "required_capability": "programmer"},
        {"id": "a2", "description": "d", "required_capability": "programmer"},
    ])
    dw = DispatchWork()
    assert dw.tick(bb) is Status.RUNNING
    assert bb.pending_dispatch.subtask_id == "a1"


def test_dispatch_work_empty_plan_is_success():
    bb = _bb()
    assert DispatchWork().tick(bb) is Status.SUCCESS


# ---------------------------------------------------------------------------
# Respond
# ---------------------------------------------------------------------------

def test_respond_concatenates_work_results_in_plan_order():
    bb = _bb(arch_plan=[
        {"id": "a1"}, {"id": "a2"},
    ])
    bb.work_results = {
        "a2": {"status": "ok", "output": "second"},
        "a1": {"status": "ok", "output": "first"},
    }
    assert Respond().tick(bb) is Status.SUCCESS
    assert bb.final_response == "first\n\n---\n\nsecond"


def test_respond_preserves_existing_final_response():
    bb = _bb(final_response="already set")
    Respond().tick(bb)
    assert bb.final_response == "already set"


def test_respond_interrupt_path_leaves_final_response_empty():
    bb = _bb(interrupt_reason="agent_gap: x")
    Respond().tick(bb)
    assert bb.final_response is None


# ---------------------------------------------------------------------------
# SwitchBranch — decision trace events
# ---------------------------------------------------------------------------

def _switch_events(bb) -> list[dict]:
    return [e for e in bb.trace if e.get("event") == "switch_decision"]


def _selector_events(bb) -> list[dict]:
    return [e for e in bb.trace if e.get("event") == "selector_decision"]


def test_switch_branch_hits_case_emits_decision():
    a = _StubNode("A", Status.SUCCESS)
    b = _StubNode("B", Status.SUCCESS)
    sw = SwitchBranch(
        key_fn=lambda bb: bb.mode,
        cases={"alpha": a, "beta": b},
        name="SW",
    )
    bb = _bb()
    bb.mode = "alpha"
    assert sw.tick(bb) is Status.SUCCESS
    assert (a.ticks, b.ticks) == (1, 0)
    events = _switch_events(bb)
    assert len(events) == 1
    ev = events[0]
    assert ev["node"] == "SW"
    assert ev["key"] == "alpha"
    assert ev["matched_case"] == "alpha"
    assert ev["chosen_child"] == "A"
    assert "error" not in ev


def test_switch_branch_falls_back_to_default_emits_decision():
    a = _StubNode("A", Status.SUCCESS)
    d = _StubNode("D", Status.SUCCESS)
    sw = SwitchBranch(
        key_fn=lambda bb: bb.mode,
        cases={"alpha": a},
        default=d,
        name="SW",
    )
    bb = _bb()
    bb.mode = "unknown"
    assert sw.tick(bb) is Status.SUCCESS
    assert (a.ticks, d.ticks) == (0, 1)
    events = _switch_events(bb)
    assert len(events) == 1
    ev = events[0]
    assert ev["key"] == "unknown"
    assert ev["matched_case"] == "__default__"
    assert ev["chosen_child"] == "D"


def test_switch_branch_no_match_no_default_returns_failure_and_emits_decision():
    a = _StubNode("A", Status.SUCCESS)
    sw = SwitchBranch(
        key_fn=lambda bb: bb.mode,
        cases={"alpha": a},
        name="SW",
    )
    bb = _bb()
    bb.mode = "unknown"
    assert sw.tick(bb) is Status.FAILURE
    assert a.ticks == 0
    events = _switch_events(bb)
    assert len(events) == 1
    ev = events[0]
    assert ev["key"] == "unknown"
    assert ev["matched_case"] == "__no_match__"
    assert ev["chosen_child"] is None


def test_switch_branch_key_fn_raises_returns_failure_and_emits_error_event():
    a = _StubNode("A", Status.SUCCESS)
    d = _StubNode("D", Status.SUCCESS)

    def _boom(_bb):
        raise RuntimeError("kaboom")

    sw = SwitchBranch(
        key_fn=_boom,
        cases={"alpha": a},
        default=d,
        name="SW",
    )
    bb = _bb()
    # Even with a default, key_fn errors short-circuit to FAILURE (no
    # fallback execution — the bb predicate itself is broken).
    assert sw.tick(bb) is Status.FAILURE
    assert (a.ticks, d.ticks) == (0, 0)
    events = _switch_events(bb)
    assert len(events) == 1
    ev = events[0]
    assert ev["matched_case"] == "__error__"
    assert ev["chosen_child"] is None
    assert ev["key"] is None
    assert ev["error"].startswith("RuntimeError: kaboom")


# ---------------------------------------------------------------------------
# Selector — decision trace events
# ---------------------------------------------------------------------------

def test_selector_first_child_success_emits_decision_with_single_result():
    a = _StubNode("A", Status.SUCCESS)
    b = _StubNode("B", Status.SUCCESS)
    sel = Selector([a, b], name="Sel")
    bb = _bb()
    assert sel.tick(bb) is Status.SUCCESS
    events = _selector_events(bb)
    assert len(events) == 1
    ev = events[0]
    assert ev["node"] == "Sel"
    assert ev["chosen_child"] == "A"
    assert ev["outcome"] == "success"
    assert ev["child_results"] == [{"name": "A", "status": "success"}]


def test_selector_second_child_success_after_failure_records_both_results():
    a = _StubNode("A", Status.FAILURE)
    b = _StubNode("B", Status.SUCCESS)
    c = _StubNode("C", Status.SUCCESS)
    sel = Selector([a, b, c], name="Sel")
    bb = _bb()
    assert sel.tick(bb) is Status.SUCCESS
    assert c.ticks == 0
    events = _selector_events(bb)
    assert len(events) == 1
    ev = events[0]
    assert ev["chosen_child"] == "B"
    assert ev["outcome"] == "success"
    assert ev["child_results"] == [
        {"name": "A", "status": "failure"},
        {"name": "B", "status": "success"},
    ]


def test_selector_middle_running_emits_running_decision():
    a = _StubNode("A", Status.FAILURE)
    b = _StubNode("B", Status.RUNNING)
    c = _StubNode("C", Status.SUCCESS)
    sel = Selector([a, b, c], name="Sel")
    bb = _bb()
    assert sel.tick(bb) is Status.RUNNING
    assert c.ticks == 0
    events = _selector_events(bb)
    assert len(events) == 1
    ev = events[0]
    assert ev["chosen_child"] == "B"
    assert ev["outcome"] == "running"
    assert ev["child_results"] == [
        {"name": "A", "status": "failure"},
        {"name": "B", "status": "running"},
    ]


def test_selector_all_failure_emits_decision_with_no_chosen_child():
    a = _StubNode("A", Status.FAILURE)
    b = _StubNode("B", Status.FAILURE)
    sel = Selector([a, b], name="Sel")
    bb = _bb()
    assert sel.tick(bb) is Status.FAILURE
    events = _selector_events(bb)
    assert len(events) == 1
    ev = events[0]
    assert ev["chosen_child"] is None
    assert ev["outcome"] == "all_failure"
    assert ev["child_results"] == [
        {"name": "A", "status": "failure"},
        {"name": "B", "status": "failure"},
    ]
