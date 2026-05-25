"""actions/collect_mem_distill.py — post-yield collector for memory-distill report.

Owns ``on_resume`` for the memory-distill dispatch path. The Runner's
two-level (agent_type, subtask_id) routing table lands the
``("hr", "governance_memory_distill")`` resume here (see
``api/result.DREAM_AGENT_SUBTASK_TO_LEAF``).

On resume:
  1. Parse the HR payload through ``loops.memory_distill_governance.parse_response``.
  2. Validate the report structure (must carry ``mem_distill_report`` or
     ``error``; every ``medium_written`` / ``medium_updated`` path must exist
     on disk under store_dir).
  3. On success: touch ``.last_distill`` marker and store the parsed report
     on ``bb.mem_distill_result``.

Tick semantics (mirror of CollectArchAdvice / CollectHRAdvice three-branch):
  - Result already on bb → SUCCESS.
  - Gate decided to skip (``mem_distill_dispatched=False``) → SUCCESS no-op.
  - Dispatched but no result on bb → FAILURE with placeholder error.

Pairs with ``actions/dispatch_mem_distill.DispatchMemDistill`` inside the
MemoryGovernanceStep sequence.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from engine.core.node import Node, Status


def _loop():
    import engine.dream.loops.memory_distill_governance as m
    return m


class CollectMemDistill(Node):
    def __init__(self, *, store_dir, name: str = "CollectMemDistill") -> None:
        self.name = name
        self._store_dir = Path(store_dir)

    def tick(self, bb) -> Status:
        if bb.mem_distill_result is not None:
            return Status.SUCCESS
        if not bb.mem_distill_dispatched:
            # Gate already wrote the skip result; this branch is for safety
            # only — Gate normally pre-populates mem_distill_result.
            bb.mem_distill_result = {"skipped": True, "reason": "gate_skipped"}
            return Status.SUCCESS
        # Dispatched but on_resume never delivered — surface as FAILURE with
        # placeholder so EmitReport still has a render target.
        bb.mem_distill_result = {
            "error": "no_payload_received",
            "skipped": False,
        }
        return Status.FAILURE

    def on_resume(self, bb, payload: Any) -> None:
        parsed = _loop().parse_response(_extract_text(payload))

        # Branch 1: parse-time error — record sentinel, no marker touch.
        if parsed.get("error") and parsed.get("mem_distill_report") is None:
            bb.mem_distill_result = {
                "error": parsed["error"],
                "skipped": False,
            }
            bb.pending_dispatch = None
            return

        report = parsed.get("mem_distill_report")
        if not isinstance(report, dict):
            bb.mem_distill_result = {
                "error": "report_not_a_dict",
                "skipped": False,
            }
            bb.pending_dispatch = None
            return

        # Branch 2: validate medium_written / medium_updated paths exist.
        missing = _missing_paths(report, self._store_dir)
        if missing:
            bb.mem_distill_result = {
                "error": "missing_medium_files",
                "missing": missing,
                "report": report,
                "skipped": False,
            }
            bb.pending_dispatch = None
            return

        # Branch 3: success — touch marker, store report.
        try:
            marker = self._store_dir / ".last_distill"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n",
                encoding="utf-8",
            )
        except OSError:
            # Marker write failure is non-fatal — distill itself succeeded.
            # Next tick's Gate will see no marker and re-fire prematurely,
            # which is annoying but not corrupting.
            pass

        bb.mem_distill_result = report
        bb.pending_dispatch = None


def _missing_paths(report: dict, store_dir: Path) -> list[str]:
    """Return any medium_written / medium_updated paths that don't exist on disk.

    Paths in the report are stored relative to ``store_dir`` per the prompt
    contract; we resolve both ways (absolute + store-relative) so a lax
    agent that emits absolute paths is still accepted.
    """
    missing: list[str] = []
    for bucket in ("medium_written", "medium_updated"):
        for entry in report.get(bucket) or []:
            if not isinstance(entry, dict):
                continue
            rel = entry.get("path")
            if not rel:
                continue
            candidate = Path(rel)
            if not candidate.is_absolute():
                candidate = store_dir / rel
            if not candidate.exists():
                missing.append(str(candidate))
    return missing


def _extract_text(payload: Any) -> Any:
    """Mirror the Task-tool unwrap from collect_arch_advice / collect_hr_advice."""
    if isinstance(payload, dict) and "output" in payload:
        return payload.get("output") or ""
    return payload
