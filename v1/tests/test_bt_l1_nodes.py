"""L1 — node-level unit tests for engine.execution (v3).

Covers core composites/decorators + each v3 Action's tick/on_resume contract.
No persistence, no MCP — pure in-memory.
"""
from __future__ import annotations

from engine.execution.actions.direct_reply import DirectReply
from engine.execution.actions.dispatch_architect import DispatchArchitect
from engine.execution.actions.dispatch_hr import DispatchHR
from engine.execution.actions.dispatch_work import DispatchWork, WorkAgentLeaf
from engine.execution.actions.init_tick import InitTick
from engine.execution.actions.llm_hook import NullLLM
from engine.execution.actions.mode_classify import ModeClassify
from engine.execution.actions.respond import Respond
from engine.execution.core.blackboard import Blackboard
from engine.execution.core.composite import ModeBranch, Parallel, Selector, Sequence
from engine.execution.core.node import Node, Status


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
    assert ModeClassify(llm=NullLLM()).tick(bb) is Status.SUCCESS
    assert bb.mode == "conversation"


def test_mode_classify_question_is_conversation():
    bb = _bb(user_request="What is CBIM?")
    assert ModeClassify(llm=NullLLM()).tick(bb) is Status.SUCCESS
    assert bb.mode == "conversation"


def test_mode_classify_chinese_question_is_conversation():
    bb = _bb(user_request="什么是 CBIM？")
    assert ModeClassify(llm=NullLLM()).tick(bb) is Status.SUCCESS
    assert bb.mode == "conversation"


def test_mode_classify_implement_verb_is_execution():
    bb = _bb(user_request="实现 login API 模块")
    assert ModeClassify(llm=NullLLM()).tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


def test_mode_classify_english_implement_is_execution():
    bb = _bb(user_request="implement the login API module")
    assert ModeClassify(llm=NullLLM()).tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


def test_mode_classify_rule_miss_defaults_to_execution_under_null_llm():
    bb = _bb(user_request="zzz qrx blarp 玳瑁")
    assert ModeClassify(llm=NullLLM()).tick(bb) is Status.SUCCESS
    assert bb.mode == "execution"


class _StubModeLLM(NullLLM):
    def __init__(self, verdict: str) -> None:
        self._verdict = verdict

    def classify_mode(self, user_request: str) -> str:
        return self._verdict


def test_mode_classify_llm_path_on_rule_miss():
    bb = _bb(user_request="zzz blarp qux")
    node = ModeClassify(llm=_StubModeLLM("conversation"))
    assert node.tick(bb) is Status.SUCCESS
    assert bb.mode == "conversation"


# ---------------------------------------------------------------------------
# DirectReply
# ---------------------------------------------------------------------------

def test_direct_reply_writes_final_response_with_null_llm():
    bb = _bb(user_request="什么是 CBIM？")
    assert DirectReply(llm=NullLLM()).tick(bb) is Status.SUCCESS
    assert bb.final_response and "什么是 CBIM？" in bb.final_response


def test_direct_reply_empty_request_writes_prompt_hint():
    bb = _bb(user_request="")
    assert DirectReply(llm=NullLLM()).tick(bb) is Status.SUCCESS
    assert bb.final_response == "请描述你的需求。"


class _StubReplyLLM(NullLLM):
    def reply_conversation(self, user_request: str) -> str:
        return "stub-reply: " + user_request


def test_direct_reply_uses_llm_when_available():
    bb = _bb(user_request="hi")
    DirectReply(llm=_StubReplyLLM()).tick(bb)
    assert bb.final_response == "stub-reply: hi"


# ---------------------------------------------------------------------------
# DispatchArchitect
# ---------------------------------------------------------------------------

def test_dispatch_architect_yields_then_resumes_with_structured_plan():
    bb = _bb(user_request="实现 login API")
    node = DispatchArchitect()
    assert node.tick(bb) is Status.RUNNING
    assert bb.pending_dispatch is not None
    assert bb.pending_dispatch.agent_type == "architect"

    reply = (
        '{"arch_plan": [{"id": "a1", "description": "build handler", '
        '"required_capability": "programmer", "arch_context": "ctx-1"}]}'
    )
    node.on_resume(bb, reply)
    assert bb.arch_plan is not None
    assert len(bb.arch_plan) == 1
    assert bb.arch_plan[0]["id"] == "a1"
    assert bb.arch_plan[0]["required_capability"] == "programmer"
    assert bb.arch_plan[0]["arch_context"] == "ctx-1"
    assert bb.pending_dispatch is None

    # Second tick should short-circuit (idempotent).
    assert node.tick(bb) is Status.SUCCESS


def test_dispatch_architect_plain_text_reply_wraps_single_task():
    bb = _bb(user_request="do the thing")
    node = DispatchArchitect()
    node.tick(bb)
    node.on_resume(bb, "Just go implement it in src/login.py.")
    assert len(bb.arch_plan) == 1
    assert bb.arch_plan[0]["required_capability"] == "generalist"
    assert "implement it" in bb.arch_plan[0]["arch_context"]


def test_dispatch_architect_json_array_reply():
    bb = _bb(user_request="x")
    node = DispatchArchitect()
    node.tick(bb)
    node.on_resume(bb, '[{"id":"a1","description":"d1"}]')
    assert len(bb.arch_plan) == 1
    assert bb.arch_plan[0]["id"] == "a1"


def test_dispatch_architect_error_sets_interrupt():
    bb = _bb(user_request="x")
    node = DispatchArchitect()
    node.tick(bb)
    node.on_resume(bb, "arch_error: ContextPack generation failed")
    assert bb.interrupt_reason and "arch_error" in bb.interrupt_reason
    # Next tick → FAILURE
    assert node.tick(bb) is Status.FAILURE


# ---------------------------------------------------------------------------
# DispatchHR
# ---------------------------------------------------------------------------

def test_dispatch_hr_yields_then_resumes():
    bb = _bb(user_request="x", arch_plan=[
        {"id": "a1", "description": "d1", "required_capability": "py"},
    ])
    node = DispatchHR()
    assert node.tick(bb) is Status.RUNNING
    assert bb.pending_dispatch.agent_type == "hr"
    assert bb.pending_dispatch.agent_file == ".claude/agents/hr/hr.md"

    reply = "task_id=a1 agent_file=.claude/agents/programmer/programmer.md capability=py"
    node.on_resume(bb, reply)
    assert bb.agent_assignments == [{
        "task_id": "a1",
        "agent_file": ".claude/agents/programmer/programmer.md",
        "capability": "py",
    }]
    # arch_plan also got the agent_file merged in.
    assert bb.arch_plan[0]["agent_file"] == ".claude/agents/programmer/programmer.md"
    assert bb.pending_dispatch is None
    # Second tick — idempotent SUCCESS.
    assert node.tick(bb) is Status.SUCCESS


def test_dispatch_hr_skips_when_all_assigned():
    bb = _bb(arch_plan=[
        {"id": "a1", "agent_file": ".claude/agents/x/x.md"},
    ])
    node = DispatchHR()
    assert node.tick(bb) is Status.SUCCESS
    assert bb.pending_dispatch is None


def test_dispatch_hr_skips_when_no_plan():
    bb = _bb()
    assert DispatchHR().tick(bb) is Status.SUCCESS


def test_dispatch_hr_gap_sets_interrupt():
    bb = _bb(arch_plan=[{"id": "a1", "description": "x"}])
    node = DispatchHR()
    node.tick(bb)
    node.on_resume(bb, "agent_gap: no agent for python\nplease recruit")
    assert bb.interrupt_reason and "agent_gap" in bb.interrupt_reason
    # Next tick — FAILURE
    assert node.tick(bb) is Status.FAILURE


def test_dispatch_hr_accepts_legacy_subtask_id_lines():
    bb = _bb(arch_plan=[{"id": "a1", "description": "x"}])
    node = DispatchHR()
    node.tick(bb)
    node.on_resume(bb, "subtask_id=a1 agent_file=.claude/agents/p/p.md capability=py")
    assert bb.arch_plan[0]["agent_file"] == ".claude/agents/p/p.md"


# ---------------------------------------------------------------------------
# WorkAgentLeaf + DispatchWork
# ---------------------------------------------------------------------------

def test_work_agent_leaf_yields_with_task_id():
    bb = _bb(arch_plan=[
        {"id": "a1", "description": "do stuff",
         "agent_file": ".claude/agents/programmer/programmer.md"},
    ])
    leaf = WorkAgentLeaf(task_id="a1")
    assert leaf.tick(bb) is Status.RUNNING
    assert bb.pending_dispatch.subtask_id == "a1"
    assert bb.pending_dispatch.agent_type == "work"
    assert bb.pending_dispatch.agent_file == ".claude/agents/programmer/programmer.md"


def test_work_agent_leaf_resume_writes_work_results():
    bb = _bb(arch_plan=[
        {"id": "a1", "description": "d", "agent_file": "x"},
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
        {"id": "a1", "description": "d", "agent_file": "x"},
        {"id": "a2", "description": "d", "agent_file": "x"},
    ])
    bb.work_results = {
        "a1": {"status": "ok", "output": "done"},
        "a2": {"status": "ok", "output": "done"},
    }
    assert DispatchWork().tick(bb) is Status.SUCCESS


def test_dispatch_work_yields_first_pending_leaf():
    bb = _bb(arch_plan=[
        {"id": "a1", "description": "d", "agent_file": "x"},
        {"id": "a2", "description": "d", "agent_file": "x"},
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
