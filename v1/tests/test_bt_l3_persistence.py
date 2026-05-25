"""L3 — persistence: bb.json + resume.json + trace.jsonl round-trips (v3).

Uses pytest tmp_path fixture for the scheduler root; never touches the
real .cbim/ directory.
"""
from __future__ import annotations

import json

import pytest

from engine.execution.api import bt_tick as api
from engine.execution.core.blackboard import Blackboard, SCHEMA_VERSION
from engine.execution.persistence import snapshot


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


def test_bb_snapshot_schema_version_is_2():
    bb = Blackboard()
    bb.tick_id = "x"
    raw = bb.to_dict()
    assert raw["schema_version"] == SCHEMA_VERSION == 2


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


def test_resume_path_targets_architect_first(isolated_scheduler_root):
    sched = isolated_scheduler_root
    r = api.bt_tick("实现 login API 模块")
    rj = json.loads((sched / "bt" / r.tick_id / "resume.json").read_text(encoding="utf-8"))
    path = rj["runner_resume_path"]
    # First yield is always DispatchArchitect (execution path).
    assert "DispatchArchitect" in path, f"resume path missing DispatchArchitect: {path}"


def test_resume_path_after_arch_targets_hr(isolated_scheduler_root):
    sched = isolated_scheduler_root
    r1 = api.bt_tick("实现 login API 模块")
    # Resume with an Architect plan.
    arch_reply = '{"arch_plan":[{"id":"a1","description":"d","required_capability":"py"}]}'
    r2 = api.bt_tick_resume(r1.tick_id, arch_reply)
    assert r2.kind == "yield"
    assert r2.dispatch_request.agent_type == "hr"
    rj = json.loads((sched / "bt" / r1.tick_id / "resume.json").read_text(encoding="utf-8"))
    assert "DispatchHR" in rj["runner_resume_path"]


def test_resume_path_includes_task_id_suffix_on_work_yield(isolated_scheduler_root):
    sched = isolated_scheduler_root
    r1 = api.bt_tick("实现 login API 模块")
    arch_reply = '{"arch_plan":[{"id":"a1","description":"d","required_capability":"py"}]}'
    r2 = api.bt_tick_resume(r1.tick_id, arch_reply)  # arch SUCCESS → hr yield
    hr_reply = "task_id=a1 agent_file=.claude/agents/programmer/programmer.md capability=py"
    r3 = api.bt_tick_resume(r1.tick_id, hr_reply)  # hr SUCCESS → work yield
    assert r3.kind == "yield"
    assert r3.dispatch_request.agent_type == "work"
    assert r3.dispatch_request.subtask_id == "a1"
    rj = json.loads((sched / "bt" / r1.tick_id / "resume.json").read_text(encoding="utf-8"))
    assert any(seg.startswith("WorkAgentLeaf#") for seg in rj["runner_resume_path"]), \
        f"resume path missing WorkAgentLeaf#<id>: {rj['runner_resume_path']}"


def test_resume_clears_resume_json_on_done(isolated_scheduler_root):
    sched = isolated_scheduler_root
    # Drive an execution flow all the way to Done, then verify resume.json
    # was cleaned up. The Done BtResult has no tick_id, so we scan the
    # scheduler dir for the single tick we created.
    arch_reply = '{"arch_plan":[{"id":"a1","description":"d","required_capability":"py"}]}'
    hr_reply = "task_id=a1 agent_file=.claude/agents/programmer/programmer.md capability=py"
    r1 = api.bt_tick("实现 login API 模块")
    r2 = api.bt_tick_resume(r1.tick_id, arch_reply)
    r3 = api.bt_tick_resume(r1.tick_id, hr_reply)
    r4 = api.bt_tick_resume(r1.tick_id, "Done.")
    assert r4.kind == "done"
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
    raw = json.loads((sched / "bt" / r.tick_id / "bb.json").read_text(encoding="utf-8"))
    assert raw["fields"].get("runner_resume_path"), \
        "runner_resume_path must be persisted into bb.json on yield"
