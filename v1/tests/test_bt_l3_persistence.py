"""L3 — persistence: bb.json + resume.json + trace.jsonl round-trips.

Uses pytest tmp_path fixture for the scheduler root; never touches the
real .cbim/ directory.
"""
from __future__ import annotations

import json

import pytest

from engine.bt.api import bt_tick as api
from engine.bt.core.blackboard import Blackboard
from engine.bt.core.runner import Runner
from engine.bt.persistence import snapshot
from engine.bt.tree.main_loop import build_root


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
    bb.iteration = 3
    bb.subtask_results = {"t1": {"status": "ok", "output": "x"}}
    bb.bb_status = "running"

    tick_dir = tmp_path / "abc123"
    snapshot.write_bb(tick_dir, bb)
    assert (tick_dir / "bb.json").exists()

    bb2 = snapshot.read_bb(tick_dir)
    assert bb2.tick_id == "abc123"
    assert bb2.user_request == "hello"
    assert bb2.iteration == 3
    assert bb2.subtask_results == {"t1": {"status": "ok", "output": "x"}}
    assert bb2.bb_status == "running"


# ---------------------------------------------------------------------------
# Yield-path persists resume artifacts
# ---------------------------------------------------------------------------

def test_yield_writes_bb_resume_and_trace(isolated_scheduler_root):
    sched = isolated_scheduler_root
    r = api.bt_tick("查询模块 X 的历史决策")
    assert r.kind == "yield"
    tick_dir = sched / "bt" / r.tick_id
    assert (tick_dir / "bb.json").exists()
    assert (tick_dir / "resume.json").exists()
    assert (tick_dir / "trace.jsonl").exists()


def test_resume_path_includes_subtask_id_suffix(isolated_scheduler_root):
    sched = isolated_scheduler_root
    r = api.bt_tick("查询模块 X 的历史决策")
    rj = json.loads((sched / "bt" / r.tick_id / "resume.json").read_text())
    path = rj["runner_resume_path"]
    assert any(seg.startswith("WorkAgentLeaf#") for seg in path), \
        f"resume path missing WorkAgentLeaf#<id>: {path}"


def test_resume_clears_resume_json_on_done(isolated_scheduler_root):
    sched = isolated_scheduler_root
    r1 = api.bt_tick("查询模块 X 的历史决策")
    r2 = api.bt_tick_resume(r1.tick_id, "X owned by alice")
    assert r2.kind == "done"
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
    r = api.bt_tick("查询模块 X 的历史决策")
    raw = json.loads((sched / "bt" / r.tick_id / "bb.json").read_text())
    assert raw["fields"].get("runner_resume_path"), \
        "runner_resume_path must be persisted into bb.json on yield"
