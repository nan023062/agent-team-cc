"""Tests for dispatch_work.WorkAgentLeaf.on_resume + receipt integration.

Covers PR-A spec §8.2 cases 10-13.
"""
from __future__ import annotations

from types import SimpleNamespace

from engine.core.node import Status
from engine.execution.actions.dispatch_work import WorkAgentLeaf


def _bb_with_task(task_id: str = "t1") -> SimpleNamespace:
    bb = SimpleNamespace()
    bb.arch_plan = [{
        "id": task_id,
        "description": "do the thing",
        "required_capability": "programmer",
        "params": {},
        "arch_context": "",
    }]
    bb.work_results = {}
    bb.pending_dispatch = None
    bb.user_request = "do the thing"
    bb.trace = []
    return bb


def _drive_to_resume(leaf: WorkAgentLeaf, bb, payload) -> Status:
    """Common pattern: tick once (RUNNING + pending_dispatch), resume, tick again."""
    first = leaf.tick(bb)
    assert first is Status.RUNNING
    assert bb.pending_dispatch is not None
    leaf.on_resume(bb, payload)
    return leaf.tick(bb)


def _trailer(status: str, **fields) -> str:
    lines = [f"status: {status}"]
    for k, v in fields.items():
        lines.append(f"{k}: {v}")
    body = "\n".join(lines)
    return (
        "prose body here\n\n"
        "<!-- BEGIN CBIM-RECEIPT v1\n"
        f"{body}\n"
        "END CBIM-RECEIPT -->\n"
    )


# ---------------------------------------------------------------------------
# Case 10 — clean ok reply
# ---------------------------------------------------------------------------

def test_on_resume_with_clean_ok_reply():
    bb = _bb_with_task("t1")
    leaf = WorkAgentLeaf(task_id="t1")
    payload = _trailer(
        "ok",
        task_id="t1",
        agent="programmer",
        summary="did the work cleanly.",
        artifacts="a.py, b.py",
    )
    status = _drive_to_resume(leaf, bb, payload)
    assert status is Status.SUCCESS
    result = bb.work_results["t1"]
    assert result["status"] == "ok"
    assert result["summary"] == "did the work cleanly."
    assert result["artifacts"] == ["a.py", "b.py"]
    assert result["agent"] == "programmer"
    assert result["question"] is None
    assert result["failure_kind"] is None
    assert result["output"] == payload  # prose body preserved verbatim


# ---------------------------------------------------------------------------
# Case 11 — needs_arch_decision reply
# ---------------------------------------------------------------------------

def test_on_resume_with_needs_arch_decision():
    bb = _bb_with_task("t1")
    leaf = WorkAgentLeaf(task_id="t1")
    payload = _trailer(
        "needs_arch_decision",
        task_id="t1",
        agent="programmer",
        summary="spec missing.",
        question="What goes in field X?",
        blocking_module="v1/kernel/engine/execution",
    )
    status = _drive_to_resume(leaf, bb, payload)
    # PR-C: leaf returns SUCCESS for any terminal status so ConvergeJudge
    # can run downstream and route the escalation. Status routing now
    # lives on bb.work_results[*].status (read by ConvergeJudge), not on
    # the leaf's tick return code.
    assert status is Status.SUCCESS
    result = bb.work_results["t1"]
    assert result["status"] == "needs_arch_decision"
    assert result["question"] == "What goes in field X?"
    assert result["blocking_module"] == "v1/kernel/engine/execution"


# ---------------------------------------------------------------------------
# Case 12 — failed reply
# ---------------------------------------------------------------------------

def test_on_resume_with_failed_reply():
    bb = _bb_with_task("t1")
    leaf = WorkAgentLeaf(task_id="t1")
    payload = _trailer(
        "failed",
        task_id="t1",
        agent="programmer",
        summary="pytest segfaults.",
        failure_kind="test_failed",
    )
    status = _drive_to_resume(leaf, bb, payload)
    # PR-C: leaf SUCCESS even on failed status — judge aggregates downstream.
    assert status is Status.SUCCESS
    result = bb.work_results["t1"]
    assert result["status"] == "failed"
    assert result["failure_kind"] == "test_failed"


# ---------------------------------------------------------------------------
# Case 13 — legacy reply (no trailer) — backward compatible
# ---------------------------------------------------------------------------

def test_on_resume_with_legacy_reply_is_backward_compatible():
    bb = _bb_with_task("t1")
    leaf = WorkAgentLeaf(task_id="t1")
    payload = "Done. Patch applied."  # no trailer at all
    status = _drive_to_resume(leaf, bb, payload)
    assert status is Status.SUCCESS
    result = bb.work_results["t1"]
    assert result["status"] == "ok"
    assert result["agent"] == "unknown"
    assert result["extras"]["_legacy"] == "no_trailer"


def test_on_resume_handles_dict_payload_with_output_key():
    """The Task tool may hand us a dict {output: text}; ensure that path still works."""
    bb = _bb_with_task("t1")
    leaf = WorkAgentLeaf(task_id="t1")
    payload = {
        "output": _trailer(
            "ok",
            task_id="t1",
            agent="programmer",
            summary="dict payload path works.",
        )
    }
    status = _drive_to_resume(leaf, bb, payload)
    assert status is Status.SUCCESS
    result = bb.work_results["t1"]
    assert result["status"] == "ok"
    assert result["summary"] == "dict payload path works."
    assert result["raw"] == payload  # raw is the original non-string payload
