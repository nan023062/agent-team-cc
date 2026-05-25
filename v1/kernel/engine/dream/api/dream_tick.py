"""api/dream_tick.py — public dream-loop entry points.

Public surface (mirrored 1:1 by mcp_server/tools/dream.py):
  dream_tick(reason, run_id=None)             → DreamResult
  dream_tick_resume(run_id, dispatch_result)  → DreamResult
  dream_list_runs(limit=10)                   → list[DreamRunSummary]
  dream_abort(run_id, reason)                 → AbortResult

The dream loop reuses bt.core.Runner + bt.persistence.snapshot, persisting
under `<scheduler_root>/dream/<run_id>/`.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.execution.core.runner import Runner
from engine.execution.persistence import snapshot

from ..core.blackboard import DreamBlackboard
from ..tree.dream_loop import build_dream_root
from .result import (
    AbortResult,
    DispatchRequest,
    DreamResult,
    DreamRunSummary,
    DREAM_AGENT_TYPE_TO_LEAF,
)


# Window for catchup-trigger gate (per contract). manual / forced bypass.
_CATCHUP_WINDOW_HOURS = 20

# Heartbeat for "stale running" detection by SessionStart hook.
_HEARTBEAT_STALE_MINUTES = 30


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _scheduler_root() -> Path:
    try:
        from context import cbim_dir  # type: ignore[import-not-found]
        return cbim_dir() / "scheduler"
    except Exception:
        return Path.cwd() / ".cbim" / "scheduler"


def _memory_store_dir() -> Path:
    try:
        from context import cbim_dir  # type: ignore[import-not-found]
        return cbim_dir() / "memory"
    except Exception:
        return Path.cwd() / ".cbim" / "memory"


def _dream_root() -> Path:
    return _scheduler_root() / "dream"


def _run_dir(run_id: str) -> Path:
    return _dream_root() / run_id


# ---------------------------------------------------------------------------
# Window gate
# ---------------------------------------------------------------------------

def _last_success_iso() -> str | None:
    p = _dream_root() / "last_success.json"
    if not p.exists():
        return None
    try:
        return (json.loads(p.read_text(encoding="utf-8")) or {}).get("finished_at")
    except (OSError, ValueError):
        return None


def _within_catchup_window() -> bool:
    last = _last_success_iso()
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False
    delta_hours = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600.0
    return delta_hours < _CATCHUP_WINDOW_HOURS


def _current_running_run_id() -> str | None:
    p = _dream_root() / "current.json"
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return None
    if raw.get("status") != "running":
        return None
    return raw.get("run_id")


def _write_current(run_id: str, status: str = "running") -> None:
    d = _dream_root()
    d.mkdir(parents=True, exist_ok=True)
    target = d / "current.json"
    tmp = d / "current.json.tmp"
    payload = {
        "run_id": run_id,
        "status": status,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "last_heartbeat": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)


def _touch_current_heartbeat(run_id: str) -> None:
    p = _dream_root() / "current.json"
    if not p.exists():
        return
    try:
        raw = json.loads(p.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return
    if raw.get("run_id") != run_id:
        return
    raw["last_heartbeat"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def dream_tick(reason: str, run_id: str | None = None) -> DreamResult:
    """Start a new governance tick. See .dna/contract.md `dream_tick`."""
    try:
        # Window gate (catchup only).
        if reason == "catchup" and _within_catchup_window():
            return DreamResult(kind="skipped", reason="within_window")

        # Single-flight: don't start another while one is running.
        if _current_running_run_id() is not None:
            return DreamResult(kind="skipped", reason="another_run_in_progress")

        run_id = run_id or uuid.uuid4().hex[:12]
        bb = DreamBlackboard()
        bb.run_id = run_id
        bb.trigger_reason = reason
        bb.bb_status = "running"
        bb.step_results = {}

        _write_current(run_id, "running")

        root = build_dream_root(
            scheduler_root=_scheduler_root(),
            memory_store_dir=_memory_store_dir(),
        )
        runner = Runner(
            root,
            scheduler_root=_scheduler_root(),
            subdir="dream",
            agent_type_to_leaf=DREAM_AGENT_TYPE_TO_LEAF,
        )
        rr = runner.run(bb)
        return _to_dream_result(rr, run_id, bb)
    except Exception as e:
        return DreamResult(
            kind="error",
            error_code="engine_internal",
            error_message=f"{type(e).__name__}: {e}",
        )


def dream_tick_resume(run_id: str, dispatch_result: Any) -> DreamResult:
    """Resume a yielded governance tick. See .dna/contract.md."""
    try:
        tick_dir = _scheduler_root() / "dream" / run_id
        bb = snapshot.read_bb(tick_dir)
        # snapshot.read_bb returns a bt Blackboard — we want a DreamBlackboard.
        # Re-read raw and rebuild.
        bb_path = tick_dir / "bb.json"
        if not bb_path.exists():
            return DreamResult(
                kind="error",
                error_code="run_not_found_or_done",
                error_message=f"run_id {run_id} not found",
            )
        raw = json.loads(bb_path.read_text(encoding="utf-8"))
        if raw.get("bb_status") != "running":
            return DreamResult(
                kind="error",
                error_code="run_not_found_or_done",
                error_message=f"run_id {run_id} is not running",
            )
        bb = DreamBlackboard.from_dict(raw)

        # Validate dispatch_result shape: must be str or dict.
        if not isinstance(dispatch_result, (str, dict)):
            return DreamResult(
                kind="error",
                error_code="dispatch_result_schema_mismatch",
                error_message=f"dispatch_result must be str or dict, got {type(dispatch_result).__name__}",
            )

        # Restore runner_resume_path from resume.json if bb's copy was cleared.
        rj_path = tick_dir / "resume.json"
        if rj_path.exists():
            try:
                rj = json.loads(rj_path.read_text(encoding="utf-8"))
                bb.runner_resume_path = rj.get("runner_resume_path") or bb.runner_resume_path
                pd = rj.get("pending_dispatch")
                if pd:
                    bb.pending_dispatch = DispatchRequest.from_dict(pd)
            except (OSError, ValueError):
                pass

        _touch_current_heartbeat(run_id)

        root = build_dream_root(
            scheduler_root=_scheduler_root(),
            memory_store_dir=_memory_store_dir(),
        )
        runner = Runner(
            root,
            scheduler_root=_scheduler_root(),
            subdir="dream",
            agent_type_to_leaf=DREAM_AGENT_TYPE_TO_LEAF,
        )
        rr = runner.resume(bb, dispatch_result)
        return _to_dream_result(rr, run_id, bb)
    except Exception as e:
        return DreamResult(
            kind="error",
            error_code="engine_internal",
            error_message=f"{type(e).__name__}: {e}",
        )


def dream_list_runs(limit: int = 10) -> list[DreamRunSummary]:
    """List recent dream runs under `.cbim/scheduler/dream/`."""
    out: list[DreamRunSummary] = []
    root = _dream_root()
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
        fields = raw.get("fields", {}) or {}
        status_raw = raw.get("bb_status") or "running"
        status = _normalize_status(status_raw, d)
        report_path = fields.get("report_path")
        out.append(DreamRunSummary(
            run_id=raw.get("tick_id") or d.name,
            trigger_reason=str(fields.get("trigger_reason") or "?"),
            status=status,
            started_at=str(fields.get("started_at") or raw.get("created_at") or ""),
            finished_at=fields.get("finished_at"),
            step_results=dict(fields.get("step_results") or {}),
            report_path=report_path,
        ))
    out.sort(key=lambda s: s.started_at, reverse=True)
    return out[: max(0, limit)]


def dream_abort(run_id: str, reason: str) -> AbortResult:
    """Mark a RUNNING tick as abandoned. See .dna/contract.md."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    tick_dir = _run_dir(run_id)
    bb_path = tick_dir / "bb.json"
    if not bb_path.exists():
        return AbortResult(aborted=False, run_id=run_id, reason=reason, abandoned_at=now)
    try:
        raw = json.loads(bb_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AbortResult(aborted=False, run_id=run_id, reason=reason, abandoned_at=now)
    if raw.get("bb_status") != "running":
        return AbortResult(aborted=False, run_id=run_id, reason=reason, abandoned_at=now)

    # Write abandoned.json (kept alongside bb.json/trace.jsonl/resume.json).
    abandoned_payload = {
        "run_id": run_id,
        "reason": reason,
        "abandoned_at": now,
    }
    target = tick_dir / "abandoned.json"
    tmp = tick_dir / "abandoned.json.tmp"
    tmp.write_text(json.dumps(abandoned_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)

    # Flip bb_status so list_runs reports "abandoned" and the single-flight gate clears.
    raw["bb_status"] = "abandoned"
    tmp_bb = tick_dir / "bb.json.tmp"
    tmp_bb.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_bb, bb_path)

    # Clear current.json so SessionStart sees no in-flight tick (we do NOT
    # touch last_success.json — abandoned ≠ success).
    current = _dream_root() / "current.json"
    if current.exists():
        try:
            current_raw = json.loads(current.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            current_raw = {}
        if current_raw.get("run_id") == run_id:
            try:
                current.unlink()
            except OSError:
                pass

    return AbortResult(aborted=True, run_id=run_id, reason=reason, abandoned_at=now)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_dream_result(rr, run_id: str, bb: DreamBlackboard) -> DreamResult:
    if rr.kind == "done":
        # Clear current.json (Finalize already tried but the engine's terminal
        # path might bypass it on edge cases).
        _delete_current_if_matches(run_id)
        return DreamResult(
            kind="done",
            summary=bb.summary_for_session or rr.user_message or "",
            report_path=bb.report_path,
        )
    if rr.kind == "yield":
        _touch_current_heartbeat(run_id)
        return DreamResult(
            kind="yield",
            run_id=run_id,
            dispatch_request=rr.dispatch_request,
        )
    return DreamResult(
        kind="error",
        error_code=rr.error_code or "engine_internal",
        error_message=rr.error_message or "",
        report_path=bb.report_path,
    )


def _delete_current_if_matches(run_id: str) -> None:
    p = _dream_root() / "current.json"
    if not p.exists():
        return
    try:
        raw = json.loads(p.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return
    if raw.get("run_id") != run_id:
        return
    try:
        p.unlink()
    except OSError:
        pass


def _normalize_status(bb_status: str, tick_dir: Path) -> str:
    """Project bb_status onto the contract's {running|done|failed|abandoned}."""
    if (tick_dir / "abandoned.json").exists():
        return "abandoned"
    if bb_status == "done":
        return "done"
    if bb_status == "error":
        return "failed"
    if bb_status == "running":
        return "running"
    if bb_status == "abandoned":
        return "abandoned"
    return "running"
