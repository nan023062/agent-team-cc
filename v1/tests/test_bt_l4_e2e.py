"""L4 — end-to-end dry-runs through the global ROOT.

FakeDispatcher: pretends to be the main agent. Each scenario drives
bt_tick → loop { yield → fake task result → bt_tick_resume } until done.
"""
from __future__ import annotations

import pytest

from engine.bt.api import bt_tick as api


@pytest.fixture
def isolated_scheduler_root(tmp_path, monkeypatch):
    sched = tmp_path / ".cbim" / "scheduler"
    sched.mkdir(parents=True)
    monkeypatch.setattr(api, "_scheduler_root", lambda: sched)
    return sched


def _drive(user_request: str, *replies: str, max_steps: int = 20):
    """Run a tick, feeding the provided replies in order on each yield.

    Returns (final_result, dispatch_log) where dispatch_log is a list of
    (agent_type, subtask_id) per yield seen.
    """
    r = api.bt_tick(user_request)
    log: list[tuple[str, str | None]] = []
    reply_iter = iter(replies)
    steps = 0
    while r.kind == "yield" and steps < max_steps:
        log.append((r.dispatch_request.agent_type, r.dispatch_request.subtask_id))
        try:
            payload = next(reply_iter)
        except StopIteration:
            payload = "default-reply"
        r = api.bt_tick_resume(r.tick_id, payload)
        steps += 1
    return r, log


# ---------------------------------------------------------------------------

def test_e2e_simple_execution_yields_arch_then_work_then_done(isolated_scheduler_root):
    r, log = _drive(
        "实现 login API 模块",
        "ContextPack: modules=[login]",
        "Implemented in src/login.py",
    )
    assert r.kind == "done"
    assert "Implemented in src/login.py" in r.user_message
    assert log[0][0] == "architect"
    assert log[1][0] == "work"


def test_e2e_pure_query_skips_arch_gate(isolated_scheduler_root):
    r, log = _drive(
        "查询模块 X 的历史决策",
        "Module X owned by alice since 2026-04-01.",
    )
    assert r.kind == "done"
    assert log[0][0] == "work"  # straight to work agent (architect role)
    assert all(entry[0] != "architect" for entry in log)


def test_e2e_escalation_loops_back_to_arch(isolated_scheduler_root):
    r, log = _drive(
        "实现 login API 模块",
        "CTX-PACK-v1",
        "NEEDS_ARCH_DECISION: dep conflict\n- context: blocked",
        "CTX-PACK-v2-updated",
        "Implemented after rework.",
    )
    assert r.kind == "done"
    # arch -> work -> arch -> work
    agent_types = [a for a, _ in log]
    assert agent_types == ["architect", "work", "architect", "work"]


def test_e2e_iteration_cap_interrupts(isolated_scheduler_root):
    # Keep escalating forever; cap=5 should interrupt.
    r, log = _drive(
        "实现 login API 模块",
        *(["CTX", "NEEDS_ARCH_DECISION: stuck"] * 10),
    )
    assert r.kind == "error"
    assert r.error_code == "interrupt"
    assert "iteration_cap_exceeded" in (r.interrupt_reason or "")


def test_e2e_empty_request_short_circuits_to_clarify(isolated_scheduler_root):
    r = api.bt_tick("")
    # AskClarify writes final_response immediately → done with the question.
    assert r.kind == "done"
    assert r.user_message  # the clarifying question


def test_e2e_unrecognized_request_errors_via_llm_fallback(isolated_scheduler_root):
    # No rule hit + NullLLM raises → IntentAnalyze FAILURE → tick error.
    r = api.bt_tick("zzz qrx blarp 玳瑁")
    assert r.kind == "error"
    assert "llm_fallback_required_but_unavailable" in (r.error_message or "" + (r.interrupt_reason or ""))
