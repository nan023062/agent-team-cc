"""L4 — dream-loop end-to-end tests.

Post-t6: arch_gov + hr_gov are in-process BT subtrees, so a single
dream_tick("manual") drives all three governance steps to completion in
one shot — no yield/resume ping-pong. These tests assert the same end-
state contract (report on disk, last_success.json, three step_results
keys) but on a single call.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.dream.api import dream_tick as api


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
# E2E cases
# ---------------------------------------------------------------------------

def test_full_tick_drives_to_done(isolated_dirs):
    scheduler_root, _ = isolated_dirs
    res = api.dream_tick("manual")
    assert res.kind == "done", res.to_dict()
    assert res.report_path is not None
    assert Path(res.report_path).exists()
    # last_success.json was written
    assert (scheduler_root / "dream" / "last_success.json").exists()


def test_done_report_records_all_three_step_results(isolated_dirs):
    res = api.dream_tick("manual")
    assert res.kind == "done"
    runs = api.dream_list_runs()
    assert len(runs) == 1
    assert runs[0].status == "done"
    assert set(runs[0].step_results.keys()) == {
        "MemoryStepCatch",
        "ArchStepCatch",
        "HRStepCatch",
    }
    # All three steps run in-process with NullLLM; memory step's 4A
    # skeletons are no-op success; arch/HR scans return empty findings on
    # the NullLLM stub reply but still SUCCEED — so all three are success.
    assert all(v == "success" for v in runs[0].step_results.values())


def test_resume_with_invalid_payload_type_returns_error(isolated_dirs):
    """The arch/HR subtrees no longer yield, so we can't get a live yield
    handle. Instead, drive a tick to done, then call resume on the now-
    terminal run with a bad payload — the API still rejects on type."""
    first = api.dream_tick("manual")
    # First call already drives to done now; resume of a finished run
    # surfaces 'run_not_found_or_done', not the schema check.
    if first.kind == "done":
        # Synthesize a RUNNING tick on disk so resume gets past the
        # status gate and hits the dispatch_result schema validation.
        scheduler_root = api._scheduler_root()
        run_id = "fake-running"
        tick_dir = scheduler_root / "dream" / run_id
        tick_dir.mkdir(parents=True, exist_ok=True)
        (tick_dir / "bb.json").write_text(json.dumps({
            "schema_version": 2,
            "tick_id": run_id,
            "bb_status": "running",
            "fields": {"tick_id": run_id},
        }), encoding="utf-8")
        res = api.dream_tick_resume(run_id, 42)
    else:
        res = api.dream_tick_resume(first.run_id, 42)
    assert res.kind == "error"
    assert res.error_code == "dispatch_result_schema_mismatch"
