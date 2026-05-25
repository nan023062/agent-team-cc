"""L1 — dream-loop Action node unit tests.

Pure in-memory, no MCP, no Runner — each Action exercised through tick() /
on_resume() directly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from engine.core.node import Status
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


def test_mem_rebuild_index_skips_when_no_drift(bb, store_dir, backend):
    bb.mem_health = {"index_drift": False}
    node = MemRebuildIndex(store_dir=store_dir, backend=backend)
    assert node.tick(bb) is Status.SUCCESS
    assert bb.mem_index_result == {"skipped": True, "reason": "no_index_drift"}


def test_mem_rebuild_index_runs_when_drift_truthy(bb, store_dir, backend):
    bb.mem_health = {"index_drift": True}
    node = MemRebuildIndex(store_dir=store_dir, backend=backend)
    assert node.tick(bb) is Status.SUCCESS
    assert "indexed" in bb.mem_index_result


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
