"""L3 — persistence: bb.json + resume.json + trace.jsonl round-trips (v3.6).

Uses pytest tmp_path fixture for the scheduler root; never touches the
real .cbim/ directory.

PR-D: the architect sub-loop was replaced by ArchExecYield — a single
yield to the architect agent. Execution-path ticks now yield TWICE per
tick: first the architect dispatch, then DispatchWork. Tests that drive
the full pipeline feed both yields in order.
"""
from __future__ import annotations

import json

import pytest

from engine.execution.api import bt_tick as api
from engine.core.blackboard import Blackboard, SCHEMA_VERSION
from engine.persistence import snapshot


# Canonical fake-architect receipt the tests feed back when ArchExecYield
# yields. Trailer carries one task so DispatchWork yields exactly one
# work-agent dispatch on the next step.
_ARCH_PLAN_JSON = (
    '[{"id":"a1","description":"stub task",'
    '"required_capability":"programmer","params":{},'
    '"arch_context":"stub-ctx"}]'
)
FAKE_ARCH_RECEIPT = (
    "Plan ready.\n"
    "<!-- BEGIN CBIM-RECEIPT v1\n"
    "status: ok\n"
    "task_id: arch:1\n"
    "agent: architect\n"
    "summary: stub plan\n"
    f"arch_plan: {_ARCH_PLAN_JSON}\n"
    "END CBIM-RECEIPT -->\n"
)


@pytest.fixture
def isolated_scheduler_root(tmp_path, monkeypatch):
    """Redirect the API's scheduler-root resolver to a tmp dir."""
    sched = tmp_path / ".cbim" / "scheduler"
    sched.mkdir(parents=True)
    monkeypatch.setattr(api, "_scheduler_root", lambda: sched)
    return sched


# ---------------------------------------------------------------------------
# bb.json round-trip
# ---------------------------------------------------------------------------

def test_bb_snapshot_roundtrip(tmp_path):
    bb = Blackboard()
    bb.tick_id = "abc123"
    bb.user_request = "hello"
    bb.mode = "execution"
    bb.arch_plan = [{"id": "a1", "description": "do thing"}]
    bb.work_results = {"a1": {"status": "ok", "output": "x"}}
    bb.bb_status = "running"

    tick_dir = tmp_path / "abc123"
    snapshot.write_bb(tick_dir, bb)
    assert (tick_dir / "bb.json").exists()

    bb2 = snapshot.read_bb(tick_dir)
    assert bb2.tick_id == "abc123"
    assert bb2.user_request == "hello"
    assert bb2.mode == "execution"
    assert bb2.arch_plan == [{"id": "a1", "description": "do thing"}]
    assert bb2.work_results == {"a1": {"status": "ok", "output": "x"}}
    assert bb2.bb_status == "running"


def test_bb_snapshot_schema_version_is_3():
    bb = Blackboard()
    bb.tick_id = "x"
    raw = bb.to_dict()
    assert raw["schema_version"] == SCHEMA_VERSION == 3


def test_bb_snapshot_has_no_agent_assignments_field():
    """v3.6 removed agent_assignments — must not appear in bb.json fields."""
    bb = Blackboard()
    bb.tick_id = "x"
    bb.arch_plan = [{"id": "a1"}]
    raw = bb.to_dict()
    assert "agent_assignments" not in raw["fields"], \
        f"agent_assignments leaked into bb.json fields: {raw['fields']}"


def test_read_bb_drops_old_schema_version(tmp_path):
    # Hand-write a v1 snapshot — read_bb should warn and return None.
    tick_dir = tmp_path / "old"
    tick_dir.mkdir()
    (tick_dir / "bb.json").write_text(json.dumps({
        "schema_version": 1,
        "tick_id": "old",
        "bb_status": "running",
        "fields": {"tick_id": "old", "user_request": "x"},
    }), encoding="utf-8")
    assert snapshot.read_bb(tick_dir) is None


# ---------------------------------------------------------------------------
# Yield-path persists resume artifacts
# ---------------------------------------------------------------------------

def test_yield_writes_bb_resume_and_trace(isolated_scheduler_root):
    sched = isolated_scheduler_root
    r = api.bt_tick("实现 login API 模块")
    assert r.kind == "yield"
    tick_dir = sched / "bt" / r.tick_id
    assert (tick_dir / "bb.json").exists()
    assert (tick_dir / "resume.json").exists()
    assert (tick_dir / "trace.jsonl").exists()


def test_first_yield_targets_architect(isolated_scheduler_root):
    """PR-D: the first execution-path yield is ArchExecYield dispatching
    the architect agent. The work-agent yield comes second, after the
    architect's receipt has populated bb.arch_plan."""
    sched = isolated_scheduler_root
    r = api.bt_tick("实现 login API 模块")
    assert r.kind == "yield"
    dr = r.dispatch_request
    assert dr.agent_type == "architect"
    assert dr.agent_file == ".claude/agents/architect/architect.md"
    assert dr.subtask_id == "arch:1"
    rj = json.loads((sched / "bt" / r.tick_id / "resume.json").read_text(encoding="utf-8"))
    assert "ArchExecYield" in rj["runner_resume_path"], \
        f"resume path missing ArchExecYield: {rj['runner_resume_path']}"


def test_second_yield_targets_work_agent(isolated_scheduler_root):
    """After feeding the architect receipt, the next yield is DispatchWork
    fanning out one WorkAgentLeaf per task in the parsed arch_plan."""
    sched = isolated_scheduler_root
    r1 = api.bt_tick("实现 login API 模块")
    assert r1.kind == "yield"
    assert r1.dispatch_request.agent_type == "architect"

    r2 = api.bt_tick_resume(r1.tick_id, FAKE_ARCH_RECEIPT)
    assert r2.kind == "yield"
    dr = r2.dispatch_request
    assert dr.agent_type == "work"
    assert dr.agent_file is None
    assert dr.required_capability == "programmer"
    assert dr.subtask_id == "a1"
    rj = json.loads((sched / "bt" / r1.tick_id / "resume.json").read_text(encoding="utf-8"))
    assert any(seg.startswith("WorkAgentLeaf#") for seg in rj["runner_resume_path"]), \
        f"resume path missing WorkAgentLeaf#<id>: {rj['runner_resume_path']}"


def test_resume_clears_resume_json_on_done(isolated_scheduler_root):
    sched = isolated_scheduler_root
    # Full pipeline: architect yield → work yield → Done.
    r1 = api.bt_tick("实现 login API 模块")
    assert r1.kind == "yield"
    r2 = api.bt_tick_resume(r1.tick_id, FAKE_ARCH_RECEIPT)
    assert r2.kind == "yield"
    r3 = api.bt_tick_resume(r1.tick_id, "Done.")
    assert r3.kind == "done"
    assert not (sched / "bt" / r1.tick_id / "resume.json").exists()


def test_dirty_flag_triggers_write(tmp_path):
    bb = Blackboard()
    bb.tick_id = "t1"
    assert bb.dirty
    bb.clear_dirty()
    assert not bb.dirty
    bb.user_request = "x"
    assert bb.dirty


def test_runner_resume_path_persists_in_bb_json(isolated_scheduler_root):
    sched = isolated_scheduler_root
    r = api.bt_tick("实现 login API 模块")
    assert r.kind == "yield"
    raw = json.loads((sched / "bt" / r.tick_id / "bb.json").read_text(encoding="utf-8"))
    assert raw["fields"].get("runner_resume_path"), \
        "runner_resume_path must be persisted into bb.json on yield"
