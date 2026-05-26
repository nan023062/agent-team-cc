"""Unit tests for ArchExecYield (PR-D).

The leaf replaces the in-process nine-leaf arch_exec subtree with a
single yield to the architect agent. Coverage:

  1. First tick: yields a DispatchRequest targeting the architect agent
     with subtask_id="arch:<iter>".
  2. on_resume with a valid receipt trailer carrying arch_plan populates
     bb.arch_plan; the next tick is SUCCESS.
  3. on_resume with malformed JSON / missing fields → bb.arch_plan=[],
     no convergence override, next tick is SUCCESS (empty plan, treated
     by DispatchWork as a no-op).
  4. on_resume with status="needs_user_input" seeds bb.convergence so
     EscalationGate routes to Respond#need_user.
  5. Cap violation (>8 tasks) is a hard fail → bb.arch_plan=[].
"""
from __future__ import annotations

from types import SimpleNamespace

from engine.execution.actions.arch_exec_yield import (
    ARCHITECT_AGENT_FILE,
    ArchExecYield,
)
from engine.core.node import Status


def _bb(**overrides) -> SimpleNamespace:
    bb = SimpleNamespace(
        tick_id="t",
        user_request="implement login",
        mode="execution",
        arch_plan=None,
        work_results={},
        pending_dispatch=None,
        trace=[],
        convergence=None,
        arch_redo_context=None,
        work_loop_iter=None,
        knowledge_snapshot=None,
    )
    for k, v in overrides.items():
        setattr(bb, k, v)
    return bb


def _receipt(arch_plan_json: str, *, status: str = "ok",
             question: str | None = None,
             task_id: str = "arch:1") -> str:
    lines = [
        "<!-- BEGIN CBIM-RECEIPT v1",
        f"status: {status}",
        f"task_id: {task_id}",
        "agent: architect",
        "summary: stub",
    ]
    if question:
        lines.append(f"question: {question}")
    if arch_plan_json is not None:
        lines.append(f"arch_plan: {arch_plan_json}")
    lines.append("END CBIM-RECEIPT -->")
    return "Body prose.\n" + "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Tick — first call yields
# ---------------------------------------------------------------------------

def test_tick_first_call_yields_architect_dispatch():
    bb = _bb()
    leaf = ArchExecYield()
    assert leaf.tick(bb) is Status.RUNNING
    dr = bb.pending_dispatch
    assert dr is not None
    assert dr.agent_type == "architect"
    assert dr.agent_file == ARCHITECT_AGENT_FILE
    assert dr.subtask_id == "arch:1"
    assert dr.prompt.startswith("## 执行模式 · ArchExec")


def test_tick_subtask_id_uses_work_loop_iter():
    bb = _bb(work_loop_iter=2)
    leaf = ArchExecYield()
    leaf.tick(bb)
    assert bb.pending_dispatch.subtask_id == "arch:2"


def test_tick_short_circuits_when_plan_present():
    bb = _bb(arch_plan=[{"id": "a1"}])
    leaf = ArchExecYield()
    assert leaf.tick(bb) is Status.SUCCESS
    assert bb.pending_dispatch is None


def test_tick_failure_when_plan_is_not_a_list():
    bb = _bb(arch_plan="not a list")
    leaf = ArchExecYield()
    assert leaf.tick(bb) is Status.FAILURE


# ---------------------------------------------------------------------------
# on_resume — happy path
# ---------------------------------------------------------------------------

def test_on_resume_with_valid_trailer_populates_arch_plan():
    bb = _bb()
    leaf = ArchExecYield()
    leaf.tick(bb)  # primes pending_dispatch
    plan_json = (
        '[{"id":"t1","description":"do thing",'
        '"required_capability":"programmer","params":{},'
        '"arch_context":"ctx-1"}]'
    )
    leaf.on_resume(bb, _receipt(plan_json))
    assert bb.pending_dispatch is None
    assert isinstance(bb.arch_plan, list)
    assert len(bb.arch_plan) == 1
    task = bb.arch_plan[0]
    assert task["id"] == "t1"
    assert task["required_capability"] == "programmer"
    assert task["arch_context"] == "ctx-1"
    # Second tick → SUCCESS, plan stays.
    assert leaf.tick(bb) is Status.SUCCESS


def test_on_resume_unknown_capability_collapses_to_generalist():
    bb = _bb()
    leaf = ArchExecYield()
    leaf.tick(bb)
    plan_json = (
        '[{"id":"t1","description":"x",'
        '"required_capability":"sorcerer","params":{},'
        '"arch_context":"c"}]'
    )
    leaf.on_resume(bb, _receipt(plan_json))
    assert bb.arch_plan[0]["required_capability"] == "generalist"


def test_on_resume_payload_can_be_dict_with_output_key():
    bb = _bb()
    leaf = ArchExecYield()
    leaf.tick(bb)
    plan_json = (
        '[{"id":"t1","description":"x",'
        '"required_capability":"programmer","params":{},'
        '"arch_context":"c"}]'
    )
    leaf.on_resume(bb, {"output": _receipt(plan_json)})
    assert bb.arch_plan and bb.arch_plan[0]["id"] == "t1"


# ---------------------------------------------------------------------------
# on_resume — failure paths
# ---------------------------------------------------------------------------

def test_on_resume_with_malformed_json_yields_empty_plan():
    bb = _bb()
    leaf = ArchExecYield()
    leaf.tick(bb)
    leaf.on_resume(bb, _receipt("[not valid json"))
    assert bb.arch_plan == []
    # Next tick is SUCCESS — empty plan is a legal terminal state
    # (architect explicitly said no work needed). DispatchWork treats
    # the empty plan as a no-op.
    assert leaf.tick(bb) is Status.SUCCESS


def test_on_resume_with_missing_arch_context_fails_validation():
    bb = _bb()
    leaf = ArchExecYield()
    leaf.tick(bb)
    plan_json = (
        '[{"id":"t1","description":"x",'
        '"required_capability":"programmer","params":{},'
        '"arch_context":""}]'
    )
    leaf.on_resume(bb, _receipt(plan_json))
    assert bb.arch_plan == []


def test_on_resume_with_too_many_tasks_fails_validation():
    bb = _bb()
    leaf = ArchExecYield()
    leaf.tick(bb)
    items = ",".join(
        f'{{"id":"t{i}","description":"x",'
        f'"required_capability":"programmer","params":{{}},'
        f'"arch_context":"c"}}'
        for i in range(9)
    )
    leaf.on_resume(bb, _receipt(f"[{items}]"))
    assert bb.arch_plan == []


def test_on_resume_with_failed_status_yields_empty_plan():
    bb = _bb()
    leaf = ArchExecYield()
    leaf.tick(bb)
    leaf.on_resume(
        bb,
        "<!-- BEGIN CBIM-RECEIPT v1\n"
        "status: failed\n"
        "task_id: arch:1\n"
        "agent: architect\n"
        "summary: gave up\n"
        "failure_kind: other\n"
        "END CBIM-RECEIPT -->\n",
    )
    assert bb.arch_plan == []


# ---------------------------------------------------------------------------
# on_resume — needs_user_input fast-path
# ---------------------------------------------------------------------------

def test_on_resume_with_needs_user_input_sets_convergence():
    bb = _bb()
    leaf = ArchExecYield()
    leaf.tick(bb)
    leaf.on_resume(
        bb,
        _receipt(
            None,
            status="needs_user_input",
            question="which auth provider?",
        ),
    )
    assert bb.arch_plan == []
    assert bb.convergence == "user_input"
    entry = bb.work_results["arch:1"]
    assert entry["status"] == "needs_user_input"
    assert entry["question"] == "which auth provider?"


# ---------------------------------------------------------------------------
# Cross-tick state hygiene
# ---------------------------------------------------------------------------

def test_no_cross_tick_state_on_self():
    leaf = ArchExecYield()
    bb1 = _bb()
    leaf.tick(bb1)
    bb2 = _bb()
    leaf.tick(bb2)
    # Both yields use the fresh bb only; nothing leaks via self.
    assert bb1.pending_dispatch.subtask_id == "arch:1"
    assert bb2.pending_dispatch.subtask_id == "arch:1"
    public_attrs = {
        k for k in vars(leaf).keys()
        if not k.startswith("_") and k != "name"
    }
    assert public_attrs == set()
