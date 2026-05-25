"""tree/main_loop.py — Global ROOT for the CBIM main loop (v3).

Static topology — auditable in one read. Stacking order locked per
WORKFLOW-EXECUTION §5: Trace > Timeout > {Retry | Catch}.

Forbidden combinations (enforced by L2 tests):
  - Retry around DispatchWork — non-idempotent (dispatches agent calls)

Tree shape (see WORKFLOW-EXECUTION §3):
  Root (Trace > Timeout > Sequence)
    InitTick
    ModeClassify
    ModeBranch
      conversation → DirectReply
      execution    → ExecutionSeq (Sequence)
          RetryDispatchArchitect
          RetryDispatchHR
          DispatchWork
          Respond
          CatchFlush(FlushMemory)
"""

from __future__ import annotations

from typing import Any

from ..actions.direct_reply import DirectReply
from ..actions.dispatch_architect import DispatchArchitect
from ..actions.dispatch_hr import DispatchHR
from ..actions.dispatch_work import DispatchWork
from ..actions.flush_memory import FlushMemory
from ..actions.init_tick import InitTick
from ..actions.llm_hook import NullLLM
from ..actions.mode_classify import ModeClassify
from ..actions.respond import Respond
from ..core.composite import ModeBranch, Sequence
from ..core.decorator import Catch, Retry, Timeout, Trace


def _default_llm() -> Any:
    """Pick the real Anthropic client when ANTHROPIC_API_KEY is set; fall back
    to NullLLM otherwise. Isolated so tests can monkeypatch it cleanly.
    """
    import os

    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return NullLLM()
    try:
        from ..actions.llm_client import AnthropicLLM
        return AnthropicLLM()
    except Exception:
        # SDK missing or client init failed — degrade silently to NullLLM
        # so the engine remains importable and the rule path still works.
        return NullLLM()


def build_root(*, llm: Any = None, global_timeout_s: int = 1800):
    llm = llm if llm is not None else _default_llm()

    init = InitTick(name="InitTick")
    classify = ModeClassify(llm=llm, name="ModeClassify")
    direct = DirectReply(llm=llm, name="DirectReply")

    arch = Retry(DispatchArchitect(name="DispatchArchitect"),
                 n=2, only="idempotent", name="RetryDispatchArchitect")
    hr = Retry(DispatchHR(name="DispatchHR"),
               n=2, only="idempotent", name="RetryDispatchHR")
    work = DispatchWork(name="DispatchWork")
    respond = Respond(name="Respond")
    flush = Catch(FlushMemory(name="FlushMemory"),
                  fallback="swallow", name="CatchFlush")

    execution_seq = Sequence(
        [arch, hr, work, respond, flush],
        name="ExecutionSeq",
    )

    branch = ModeBranch(
        conversation=direct,
        execution=execution_seq,
        name="ModeBranch",
    )

    body = Sequence([init, classify, branch], name="RootSeq")

    return Trace(Timeout(body, seconds=global_timeout_s, name="GlobalTimeout"),
                 name="Root")


ROOT = build_root()
