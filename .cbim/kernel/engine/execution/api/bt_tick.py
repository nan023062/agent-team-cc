"""api/bt_tick.py — MCP-facing top-level entry points.

Public surface (mirrored 1:1 by mcp_server/tools/bt.py):
  bt_tick(user_request, context=None) -> BtResult
  bt_tick_resume(tick_id, dispatch_result) -> BtResult
  bt_list_running_ticks() -> list[TickStatus]
  bt_abort(tick_id, reason="") -> dict

The engine knows nothing about MCP; the bt.py tools file is a thin shim
that calls these and serializes BtResult via .to_dict().
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from engine.core.blackboard import Blackboard
from engine.core.runner import Runner
from engine.persistence import snapshot
from ..tree.main_loop import ROOT
from .result import BtResult, DispatchRequest, TickStatus


# Lazily import scheduler_root resolver to avoid hard dep on `context` at import time.
def _scheduler_root() -> Path:
    try:
        from context import cbim_dir
        return cbim_dir() / "scheduler"
    except Exception:
        return Path.cwd() / ".cbim" / "scheduler"


# PR-D: both ArchExecYield (WorkLoop's first child) and
# DispatchCoreAgent#architect (ArchitectBranch) dispatch agent_type=
# "architect". The Runner's default agent_type→leaf map points
# "architect" at DispatchCoreAgent#architect, which is right for the
# core-agent branch but wrong for the WorkLoop. The two-level subtask
# map below routes by (agent_type, subtask_id):
#
#   ("architect", "core:architect") → DispatchCoreAgent#architect
#   ("architect", "arch:<n>")       → ArchExecYield  (single-level
#                                       fallback below catches this)
#
# We override the single-level default for "architect" to "ArchExecYield"
# so the WorkLoop yield resumes at the right leaf. The subtask map
# above takes priority for the core-agent branch — see runner's
# `_build_resume_path` priority chain.
from engine.core.runner import DEFAULT_AGENT_TYPE_TO_LEAF as _RUNNER_DEFAULT_MAP

_AGENT_TYPE_TO_LEAF: dict[str, str] = {
    **_RUNNER_DEFAULT_MAP,
    "architect": "ArchExecYield",
}

_AGENT_SUBTASK_TO_LEAF: dict[str, dict[str, str]] = {
    "architect": {"core:architect": "DispatchCoreAgent#architect"},
}


def _build_runner() -> Runner:
    return Runner(
        ROOT,
        scheduler_root=_scheduler_root(),
        agent_type_to_leaf=_AGENT_TYPE_TO_LEAF,
        agent_subtask_to_leaf=_AGENT_SUBTASK_TO_LEAF,
    )


def bt_tick(user_request: str, context: dict | None = None) -> BtResult:
    """Start a new tick. Generates tick_id, initializes bb, drives to
    first yield / Done / Error."""
    try:
        tick_id = uuid.uuid4().hex[:12]
        bb = Blackboard()
        bb.tick_id = tick_id
        bb.user_request = user_request
        bb.mode = None
        bb.arch_plan = None
        bb.agent_assignments = None
        bb.work_results = {}
        bb.bb_status = "running"

        runner = _build_runner()
        rr = runner.run(bb)
        return _to_bt_result(rr, tick_id)
    except Exception as e:
        return BtResult(
            kind="error",
            error_code="engine_internal",
            error_message=f"{type(e).__name__}: {e}",
        )


def bt_tick_resume(tick_id: str, dispatch_result: Any) -> BtResult:
    """Resume a yielded tick."""
    try:
        tick_dir = _scheduler_root() / "bt" / tick_id
        bb = snapshot.read_bb(tick_dir)
        if bb is None or bb.bb_status != "running":
            return BtResult(
                kind="error",
                error_code="tick_not_found_or_done",
                error_message=f"tick_id {tick_id} not found or already terminal",
            )
        runner = _build_runner()
        rr = runner.resume(bb, dispatch_result)
        return _to_bt_result(rr, tick_id)
    except Exception as e:
        return BtResult(
            kind="error",
            error_code="engine_internal",
            error_message=f"{type(e).__name__}: {e}",
        )


def bt_list_running_ticks() -> list[TickStatus]:
    """List all bb_status=running ticks under .cbim/scheduler/bt/."""
    root = _scheduler_root() / "bt"
    out: list[TickStatus] = []
    if not root.exists():
        return out
    for d in root.iterdir():
        if not d.is_dir():
            continue
        bb_path = d / "bb.json"
        if not bb_path.exists():
            continue
        try:
            raw = json.loads(bb_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if raw.get("bb_status") != "running":
            continue
        fields = raw.get("fields", {}) or {}
        # Read last_yield dispatch from resume.json if available.
        last_agent: str | None = None
        rp = d / "resume.json"
        if rp.exists():
            try:
                rj = json.loads(rp.read_text(encoding="utf-8"))
                pd = rj.get("pending_dispatch") or {}
                last_agent = pd.get("agent_type")
            except (OSError, ValueError):
                pass
        out.append(TickStatus(
            tick_id=raw.get("tick_id") or d.name,
            created_at=raw.get("created_at"),
            updated_at=raw.get("updated_at"),
            user_request=(fields.get("user_request") or "")[:200],
            last_yield_dispatch_agent=last_agent,
        ))
    out.sort(key=lambda t: t.updated_at or "", reverse=True)
    return out


def bt_abort(tick_id: str, reason: str = "") -> dict:
    """Mark a running tick as aborted (sets bb_status=error + writes reason)."""
    tick_dir = _scheduler_root() / "bt" / tick_id
    bb = snapshot.read_bb(tick_dir)
    if bb is None:
        return {"ok": False, "error": "tick_not_found"}
    if bb.bb_status != "running":
        return {"ok": False, "error": "tick_not_running", "status": bb.bb_status}
    bb.bb_status = "error"
    bb.interrupt_reason = bb.interrupt_reason or f"aborted: {reason}"
    snapshot.write_bb(tick_dir, bb)
    snapshot.delete_resume(tick_dir)
    return {"ok": True, "tick_id": tick_id, "reason": reason}


def _to_bt_result(rr, tick_id: str) -> BtResult:
    if rr.kind == "done":
        return BtResult(kind="done", user_message=rr.user_message)
    if rr.kind == "yield":
        return BtResult(
            kind="yield",
            tick_id=tick_id,
            dispatch_request=rr.dispatch_request,
        )
    return BtResult(
        kind="error",
        error_code=rr.error_code or "engine_internal",
        error_message=rr.error_message or "",
        interrupt_reason=rr.interrupt_reason,
    )
