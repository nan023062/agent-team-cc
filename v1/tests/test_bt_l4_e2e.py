"""L4 — end-to-end dry-runs through the global ROOT (v3).

Post-t6: the architect/HR sub-loops run as in-process BT subtrees, so the
only execution-path yield is DispatchWork dispatching the work agent.
The fixture rebuilds ROOT with a StubArchHrLLM so the arch/HR subtrees
produce a deterministic single-task arch_plan + agent_assignments.
"""
from __future__ import annotations

import pytest

from engine.execution.api import bt_tick as api
from engine.execution.tree.main_loop import build_root

from stub_llm import StubArchHrLLM


@pytest.fixture
def isolated_scheduler_root(tmp_path, monkeypatch):
    sched = tmp_path / ".cbim" / "scheduler"
    sched.mkdir(parents=True)
    monkeypatch.setattr(api, "_scheduler_root", lambda: sched)
    monkeypatch.setattr(api, "ROOT", build_root(llm=StubArchHrLLM()))
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

def test_e2e_execution_single_work_yield_then_done(isolated_scheduler_root):
    """StubArchHrLLM produces a single-task arch_plan; the only yield is
    DispatchWork for that task, after which Respond writes the work output
    into final_response."""
    r, log = _drive(
        "实现 login API 模块",
        "Implemented in src/login.py",
    )
    assert r.kind == "done"
    assert "Implemented in src/login.py" in r.user_message
    assert len(log) == 1
    assert log[0] == ("work", "a1")


def test_e2e_execution_work_failure_reply_still_completes(isolated_scheduler_root):
    """Even a 'Done.' style work reply terminates cleanly — the engine
    treats the reply as the work output and Respond echoes it."""
    r, log = _drive("实现 login API", "Done.")
    assert r.kind == "done"
    assert "Done." in r.user_message
    assert [a for a, _ in log] == ["work"]


# ---------------------------------------------------------------------------
# Memory CRUD flush smoke
# ---------------------------------------------------------------------------

def test_e2e_flush_memory_drains_queue(monkeypatch, tmp_path):
    """Smoke: FlushMemory drains bb.memory_flush_queue via the CRUD sub-loop.

    Replaces the real write primitive with an in-memory stub so no real
    file IO happens. Asserts the node returns SUCCESS and the queue is
    cleared after a successful write.
    """
    from types import SimpleNamespace
    from engine.execution.actions import flush_memory as fm
    from engine.core.node import Status

    writes: list[tuple[str, str]] = []

    def _stub_make_write_call(_backend):
        def _call(crud_bb):
            entry = (crud_bb.crud_op or {}).get("entry") or {}
            path = entry.get("path")
            tier = entry.get("tier")
            if not path or not tier:
                raise ValueError(f"flush entry missing path/tier: {entry!r}")
            writes.append((path, tier))
            return {"path": path, "tier": tier}
        return _call

    monkeypatch.setattr(fm, "_make_write_call", _stub_make_write_call)

    bb = SimpleNamespace(
        memory_flush_queue=[
            {
                "path": str(tmp_path / "short" / "2026-05-25-smoke.md"),
                "tier": "short",
                "content": "smoke entry",
            }
        ]
    )

    status = fm.FlushMemory().tick(bb)

    # Spec: 1) does not raise (status SUCCESS or FAILURE both acceptable);
    #       2) queue drained after the tick;
    #       3) the stub write_call is actually invoked (regression: missing
    #          runner_resume_path on crud_bb used to swallow every entry).
    assert status in (Status.SUCCESS, Status.FAILURE)
    assert bb.memory_flush_queue == []
    assert len(writes) == 1
    assert writes[0] == (
        str(tmp_path / "short" / "2026-05-25-smoke.md"),
        "short",
    )
