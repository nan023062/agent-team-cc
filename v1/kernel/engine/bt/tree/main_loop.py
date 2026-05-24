"""tree/main_loop.py — Global ROOT for the CBIM main loop.

Static topology — auditable in one read. Stacking order locked per
WORKFLOW-EXECUTION §3: Trace > Timeout > {Retry | IterationGuard | Catch}.

Forbidden combinations (enforced by L2 test_no_retry_on_decompose_or_dispatch_or_aggregate):
  - Retry around Decompose       — non-idempotent (bumps iteration)
  - Retry around DispatchParallel — non-idempotent (sends agent calls)
  - Retry around Aggregate       — would re-derive the same verdict
"""

from __future__ import annotations

from typing import Any

from ..core.composite import ClarifyBranch, Sequence
from ..core.decorator import Catch, IterationGuard, LoopUntilConverge, Retry, Timeout, Trace
from ..actions.aggregate import Aggregate
from ..actions.arch_gate import ArchGate
from ..actions.ask_clarify import AskClarify
from ..actions.call_hr import CallHR
from ..actions.converge_judge import ConvergeJudge
from ..actions.decompose import Decompose
from ..actions.dispatch_parallel import DispatchParallel
from ..actions.flush_memory import FlushMemory
from ..actions.init_tick import InitTick
from ..actions.intent_analyze import IntentAnalyze, IntentRules, NullLLM
from ..actions.respond import Respond


def build_root(*, llm: Any = None, intent_rules: IntentRules | None = None,
               global_timeout_s: int = 1800):
    llm = llm or NullLLM()
    intent_rules = intent_rules or IntentRules.from_dispatch_skill()

    init = InitTick(name="InitTick")
    intent = Retry(IntentAnalyze(rules=intent_rules, llm=llm, name="IntentAnalyze"),
                   n=2, only="idempotent", name="RetryIntent")
    ask = AskClarify(name="AskClarify")

    decompose = Decompose(llm=llm, name="Decompose")
    arch_gate = Retry(ArchGate(name="ArchGate"), n=2, only="idempotent", name="RetryArchGate")
    call_hr = Retry(CallHR(name="CallHR"), n=2, only="idempotent", name="RetryCallHR")
    dispatch = DispatchParallel(name="DispatchParallel")
    aggregate = Aggregate(name="Aggregate")
    converge = Retry(ConvergeJudge(llm=llm, name="ConvergeJudge"),
                     n=2, only="idempotent", name="RetryConverge")

    loop_seq = IterationGuard(
        Sequence(
            [decompose, arch_gate, call_hr, dispatch, aggregate, converge],
            name="LoopSeq",
        ),
        name="LoopSeqGuard",
    )
    loop = LoopUntilConverge(loop_seq, name="LoopRoot")

    respond = Respond(name="Respond")
    flush = Catch(FlushMemory(name="FlushMemory"), fallback="swallow", name="CatchFlush")

    main_body = Sequence([loop, respond, flush], name="MainBody")

    clarify = ClarifyBranch(yes=ask, no=main_body, name="ClarifyBranch")

    body = Sequence([init, intent, clarify], name="RootSeq")

    return Trace(Timeout(body, seconds=global_timeout_s, name="GlobalTimeout"),
                 name="Root")


ROOT = build_root()
