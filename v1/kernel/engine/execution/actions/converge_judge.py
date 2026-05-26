"""actions/converge_judge.py — aggregate bb.work_results and set bb.convergence.

PR-C decision point 2. Pure code; no LLM, no filesystem, no network.

Reads:
  - bb.work_results (dict[task_id, {status, ...}])  — written by DispatchWork
  - bb.work_loop_iter (int)                          — written by LoopSeq
  - bb.arch_plan (list[dict])                        — for arch_redo_context

Writes:
  - bb.convergence (closed enum: "done" | "arch_redo" | "user_input" | "exhausted")
  - bb.arch_redo_context (dict, only on arch_redo / exhausted paths)
  - bb.work_results (purged of needs_arch_decision entries on arch_redo path)
  - bb.trace (event entries for arch_redo_stashed / work_results_purged)

Return contract:
  - SUCCESS — exit the LoopSeq (convergence in {"done", "user_input",
              "exhausted"})
  - FAILURE — re-loop (convergence == "arch_redo"); LoopSeq is expected
              to catch this and bump bb.work_loop_iter
"""

from __future__ import annotations

from engine.core._trace_utils import _append_trace_event, _now_iso_ms
from engine.core.node import Node, Status


DEFAULT_MAX_ITERS = 3


class ConvergeJudge(Node):
    """Aggregate bb.work_results into bb.convergence with bounded retry."""

    def __init__(
        self,
        *,
        max_iters: int = DEFAULT_MAX_ITERS,
        name: str = "ConvergeJudge",
    ) -> None:
        self.name = name
        self._max_iters = max_iters

    def tick(self, bb) -> Status:
        try:
            return self._tick_impl(bb)
        except Exception as e:  # noqa: BLE001 — defensive blanket per §4.6
            # Defensive: never break the loop. Force "done" so EscalationGate
            # renders whatever we have, and log for post-mortem.
            try:
                bb.convergence = "done"
            except Exception:
                pass
            _append_trace_event(bb, {
                "event": "converge_internal_error",
                "node": self.name,
                "error": f"{type(e).__name__}: {e}",
                "ts": _now_iso_ms(),
            })
            return Status.SUCCESS

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _tick_impl(self, bb) -> Status:
        results = bb.work_results or {}
        iter_no = int(getattr(bb, "work_loop_iter", 1) or 1)

        needs_user = any(
            self._status(r) == "needs_user_input" for r in results.values()
        )
        needs_arch = any(
            self._status(r) == "needs_arch_decision" for r in results.values()
        )

        # Priority order (top wins) — see §4.3.
        if needs_user:
            bb.convergence = "user_input"
            return Status.SUCCESS

        if needs_arch:
            if iter_no < self._max_iters:
                bb.convergence = "arch_redo"
                self._stash_redo_context(bb, iter_no)
                self._purge_arch_decision_entries(bb)
                return Status.FAILURE
            # Exhausted — still surface the unresolved escalations.
            bb.convergence = "exhausted"
            self._stash_redo_context(bb, iter_no)
            return Status.SUCCESS

        # Terminal: all ok / failed / empty.
        bb.convergence = "done"
        return Status.SUCCESS

    @staticmethod
    def _status(entry) -> str:
        if not isinstance(entry, dict):
            return "failed"
        s = entry.get("status")
        if s in ("ok", "failed", "needs_arch_decision", "needs_user_input"):
            return s
        # Defensive: malformed trailer → treat as failed (parser already
        # collapses malformed receipts to failed; this is belt-and-braces).
        return "failed"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _stash_redo_context(self, bb, iter_no: int) -> None:
        unresolved = []
        for tid, r in (bb.work_results or {}).items():
            if not isinstance(r, dict):
                continue
            if r.get("status") != "needs_arch_decision":
                continue
            unresolved.append({
                "task_id": tid,
                "blocking_module": r.get("blocking_module"),
                "question": r.get("question") or "",
                "agent": r.get("agent") or "unknown",
                "summary": r.get("summary") or "",
            })
        bb.arch_redo_context = {
            "iter": iter_no,
            "unresolved": unresolved,
            "previous_plan": list(bb.arch_plan or []),
        }
        _append_trace_event(bb, {
            "event": "arch_redo_stashed",
            "node": self.name,
            "iter": iter_no,
            "unresolved_count": len(unresolved),
            "ts": _now_iso_ms(),
        })

    def _purge_arch_decision_entries(self, bb) -> None:
        results = dict(bb.work_results or {})
        purged = [
            tid for tid, r in results.items()
            if isinstance(r, dict) and r.get("status") == "needs_arch_decision"
        ]
        for tid in purged:
            del results[tid]
        bb.work_results = results
        _append_trace_event(bb, {
            "event": "work_results_purged",
            "node": self.name,
            "task_ids": purged,
            "ts": _now_iso_ms(),
        })


__all__ = ["ConvergeJudge", "DEFAULT_MAX_ITERS"]
