"""PR-C — ConvergeJudge unit tests.

Covers spec §10.2 cases 1-10. Pure aggregation; depends only on
bb.work_results shape (PR-A landed).
"""
from __future__ import annotations

from types import SimpleNamespace

from engine.core.node import Status
from engine.execution.actions.converge_judge import (
    DEFAULT_MAX_ITERS,
    ConvergeJudge,
)


def _bb(work_results=None, *, iter_no=1, arch_plan=None) -> SimpleNamespace:
    bb = SimpleNamespace()
    bb.work_results = dict(work_results or {})
    bb.work_loop_iter = iter_no
    bb.arch_plan = list(arch_plan or [])
    bb.trace = []
    bb.convergence = None
    bb.arch_redo_context = None
    bb.interrupt_reason = None
    bb.final_response = None
    return bb


def _result(status: str, **fields) -> dict:
    base = {"status": status, "agent": "programmer", "summary": "s", "output": "o"}
    base.update(fields)
    return base


def _trace_events(bb, event_name: str) -> list[dict]:
    return [e for e in bb.trace if e.get("event") == event_name]


# ---------------------------------------------------------------------------
# Case 1: all ok → done
# ---------------------------------------------------------------------------

def test_all_ok_yields_done():
    bb = _bb({"t1": _result("ok"), "t2": _result("ok")})
    assert ConvergeJudge().tick(bb) is Status.SUCCESS
    assert bb.convergence == "done"
    assert bb.arch_redo_context is None


# ---------------------------------------------------------------------------
# Case 2: mix of ok + failed → done (failure surfaces in Respond)
# ---------------------------------------------------------------------------

def test_mix_ok_and_failed_yields_done():
    bb = _bb({"t1": _result("ok"), "t2": _result("failed", failure_kind="test_failed")})
    assert ConvergeJudge().tick(bb) is Status.SUCCESS
    assert bb.convergence == "done"


# ---------------------------------------------------------------------------
# Case 3: one needs_arch_decision, iter 1, max 3 → arch_redo FAILURE
# ---------------------------------------------------------------------------

def test_needs_arch_decision_at_iter_1_returns_failure_for_redo():
    bb = _bb(
        {"t1": _result("ok"),
         "t2": _result("needs_arch_decision", question="what now?",
                       blocking_module="v1/x")},
        iter_no=1,
    )
    assert ConvergeJudge(max_iters=3).tick(bb) is Status.FAILURE
    assert bb.convergence == "arch_redo"
    ctx = bb.arch_redo_context
    assert ctx is not None
    assert ctx["iter"] == 1
    assert len(ctx["unresolved"]) == 1
    assert ctx["unresolved"][0]["task_id"] == "t2"


# ---------------------------------------------------------------------------
# Case 4: one needs_arch_decision, iter 3, max 3 → exhausted SUCCESS
# ---------------------------------------------------------------------------

def test_needs_arch_decision_at_final_iter_yields_exhausted():
    bb = _bb(
        {"t1": _result("needs_arch_decision", question="q", blocking_module="m")},
        iter_no=3,
    )
    assert ConvergeJudge(max_iters=3).tick(bb) is Status.SUCCESS
    assert bb.convergence == "exhausted"
    # arch_redo_context still populated so Respond#exhausted can quote it.
    assert bb.arch_redo_context is not None
    assert bb.arch_redo_context["iter"] == 3


# ---------------------------------------------------------------------------
# Case 5: needs_user_input wins over needs_arch_decision; no redo context
# ---------------------------------------------------------------------------

def test_needs_user_wins_over_needs_arch():
    bb = _bb({
        "t1": _result("needs_user_input", question="what should I do?"),
        "t2": _result("needs_arch_decision", question="arch q"),
    }, iter_no=1)
    assert ConvergeJudge().tick(bb) is Status.SUCCESS
    assert bb.convergence == "user_input"
    # No arch_redo_context written on the user_input path.
    assert bb.arch_redo_context is None


# ---------------------------------------------------------------------------
# Case 6: empty work_results → done
# ---------------------------------------------------------------------------

def test_empty_work_results_yields_done():
    bb = _bb({})
    assert ConvergeJudge().tick(bb) is Status.SUCCESS
    assert bb.convergence == "done"


# ---------------------------------------------------------------------------
# Case 7: arch_redo path purges only the needs_arch_decision entries
# ---------------------------------------------------------------------------

def test_arch_redo_purges_only_needs_arch_decision_entries():
    bb = _bb({
        "t1": _result("ok", output="kept ok"),
        "t2": _result("needs_arch_decision", question="q"),
        "t3": _result("failed", failure_kind="x"),
    }, iter_no=1)
    ConvergeJudge(max_iters=3).tick(bb)
    assert bb.convergence == "arch_redo"
    remaining = set(bb.work_results.keys())
    assert "t1" in remaining
    assert "t3" in remaining
    assert "t2" not in remaining
    # Surviving entries unchanged.
    assert bb.work_results["t1"]["output"] == "kept ok"
    assert bb.work_results["t3"]["failure_kind"] == "x"


# ---------------------------------------------------------------------------
# Case 8: arch_redo_context fields carry through verbatim
# ---------------------------------------------------------------------------

def test_arch_redo_context_carries_task_fields():
    bb = _bb({
        "t9": _result(
            "needs_arch_decision",
            question="What schema for field Z?",
            blocking_module="v1/kernel/engine/exec",
            agent="programmer",
            summary="cannot proceed without schema",
        ),
    }, iter_no=2, arch_plan=[{"id": "t9", "description": "d"}])
    ConvergeJudge(max_iters=3).tick(bb)
    entry = bb.arch_redo_context["unresolved"][0]
    assert entry == {
        "task_id": "t9",
        "blocking_module": "v1/kernel/engine/exec",
        "question": "What schema for field Z?",
        "agent": "programmer",
        "summary": "cannot proceed without schema",
    }
    assert bb.arch_redo_context["previous_plan"] == [{"id": "t9", "description": "d"}]
    assert bb.arch_redo_context["iter"] == 2


# ---------------------------------------------------------------------------
# Case 9: trace entries arch_redo_stashed + work_results_purged appear
# ---------------------------------------------------------------------------

def test_arch_redo_emits_trace_events():
    bb = _bb({
        "t1": _result("needs_arch_decision", question="q1"),
        "t2": _result("ok"),
    }, iter_no=1)
    ConvergeJudge(max_iters=3).tick(bb)
    stashed = _trace_events(bb, "arch_redo_stashed")
    purged = _trace_events(bb, "work_results_purged")
    assert len(stashed) == 1
    assert stashed[0]["iter"] == 1
    assert stashed[0]["unresolved_count"] == 1
    assert len(purged) == 1
    assert purged[0]["task_ids"] == ["t1"]


# ---------------------------------------------------------------------------
# Case 10: malformed entry without status field treated as failed (no loop)
# ---------------------------------------------------------------------------

def test_malformed_entry_without_status_treated_as_failed():
    bb = _bb({"t1": {"agent": "programmer"}}, iter_no=1)  # no status key
    assert ConvergeJudge().tick(bb) is Status.SUCCESS
    assert bb.convergence == "done"  # aggregated as failed → terminal done
    assert bb.arch_redo_context is None


# ---------------------------------------------------------------------------
# Extra: default max_iters matches the module constant
# ---------------------------------------------------------------------------

def test_default_max_iters_constant():
    assert DEFAULT_MAX_ITERS == 3
    judge = ConvergeJudge()
    # Iter at the default boundary → exhausted.
    bb = _bb({"t1": _result("needs_arch_decision", question="q")},
             iter_no=DEFAULT_MAX_ITERS)
    assert judge.tick(bb) is Status.SUCCESS
    assert bb.convergence == "exhausted"


# ---------------------------------------------------------------------------
# Extra: ConvergeJudge swallows internal errors and forces "done"
# ---------------------------------------------------------------------------

def test_internal_error_is_swallowed_and_traces():
    class _Boom:
        # values() raises, simulating a hostile work_results object.
        def values(self):
            raise RuntimeError("kaboom")

        def __bool__(self):
            return True

    bb = SimpleNamespace()
    bb.work_results = _Boom()
    bb.work_loop_iter = 1
    bb.arch_plan = []
    bb.trace = []
    bb.convergence = None
    bb.arch_redo_context = None
    assert ConvergeJudge().tick(bb) is Status.SUCCESS
    assert bb.convergence == "done"
    errs = _trace_events(bb, "converge_internal_error")
    assert len(errs) == 1
    assert "RuntimeError" in errs[0]["error"]
