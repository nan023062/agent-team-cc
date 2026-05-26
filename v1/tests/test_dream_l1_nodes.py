"""L1 — dream-loop Action node unit tests.

Pure in-memory, no MCP, no Runner — each Action exercised through tick() /
on_resume() directly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import json

from engine.core.node import Status
from engine.dream.actions.collect_arch_advice import CollectArchAdvice
from engine.dream.actions.collect_hr_advice import CollectHRAdvice
from engine.dream.actions.dispatch_arch import DispatchArchGovern
from engine.dream.actions.dispatch_hr import DispatchHRGovern
from engine.dream.actions.emit_report import EmitReport
from engine.dream.actions.finalize import FinalizeDreamTick
from engine.dream.actions.init_tick import InitDreamTick
from engine.dream.actions.mem_steps import (
    MemCompact,
    MemHealthScan,
    MemRebuildIndex,
    MemSweepExpired,
)
from engine.dream.core.blackboard import DreamBlackboard
from memory.crud.file_backend import FileBackend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bb() -> DreamBlackboard:
    b = DreamBlackboard()
    b.run_id = "test-run"
    b.trigger_reason = "manual"
    return b


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    d = tmp_path / "memory"
    (d / "short").mkdir(parents=True)
    (d / "medium").mkdir(parents=True)
    return d


@pytest.fixture
def backend(store_dir: Path) -> FileBackend:
    return FileBackend(store_dir)


# ---------------------------------------------------------------------------
# InitDreamTick
# ---------------------------------------------------------------------------

def test_init_dream_tick_fills_defaults(bb):
    node = InitDreamTick()
    assert node.tick(bb) is Status.SUCCESS
    assert bb.step_results == {}
    assert bb.bb_status == "running"
    assert bb.started_at is not None


def test_init_dream_tick_is_idempotent(bb):
    bb.started_at = "2026-01-01T00:00:00+00:00"
    bb.step_results = {"memory": "success"}
    node = InitDreamTick()
    assert node.tick(bb) is Status.SUCCESS
    # Should NOT clobber pre-existing values.
    assert bb.started_at == "2026-01-01T00:00:00+00:00"
    assert bb.step_results == {"memory": "success"}


# ---------------------------------------------------------------------------
# Memory step actions
# ---------------------------------------------------------------------------

def test_mem_health_scan_returns_success_with_skeleton(bb, store_dir):
    node = MemHealthScan(store_dir=store_dir)
    assert node.tick(bb) is Status.SUCCESS
    # HealthChecker 4A skeleton returns a HealthReport — _report_to_dict converts.
    assert isinstance(bb.mem_health, dict)


def test_mem_compact_returns_success_with_skeleton(bb, store_dir):
    node = MemCompact(store_dir=store_dir)
    assert node.tick(bb) is Status.SUCCESS
    assert isinstance(bb.mem_compact_result, dict)


def test_mem_sweep_expired_returns_success_with_empty_store(bb, store_dir, backend):
    node = MemSweepExpired(store_dir=store_dir, backend=backend)
    assert node.tick(bb) is Status.SUCCESS
    assert bb.mem_sweep_result == {"deleted": 0, "keep_days": 3}


def test_mem_rebuild_index_always_runs(bb, store_dir, backend):
    """v2: rebuild_and_verify runs every tick (no index_drift skip path).

    Returns a RebuildReport dict containing indexed_count + drift_*
    fields. Empty store → indexed_count=0 but the call still succeeds.
    """
    node = MemRebuildIndex(store_dir=store_dir, backend=backend)
    assert node.tick(bb) is Status.SUCCESS
    assert "indexed_count" in bb.mem_index_result
    assert "drift_checked" in bb.mem_index_result


# ---------------------------------------------------------------------------
# Emit / Finalize
# ---------------------------------------------------------------------------

def test_emit_report_writes_markdown(bb, tmp_path):
    scheduler_root = tmp_path / "scheduler"
    bb.step_results = {"memory": "success", "knowledge": "failure", "capability": "success"}
    node = EmitReport(scheduler_root=scheduler_root)
    assert node.tick(bb) is Status.SUCCESS
    report = Path(bb.report_path)
    assert report.exists()
    content = report.read_text(encoding="utf-8")
    assert "Dream Tick Report" in content
    assert "memory" in content and "knowledge" in content
    assert bb.summary_for_session.startswith("[CBIM dream test-run]")


def test_finalize_writes_last_success_json(bb, tmp_path):
    scheduler_root = tmp_path / "scheduler"
    bb.report_path = str(tmp_path / "report.md")
    bb.step_results = {"memory": "success"}
    node = FinalizeDreamTick(scheduler_root=scheduler_root)
    assert node.tick(bb) is Status.SUCCESS
    last = scheduler_root / "dream" / "last_success.json"
    assert last.exists()
    import json
    payload = json.loads(last.read_text(encoding="utf-8"))
    assert payload["run_id"] == "test-run"
    assert payload["summary_path"] == str(tmp_path / "report.md")
    assert payload["step_results"] == {"memory": "success"}
    assert bb.finished_at is not None


# ---------------------------------------------------------------------------
# Architect governance dispatch + collect
# ---------------------------------------------------------------------------

def test_dispatch_arch_yields_on_first_tick_then_succeeds(bb):
    node = DispatchArchGovern()
    # First tick → yield: fills bb.pending_dispatch and sets the flag.
    assert node.tick(bb) is Status.RUNNING
    assert bb.arch_governance_dispatched is True
    pd = bb.pending_dispatch
    assert pd is not None
    assert pd.agent_type == "architect"
    assert pd.subtask_id == "governance_knowledge"
    assert pd.prompt.lstrip().startswith("## 治理模式")
    # Second tick (idempotent path) → SUCCESS, no re-dispatch.
    bb.pending_dispatch = None
    assert node.tick(bb) is Status.SUCCESS


def test_collect_arch_advice_parses_payload_on_resume(bb):
    node = CollectArchAdvice()
    bb.arch_governance_dispatched = True
    payload = json.dumps({
        "arch_governance_report": {
            "safe_actions_applied": ["dna_edit src/foo 补 owner"],
            "advice_pending": [],
        }
    })
    node.on_resume(bb, payload)
    assert bb.arch_governance_report == {
        "safe_actions_applied": ["dna_edit src/foo 补 owner"],
        "advice_pending": [],
    }
    assert bb.pending_dispatch is None
    # Tick after resume is SUCCESS (report present).
    assert node.tick(bb) is Status.SUCCESS


def test_collect_arch_advice_no_dispatch_is_noop(bb):
    node = CollectArchAdvice()
    # Never dispatched → SUCCESS no-op, no error report written.
    assert node.tick(bb) is Status.SUCCESS
    assert bb.arch_governance_report is None


def test_collect_arch_advice_dispatched_but_no_resume_is_failure(bb):
    node = CollectArchAdvice()
    bb.arch_governance_dispatched = True
    # Tick without on_resume having been called → FAILURE with placeholder.
    assert node.tick(bb) is Status.FAILURE
    assert bb.arch_governance_report["error"] == "no_payload_received"


# ---------------------------------------------------------------------------
# HR governance dispatch + collect (mirror of arch)
# ---------------------------------------------------------------------------

def test_dispatch_hr_yields_on_first_tick_then_succeeds(bb):
    node = DispatchHRGovern()
    assert node.tick(bb) is Status.RUNNING
    assert bb.hr_governance_dispatched is True
    pd = bb.pending_dispatch
    assert pd is not None
    assert pd.agent_type == "hr"
    assert pd.subtask_id == "governance_capability"
    assert pd.prompt.lstrip().startswith("## 治理模式")
    bb.pending_dispatch = None
    assert node.tick(bb) is Status.SUCCESS


def test_collect_hr_advice_parses_payload_on_resume(bb):
    node = CollectHRAdvice()
    bb.hr_governance_dispatched = True
    payload = json.dumps({
        "hr_governance_report": {
            "safe_actions_applied": [],
            "advice_pending": ["translator agent 14 天闲置，建议归档"],
        }
    })
    node.on_resume(bb, payload)
    assert bb.hr_governance_report == {
        "safe_actions_applied": [],
        "advice_pending": ["translator agent 14 天闲置，建议归档"],
    }
    assert bb.pending_dispatch is None
    assert node.tick(bb) is Status.SUCCESS


def test_collect_hr_advice_extracts_dict_payload_output(bb):
    """on_resume should unwrap the Task-tool dict shape {status, output, ...}."""
    node = CollectHRAdvice()
    bb.hr_governance_dispatched = True
    raw = {
        "status": "ok",
        "output": json.dumps({
            "hr_governance_report": {
                "safe_actions_applied": ["agent_edit translator 补 description"],
                "advice_pending": [],
            }
        }),
    }
    node.on_resume(bb, raw)
    assert bb.hr_governance_report["safe_actions_applied"] == [
        "agent_edit translator 补 description"
    ]
