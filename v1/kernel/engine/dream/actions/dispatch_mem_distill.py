"""actions/dispatch_mem_distill.py — memory-distill governance dispatcher.

Yields a DispatchRequest(agent_type="main", subtask_id="governance_memory_distill")
on first tick when ``bb.mem_distill_dispatched`` is True (set by MemDistillGate)
and ``bb.mem_distill_result`` is not yet populated. On resume the sibling
CollectMemDistill node owns ``on_resume`` and stores the parsed report on
``bb.mem_distill_result``.

Why ``agent_type="main"`` (not "hr"):
  - Distillation is a memory-source responsibility — the ``memory_distill``
    skill itself documents "Main agent only".
  - The HR agent's MCP tool surface lacks ``memory_get``, so it cannot
    read short-term entry bodies (prior run f1328bf4eb53 surfaced this
    exact failure: HR collected metadata but couldn't ingest the content).
  - The coordinator already has the full memory toolbelt and the prompt
    embeds the schema; main-agent execution is the canonical path.

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

Routing: the Runner reads (agent_type="main", subtask_id="governance_memory_distill")
from ``DREAM_AGENT_SUBTASK_TO_LEAF`` and resumes on ``CollectMemDistill``.
"""

from __future__ import annotations

from engine.core.node import Node, Status

from ..api.result import DispatchRequest


def _loop():
    # Lazy import to break the import cycle (see dispatch_arch.py).
    import engine.dream.loops.memory_distill_governance as m
    return m


class DispatchMemDistill(Node):
    def __init__(
        self,
        *,
        store_dir,
        timeout_hint_s: int = 600,
        name: str = "DispatchMemDistill",
    ) -> None:
        self.name = name
        from pathlib import Path
        self._store_dir = Path(store_dir)
        self._timeout_hint_s = timeout_hint_s

    def tick(self, bb) -> Status:
        # Gate decided to skip — Collect already has the skip result.
        if not bb.mem_distill_dispatched:
            return Status.SUCCESS
        # Already collected (post-resume re-entry) — no-op.
        if bb.mem_distill_result is not None:
            return Status.SUCCESS
        bb.pending_dispatch = DispatchRequest(
            agent_type="main",
            agent_file=None,
            prompt=_loop().compose_prompt(bb, str(self._store_dir)),
            subtask_id="governance_memory_distill",
            timeout_hint_s=self._timeout_hint_s,
        )
        return Status.RUNNING
