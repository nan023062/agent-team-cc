"""actions/dispatch_mem_distill.py — memory-distill governance dispatcher.

Yields a DispatchRequest(agent_type="hr", subtask_id="governance_memory_distill")
on first tick when ``bb.mem_distill_dispatched`` is True (set by MemDistillGate)
and ``bb.mem_distill_result`` is not yet populated. On resume the sibling
CollectMemDistill node owns ``on_resume`` and stores the parsed report on
``bb.mem_distill_result``.

Gate semantics:
  - MemDistillGate already evaluated thresholds upstream. If it set
    ``mem_distill_dispatched=False`` (and pre-populated ``mem_distill_result``
    with the skip reason), this node is a SUCCESS no-op.
  - If ``mem_distill_dispatched=True`` and no result yet → yield.
  - If the result is already on bb (idempotent re-entry after resume) →
    SUCCESS no-op.

Prompt scaffolding is delegated to
``engine.dream.loops.memory_distill_governance`` so the schema embedded in
the prompt is the single source of truth.

Reference pattern: ``dispatch_hr.DispatchHRGovern`` — same agent_type ("hr"),
different subtask_id; (agent_type, subtask_id) two-level routing in the
Runner steers the resume path to CollectMemDistill instead of
CollectHRAdvice.
"""

from __future__ import annotations

from engine.core.node import Node, Status

from ..api.result import DispatchRequest


def _loop():
    # Lazy import to break the import cycle (see dispatch_arch.py).
    import engine.dream.loops.memory_distill_governance as m
    return m


# Default HR agent file path (same agent as governance_capability — subtask_id
# discriminates between the two governance jobs HR handles).
DEFAULT_HR_FILE = ".claude/agents/hr/hr.md"


class DispatchMemDistill(Node):
    def __init__(
        self,
        *,
        store_dir,
        agent_file: str = DEFAULT_HR_FILE,
        timeout_hint_s: int = 600,
        name: str = "DispatchMemDistill",
    ) -> None:
        self.name = name
        from pathlib import Path
        self._store_dir = Path(store_dir)
        self._agent_file = agent_file
        self._timeout_hint_s = timeout_hint_s

    def tick(self, bb) -> Status:
        # Gate decided to skip — Collect already has the skip result.
        if not bb.mem_distill_dispatched:
            return Status.SUCCESS
        # Already collected (post-resume re-entry) — no-op.
        if bb.mem_distill_result is not None:
            return Status.SUCCESS
        bb.pending_dispatch = DispatchRequest(
            agent_type="hr",
            agent_file=self._agent_file,
            prompt=_loop().compose_prompt(bb, str(self._store_dir)),
            subtask_id="governance_memory_distill",
            timeout_hint_s=self._timeout_hint_s,
        )
        return Status.RUNNING
