"""L4 — dream-loop end-to-end tests.

Rollback of t6: the architect / HR governance steps are yield-based again
(DispatchXxxGovern → CollectXxxAdvice pairs), so a single dream_tick(...)
yields for the architect dispatch first, dream_tick_resume(...) drives to
the next yield (HR dispatch), and a second resume drives to done.

These tests cover that two-yield trajectory plus the contract-locked error
paths (run_not_found_or_done / dispatch_result_schema_mismatch).
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


def _arch_report_payload() -> str:
    return json.dumps({
        "arch_governance_report": {
            "safe_actions_applied": ["dna_edit src/foo 补 owner 字段"],
            "advice_pending": [],
        }
    })


def _hr_report_payload() -> str:
    return json.dumps({
        "hr_governance_report": {
            "safe_actions_applied": [],
            "advice_pending": ["translator agent 14 天闲置，建议归档"],
        }
    })


# ---------------------------------------------------------------------------
# E2E cases
# ---------------------------------------------------------------------------

def test_first_tick_yields_for_architect_dispatch(isolated_dirs):
    """Memory step runs in-process and succeeds; architect step is the
    first yield point."""
    res = api.dream_tick("manual")
    assert res.kind == "yield", res.to_dict()
    assert res.dispatch_request is not None
    assert res.dispatch_request.agent_type == "architect"
    assert res.dispatch_request.subtask_id == "governance_knowledge"
    assert res.dispatch_request.prompt.lstrip().startswith("## 治理模式")


def test_two_yields_then_done_writes_full_report(isolated_dirs):
    """architect yield → resume → HR yield → resume → done.
    All three governance step_results should be recorded."""
    scheduler_root, _ = isolated_dirs

    first = api.dream_tick("manual")
    assert first.kind == "yield"
    assert first.dispatch_request.agent_type == "architect"

    second = api.dream_tick_resume(first.run_id, _arch_report_payload())
    assert second.kind == "yield", second.to_dict()
    assert second.dispatch_request.agent_type == "hr"
    assert second.dispatch_request.subtask_id == "governance_capability"

    third = api.dream_tick_resume(second.run_id, _hr_report_payload())
    assert third.kind == "done", third.to_dict()
    assert third.report_path is not None
    assert Path(third.report_path).exists()
    # last_success.json was written
    assert (scheduler_root / "dream" / "last_success.json").exists()

    runs = api.dream_list_runs()
    assert len(runs) == 1
    assert runs[0].status == "done"
    assert set(runs[0].step_results.keys()) == {
        "MemoryStepCatch",
        "ArchStepCatch",
        "HRStepCatch",
    }
    assert all(v == "success" for v in runs[0].step_results.values())


def test_resume_with_invalid_payload_type_returns_error(isolated_dirs):
    """The API rejects non-(str|dict) dispatch_result with the locked
    error_code dispatch_result_schema_mismatch."""
    first = api.dream_tick("manual")
    assert first.kind == "yield"
    res = api.dream_tick_resume(first.run_id, 42)
    assert res.kind == "error"
    assert res.error_code == "dispatch_result_schema_mismatch"


def test_resume_on_unknown_run_returns_run_not_found(isolated_dirs):
    res = api.dream_tick_resume("never-existed", _arch_report_payload())
    assert res.kind == "error"
    assert res.error_code == "run_not_found_or_done"
