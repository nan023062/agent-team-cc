"""actions/aggregate.py — detect conflicts / no-progress across subtask_results.

Pure read of bb.subtask_results + bb.iteration; writes bb.interrupt_reason
on detected conflict / stalled progress. Returns FAILURE on detection so
LoopUntilConverge will see the interrupt and terminate.

NEVER wrap in @Retry — re-running it would just produce the same conclusion.
"""

from __future__ import annotations

from ..core.node import Node, Status


class Aggregate(Node):
    def __init__(self, *, name: str = "Aggregate") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        results = bb.subtask_results or {}

        # Conflict detection: two subtasks of kind "execution" whose output
        # contains contradictory verdicts (CONFLICT: marker). v2 baseline —
        # the LLM-judge variant can replace this later.
        conflicts = self._detect_conflicts(results)
        if conflicts:
            bb.interrupt_reason = f"conflict: {conflicts}"
            return Status.FAILURE

        # No-progress check: iteration > 1, no new subtask results since
        # last iteration. We approximate by counting "ok" results — if
        # the count did not grow, treat as stalled.
        if (bb.iteration or 0) > 1 and self._no_progress(bb):
            bb.interrupt_reason = "no_progress_between_iterations"
            return Status.FAILURE

        return Status.SUCCESS

    @staticmethod
    def _detect_conflicts(results: dict) -> str:
        verdicts: dict[str, str] = {}
        for sid, r in results.items():
            out = (r.get("output") or "") if isinstance(r, dict) else ""
            for line in out.splitlines():
                if line.startswith("CONFLICT:"):
                    verdicts[sid] = line.strip()
        if len(verdicts) >= 2:
            return "; ".join(f"{k}={v}" for k, v in verdicts.items())
        return ""

    @staticmethod
    def _no_progress(bb) -> bool:
        results = bb.subtask_results or {}
        # If every result is "needs_arch" the loop will escalate via
        # ConvergeJudge; that is progress, not stall.
        if any(r.get("needs_arch_decision") for r in results.values()):
            return False
        # No-progress when no "ok" results in current results dict.
        ok_count = sum(1 for r in results.values() if r.get("status") == "ok")
        return ok_count == 0
