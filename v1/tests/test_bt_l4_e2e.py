"""L4 — end-to-end dry-runs through the global ROOT (v3).

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
# Conversation path
# ---------------------------------------------------------------------------

def test_e2e_conversation_short_circuits_to_done(isolated_scheduler_root):
    r = api.bt_tick("什么是 CBIM？")
    assert r.kind == "done"
    assert r.user_message
    # No dispatches at all — conversation mode bypasses ExecutionSeq.


def test_e2e_empty_request_lands_in_conversation_mode(isolated_scheduler_root):
    r = api.bt_tick("")
    assert r.kind == "done"
    assert "请描述你的需求" in (r.user_message or "")


def test_e2e_english_question_is_conversation(isolated_scheduler_root):
    r = api.bt_tick("what is the difference between L1 and L2 tests?")
    assert r.kind == "done"
    assert r.user_message


# ---------------------------------------------------------------------------
# Execution path
# ---------------------------------------------------------------------------

_ARCH_REPLY = (
    '{"arch_plan":[{"id":"a1","description":"build login handler",'
    '"required_capability":"programmer","arch_context":"ctx-pack-1"}]}'
)

_HR_REPLY_A1 = (
    "task_id=a1 agent_file=.claude/agents/programmer/programmer.md capability=py"
)


def test_e2e_execution_three_step_dispatch(isolated_scheduler_root):
    r, log = _drive(
        "实现 login API 模块",
        _ARCH_REPLY,
        _HR_REPLY_A1,
        "Implemented in src/login.py",
    )
    assert r.kind == "done"
    assert "Implemented in src/login.py" in r.user_message
    assert log[0][0] == "architect"
    assert log[1][0] == "hr"
    assert log[2][0] == "work"
    assert log[2][1] == "a1"


def test_e2e_execution_multi_task_plan(isolated_scheduler_root):
    arch = (
        '{"arch_plan":['
        '{"id":"a1","description":"build handler","required_capability":"py"},'
        '{"id":"a2","description":"write tests","required_capability":"py"}'
        ']}'
    )
    hr = (
        "task_id=a1 agent_file=.claude/agents/programmer/programmer.md capability=py\n"
        "task_id=a2 agent_file=.claude/agents/programmer/programmer.md capability=py"
    )
    r, log = _drive(
        "实现 login API 与测试",
        arch, hr,
        "handler done",
        "tests done",
    )
    assert r.kind == "done"
    assert "handler done" in r.user_message
    assert "tests done" in r.user_message
    agent_types = [a for a, _ in log]
    assert agent_types == ["architect", "hr", "work", "work"]
    # task ids on the two work yields
    work_ids = [sid for atype, sid in log if atype == "work"]
    assert work_ids == ["a1", "a2"]


def test_e2e_architect_plain_text_reply_is_single_task(isolated_scheduler_root):
    r, log = _drive(
        "实现 login API",
        "Just go put the handler in src/login.py and call it a day.",
        "task_id=t1 agent_file=.claude/agents/programmer/programmer.md capability=py",
        "Done.",
    )
    assert r.kind == "done"
    assert "Done." in r.user_message
    assert [a for a, _ in log] == ["architect", "hr", "work"]


def test_e2e_hr_agent_gap_interrupts(isolated_scheduler_root):
    r, log = _drive(
        "实现 login API",
        _ARCH_REPLY,
        "agent_gap: no programmer agent available",
    )
    assert r.kind == "error"
    # Retry will resend once → second HR yield with same agent_gap response →
    # so we may see two HR yields before failure surfaces.
    assert "agent_gap" in (r.interrupt_reason or "") or "agent_gap" in (r.error_message or "")


def test_e2e_architect_error_interrupts(isolated_scheduler_root):
    r, log = _drive(
        "实现 login API",
        "arch_error: blueprint missing",
    )
    assert r.kind == "error"
    assert "arch_error" in (r.interrupt_reason or "") or "arch_error" in (r.error_message or "")
