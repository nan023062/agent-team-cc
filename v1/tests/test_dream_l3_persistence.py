"""L3 — dream-loop persistence + 20h-window gate tests.

Uses tmp_path for the scheduler root so each test is isolated.
Monkey-patches engine.dream.api.dream_tick._scheduler_root and _memory_store_dir
to route writes under tmp_path.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from engine.dream.api import dream_tick as api


@pytest.fixture
def isolated_dirs(tmp_path: Path, monkeypatch):
    scheduler_root = tmp_path / "scheduler"
    memory_root = tmp_path / "memory"
    (memory_root / "short").mkdir(parents=True)
    (memory_root / "medium").mkdir(parents=True)
    scheduler_root.mkdir(parents=True)
    # Seed .last_distill so MemDistillGate's weekly-cadence rule does not
    # fire — keeps these persistence tests on the original 2-yield trajectory
    # (architect → HR). Distill-specific behaviour is exercised separately.
    (memory_root / ".last_distill").write_text("seeded\n", encoding="utf-8")

    monkeypatch.setattr(api, "_scheduler_root", lambda: scheduler_root)
    monkeypatch.setattr(api, "_memory_store_dir", lambda: memory_root)
    return scheduler_root, memory_root


# ---------------------------------------------------------------------------
# Window gate
# ---------------------------------------------------------------------------

def test_catchup_within_20h_window_returns_skipped(isolated_dirs):
    scheduler_root, _ = isolated_dirs
    dream_root = scheduler_root / "dream"
    dream_root.mkdir(parents=True, exist_ok=True)
    last = datetime.now(timezone.utc) - timedelta(hours=2)
    (dream_root / "last_success.json").write_text(
        json.dumps({"finished_at": last.isoformat(timespec="seconds")}),
        encoding="utf-8",
    )
    res = api.dream_tick("catchup")
    assert res.kind == "skipped"
    assert res.reason == "within_window"


def test_catchup_outside_20h_window_runs(isolated_dirs):
    scheduler_root, _ = isolated_dirs
    dream_root = scheduler_root / "dream"
    dream_root.mkdir(parents=True, exist_ok=True)
    long_ago = datetime.now(timezone.utc) - timedelta(hours=25)
    (dream_root / "last_success.json").write_text(
        json.dumps({"finished_at": long_ago.isoformat(timespec="seconds")}),
        encoding="utf-8",
    )
    res = api.dream_tick("catchup")
    # First yield is Architect dispatch (memory step runs in-process and
    # succeeds; arch step's first action is the yield to the architect agent).
    assert res.kind == "yield", f"unexpected: {res.to_dict()}"
    assert res.dispatch_request is not None
    assert res.dispatch_request.agent_type == "architect"


# ---------------------------------------------------------------------------
# Single-flight
# ---------------------------------------------------------------------------
#
# A fresh dream_tick yields at the architect-dispatch leaf; after that
# yield the engine has written `current.json` and the persistent RUNNING
# state we need to test single-flight / abort / list_runs against.
# `_seed_running_tick` still synthesizes a stuck tick on disk so tests
# don't depend on a real mid-tick suspension survival.


def _seed_running_tick(scheduler_root, run_id: str = "stuck-run") -> None:
    """Write a minimal bb.json + current.json that look like a tick in
    flight, without ever invoking the engine."""
    dream_dir = scheduler_root / "dream"
    tick_dir = dream_dir / run_id
    tick_dir.mkdir(parents=True, exist_ok=True)
    (tick_dir / "bb.json").write_text(json.dumps({
        "schema_version": 2,
        "tick_id": run_id,
        "bb_status": "running",
        "created_at": "2026-05-25T00:00:00+00:00",
        "updated_at": "2026-05-25T00:00:00+00:00",
        "fields": {
            "tick_id": run_id,
            "trigger_reason": "manual",
            "started_at": "2026-05-25T00:00:00+00:00",
            "step_results": {},
        },
    }), encoding="utf-8")
    (dream_dir / "current.json").write_text(json.dumps({
        "run_id": run_id,
        "status": "running",
        "started_at": "2026-05-25T00:00:00+00:00",
        "last_heartbeat": "2026-05-25T00:00:00+00:00",
    }), encoding="utf-8")


def test_second_dream_tick_while_running_is_skipped(isolated_dirs):
    scheduler_root, _ = isolated_dirs
    _seed_running_tick(scheduler_root)
    res = api.dream_tick("manual")
    assert res.kind == "skipped"
    assert res.reason == "another_run_in_progress"


# ---------------------------------------------------------------------------
# dream_list_runs
# ---------------------------------------------------------------------------

def test_dream_list_runs_returns_empty_when_no_dir(isolated_dirs):
    assert api.dream_list_runs() == []


def test_dream_list_runs_includes_running_tick(isolated_dirs):
    scheduler_root, _ = isolated_dirs
    _seed_running_tick(scheduler_root, run_id="stuck-1")
    runs = api.dream_list_runs()
    assert len(runs) == 1
    assert runs[0].run_id == "stuck-1"
    assert runs[0].status == "running"
    assert runs[0].trigger_reason == "manual"


def test_dream_list_runs_records_done_tick(isolated_dirs):
    """A full tick yields twice (architect → HR) then drives to done;
    list_runs should pick up the done state."""
    first = api.dream_tick("manual")
    assert first.kind == "yield"
    second = api.dream_tick_resume(
        first.run_id,
        json.dumps({"arch_governance_report": {"safe_actions_applied": [], "advice_pending": []}}),
    )
    assert second.kind == "yield"
    third = api.dream_tick_resume(
        second.run_id,
        json.dumps({"hr_governance_report": {"safe_actions_applied": [], "advice_pending": []}}),
    )
    assert third.kind == "done", third.to_dict()
    runs = api.dream_list_runs()
    assert len(runs) == 1
    assert runs[0].status == "done"


# ---------------------------------------------------------------------------
# dream_abort
# ---------------------------------------------------------------------------

def test_dream_abort_marks_abandoned_and_clears_current(isolated_dirs):
    scheduler_root, _ = isolated_dirs
    _seed_running_tick(scheduler_root, run_id="stuck-abort")
    abort = api.dream_abort("stuck-abort", "user_preempted")
    assert abort.aborted is True
    # abandoned.json exists
    assert (scheduler_root / "dream" / "stuck-abort" / "abandoned.json").exists()
    # current.json cleared → another tick can now start
    res2 = api.dream_tick("manual")
    assert res2.kind in ("done", "yield")
    # The aborted tick must NOT advance last_success.json by itself; a
    # subsequent successful tick may, so we only assert the abort half here.
    runs = {r.run_id: r.status for r in api.dream_list_runs()}
    assert runs["stuck-abort"] == "abandoned"


def test_dream_abort_on_unknown_run_is_noop(isolated_dirs):
    abort = api.dream_abort("does-not-exist", "manual_abort")
    assert abort.aborted is False
