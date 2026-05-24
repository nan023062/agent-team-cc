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
    # succeeds; arch step's first action is the yield).
    assert res.kind in ("yield", "done"), f"unexpected: {res.to_dict()}"


# ---------------------------------------------------------------------------
# Single-flight
# ---------------------------------------------------------------------------

def test_second_dream_tick_while_running_is_skipped(isolated_dirs):
    scheduler_root, _ = isolated_dirs
    res1 = api.dream_tick("manual")
    assert res1.kind == "yield"
    res2 = api.dream_tick("manual")
    assert res2.kind == "skipped"
    assert res2.reason == "another_run_in_progress"


# ---------------------------------------------------------------------------
# dream_list_runs
# ---------------------------------------------------------------------------

def test_dream_list_runs_returns_empty_when_no_dir(isolated_dirs):
    assert api.dream_list_runs() == []


def test_dream_list_runs_includes_running_tick(isolated_dirs):
    res = api.dream_tick("manual")
    assert res.kind == "yield"
    runs = api.dream_list_runs()
    assert len(runs) == 1
    assert runs[0].run_id == res.run_id
    assert runs[0].status == "running"
    assert runs[0].trigger_reason == "manual"


# ---------------------------------------------------------------------------
# dream_abort
# ---------------------------------------------------------------------------

def test_dream_abort_marks_abandoned_and_clears_current(isolated_dirs):
    scheduler_root, _ = isolated_dirs
    res = api.dream_tick("manual")
    assert res.kind == "yield"
    abort = api.dream_abort(res.run_id, "user_preempted")
    assert abort.aborted is True
    # abandoned.json exists
    assert (scheduler_root / "dream" / res.run_id / "abandoned.json").exists()
    # current.json cleared → another tick can now start
    res2 = api.dream_tick("manual")
    assert res2.kind == "yield"
    # last_success.json must NOT have been written by abort
    assert not (scheduler_root / "dream" / "last_success.json").exists()
    # list_runs reports the aborted one as abandoned
    runs = {r.run_id: r.status for r in api.dream_list_runs()}
    assert runs[res.run_id] == "abandoned"


def test_dream_abort_on_unknown_run_is_noop(isolated_dirs):
    abort = api.dream_abort("does-not-exist", "manual_abort")
    assert abort.aborted is False
