"""L4 — dream-loop end-to-end tests.

Drive a full tick through both yield gates (Architect + HR) with a
FakeDispatcher that asserts governance-context invariants on every dispatch.
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


class FakeDispatcher:
    """Drives dream ticks: enforces governance-context invariants on every
    yield (agent_type ∈ {architect, hr}, subtask_id ∈ {governance_knowledge,
    governance_capability}, prompt starts with `## 治理模式`).
    """

    def __init__(self):
        self.dispatches: list[dict] = []

    def drive(self, first: "api.DreamResult", reply_by_agent: dict | None = None):
        reply_by_agent = reply_by_agent or {}
        res = first
        steps = 0
        while res.kind == "yield":
            steps += 1
            assert steps < 10, "yield ping-pong did not terminate"
            dr = res.dispatch_request
            assert dr.agent_type in ("architect", "hr"), dr.agent_type
            assert dr.subtask_id in ("governance_knowledge", "governance_capability"), dr.subtask_id
            assert dr.prompt.startswith("## 治理模式")
            self.dispatches.append({
                "agent_type": dr.agent_type,
                "subtask_id": dr.subtask_id,
            })
            reply = reply_by_agent.get(dr.agent_type, {
                "safe_actions_applied": [f"{dr.agent_type} ack"],
                "advice_pending": [],
            })
            res = api.dream_tick_resume(res.run_id, reply)
        return res


# ---------------------------------------------------------------------------
# E2E cases
# ---------------------------------------------------------------------------

def test_full_tick_drives_to_done(isolated_dirs):
    scheduler_root, _ = isolated_dirs
    first = api.dream_tick("manual")
    final = FakeDispatcher().drive(first)
    assert final.kind == "done", final.to_dict()
    assert final.report_path is not None
    assert Path(final.report_path).exists()
    # last_success.json was written
    assert (scheduler_root / "dream" / "last_success.json").exists()


def test_full_tick_yields_arch_then_hr_in_order(isolated_dirs):
    first = api.dream_tick("manual")
    fd = FakeDispatcher()
    final = fd.drive(first)
    assert final.kind == "done"
    # Architect yield before HR yield.
    types = [d["agent_type"] for d in fd.dispatches]
    assert types == ["architect", "hr"]


def test_done_report_records_all_three_step_results(isolated_dirs):
    first = api.dream_tick("manual")
    final = FakeDispatcher().drive(first)
    assert final.kind == "done"
    runs = api.dream_list_runs()
    assert len(runs) == 1
    assert runs[0].status == "done"
    assert set(runs[0].step_results.keys()) == {
        "MemoryStepCatch",
        "ArchStepCatch",
        "HRStepCatch",
    }
    # All three should be success since FakeDispatcher always replies cleanly
    # and memory step's 4A skeletons are no-op success.
    assert all(v == "success" for v in runs[0].step_results.values())


def test_resume_with_invalid_payload_type_returns_error(isolated_dirs):
    first = api.dream_tick("manual")
    assert first.kind == "yield"
    # Pass an int — not str, not dict.
    res = api.dream_tick_resume(first.run_id, 42)
    assert res.kind == "error"
    assert res.error_code == "dispatch_result_schema_mismatch"
