"""PR-C — Blackboard `_extras` persistence round-trip tests.

Covers spec §10.3 cases 23-25.
"""
from __future__ import annotations

from engine.core.blackboard import SCHEMA_VERSION, Blackboard


# ---------------------------------------------------------------------------
# Case 23: round-trip with work_loop_iter + arch_redo_context
# ---------------------------------------------------------------------------

def test_extras_round_trip_preserves_pr_c_scratch_fields():
    bb = Blackboard()
    bb.tick_id = "rt-1"
    bb.user_request = "hi"
    bb.mode = "execution"
    bb.arch_plan = [{"id": "t1"}]
    # PR-C scratch fields ride on bb.__dict__
    bb.work_loop_iter = 2
    bb._loopseq_WorkLoop_iter = 2
    bb.arch_redo_context = {
        "iter": 2,
        "unresolved": [{
            "task_id": "t1",
            "blocking_module": "v1/x",
            "question": "what now?",
            "agent": "programmer",
            "summary": "stuck",
        }],
        "previous_plan": [{"id": "t1"}],
    }
    bb.convergence = "arch_redo"

    raw = bb.to_dict()
    # Extras key is present and inside fields.
    assert "_extras" in raw["fields"], f"missing _extras: {raw['fields']}"
    extras = raw["fields"]["_extras"]
    assert extras["work_loop_iter"] == 2
    assert extras["_loopseq_WorkLoop_iter"] == 2
    assert extras["convergence"] == "arch_redo"
    assert extras["arch_redo_context"]["iter"] == 2

    bb2 = Blackboard.from_dict(raw)
    assert bb2.work_loop_iter == 2
    assert getattr(bb2, "_loopseq_WorkLoop_iter") == 2
    assert bb2.convergence == "arch_redo"
    assert bb2.arch_redo_context == bb.arch_redo_context


# ---------------------------------------------------------------------------
# Case 24: from_dict on an old snapshot lacking _extras is a no-op
# ---------------------------------------------------------------------------

def test_from_dict_without_extras_is_noop():
    old_snapshot = {
        "schema_version": SCHEMA_VERSION,
        "tick_id": "old-1",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "bb_status": "running",
        "fields": {
            "tick_id": "old-1",
            "user_request": "hello",
            "mode": "conversation",
        },
    }
    bb = Blackboard.from_dict(old_snapshot)
    assert bb.tick_id == "old-1"
    assert bb.user_request == "hello"
    assert bb.mode == "conversation"
    # No extras → these are unset (None).
    assert getattr(bb, "work_loop_iter", None) is None
    assert getattr(bb, "convergence", None) is None
    assert getattr(bb, "arch_redo_context", None) is None


# ---------------------------------------------------------------------------
# Case 25: schema_version is unchanged (additive extras stay backward-readable)
# ---------------------------------------------------------------------------

def test_schema_version_unchanged_by_extras():
    bb = Blackboard()
    bb.tick_id = "sv"
    bb.convergence = "done"
    bb.work_loop_iter = 1
    raw = bb.to_dict()
    assert raw["schema_version"] == SCHEMA_VERSION == 3


def test_extras_not_emitted_when_no_scratch_set():
    bb = Blackboard()
    bb.tick_id = "no-extras"
    raw = bb.to_dict()
    # Pure canonical fields only — _extras must not appear.
    assert "_extras" not in raw["fields"]


def test_extras_round_trip_preserves_arch_subtree_state():
    """Arch subtree intermediates ride alongside PR-C fields — verify they
    survive a snapshot cycle too (regression coverage for the in-process
    architect loop)."""
    bb = Blackboard()
    bb.tick_id = "arch"
    bb.arch_plan_draft = [{"id": "t1", "description": "d"}]
    bb.arch_state = "in_sync"
    bb.arch_scan_summary = {"files": 12}
    raw = bb.to_dict()
    assert "_extras" in raw["fields"]
    bb2 = Blackboard.from_dict(raw)
    assert getattr(bb2, "arch_plan_draft") == [{"id": "t1", "description": "d"}]
    assert getattr(bb2, "arch_state") == "in_sync"
    assert getattr(bb2, "arch_scan_summary") == {"files": 12}
