"""actions/converge_judge.py — five-rule terminator for the main loop.

Reads bb.subtask_results / bb.interrupt_reason / bb.iteration / iteration_cap
and writes bb.converge_signal ∈ {"done", "loop", "interrupt"}.

The five rules (priority order):
  1. interrupt_reason already set → "interrupt"
  2. any subtask flagged needs_arch_decision → "loop" (re-enter ArchGate)
  3. any non-retryable fatal error → "interrupt"
  4. all subtasks "ok" and no new subtask implied by output → "done"
  5. otherwise → "loop"

When LLM is wired, rule 4's "new subtask implied" check can call
llm.judge_converge for semantic detection; default heuristic: SUCCESS.

ALWAYS returns SUCCESS — the converge_signal is what matters, not the
return value. Retry is safe (idempotent on stable bb).
"""

from __future__ import annotations

from typing import Any

from ..core.node import Node, Status


class ConvergeJudge(Node):
    def __init__(self, *, llm: Any = None, name: str = "ConvergeJudge") -> None:
        self.name = name
        self._llm = llm

    def tick(self, bb) -> Status:
        results = bb.subtask_results or {}

        # Rule 1
        if bb.interrupt_reason:
            bb.converge_signal = "interrupt"
            return Status.SUCCESS

        # Rule 2
        if any(r.get("needs_arch_decision") for r in results.values()):
            # Clear arch_context so ArchGate yields again on the next iteration.
            bb.arch_context = None
            bb.converge_signal = "loop"
            return Status.SUCCESS

        # Rule 3
        fatal = [
            r for r in results.values()
            if r.get("status") == "error" and not r.get("retryable")
        ]
        if fatal:
            first = fatal[0]
            bb.interrupt_reason = (
                f"fatal_subtask_error: {(first.get('output') or '')[:200]}"
            )
            bb.converge_signal = "interrupt"
            return Status.SUCCESS

        # Rule 4
        if results and all(r.get("status") == "ok" for r in results.values()):
            if not self._new_subtasks_implied(bb):
                # Compose final_response from subtask outputs.
                bb.final_response = self._compose_final(results)
                bb.converge_signal = "done"
                return Status.SUCCESS

        # Rule 5
        bb.converge_signal = "loop"
        return Status.SUCCESS

    def _new_subtasks_implied(self, bb) -> bool:
        # 4B baseline: no LLM judge — heuristic returns False (assume converged).
        # Tests can subclass to flip behavior.
        if self._llm is None:
            return False
        try:
            payload = self._llm.judge_converge({
                "user_request": bb.user_request,
                "subtask_results": bb.subtask_results,
                "iteration": bb.iteration,
            })
            return bool(payload.get("new_subtasks_implied"))
        except NotImplementedError:
            return False

    @staticmethod
    def _compose_final(results: dict) -> str:
        parts: list[str] = []
        for sid, r in results.items():
            out = (r.get("output") or "").strip() if isinstance(r, dict) else ""
            if out:
                parts.append(out)
        return "\n\n---\n\n".join(parts) if parts else "(no output)"
