"""tree/main_loop.py — Global ROOT for the CBIM main loop (v3.5).

Static topology — auditable in one read. Stacking order locked per
WORKFLOW-EXECUTION §5: Trace > Timeout > {Retry | Catch}.

Tree shape (see module.md §"5 分支模式拓扑"):
  Root (Trace > Timeout > RootSeq)
    InitTick
    ModeClassify
    ModeSwitch (SwitchBranch on bb.mode)
      conversation → DirectReply
      architect    → ArchitectBranch (Sequence)
          DispatchCoreAgent#architect
          Respond#architect
      hr           → HrBranch (Sequence)
          DispatchCoreAgent#hr
          Respond#hr
      audit        → AuditBranch (Sequence)
          DispatchCoreAgent#auditor
          Respond#audit
      execution    → ExecutionSeq (Sequence)
          WorkLoop (LoopSeq, max_iters=3)
            ArchExecYield        (PR-D: single yield to the architect
                                  agent; replaces the in-process
                                  nine-leaf arch_exec subtree)
            DispatchWork
            ConvergeJudge        (PR-C: aggregates bb.work_results →
                                  bb.convergence ∈ {done | arch_redo |
                                  user_input | exhausted})
          EscalationGate (SwitchBranch on bb.convergence)
            "done"       → Respond
            "user_input" → Respond#need_user
            "exhausted"  → Respond#exhausted
          CatchFlush(FlushMemory)
      default      → ExecutionSeq (mirror — defensive fallback)

The three core-agent branches each produce exactly one yield with a
distinct ``agent_type`` (``architect`` / ``hr`` / ``auditor``); the main
agent dispatches to the fixed ``.claude/agents/*.md`` paths held by
``actions/core_agents.CORE_AGENT_FILES``.

PR-D: the kernel no longer holds any LLM client. ModeClassify is rule-
only (rule miss → "execution"); DirectReply is a deterministic
passthrough; ArchExecYield dispatches the architect agent and parses
its receipt trailer. All LLM-driven decisions live in
``.claude/agents/*.md`` personas, reached only via Task-tool dispatch.
"""

from __future__ import annotations

from ..actions.arch_exec_yield import ArchExecYield
from ..actions.converge_judge import DEFAULT_MAX_ITERS, ConvergeJudge
from ..actions.direct_reply import DirectReply
from ..actions.dispatch_core_agent import DispatchCoreAgent
from ..actions.dispatch_work import DispatchWork
from ..actions.flush_memory import FlushMemory
from ..actions.init_tick import InitTick
from ..actions.mode_classify import ModeClassify
from ..actions.respond import Respond
from engine.core.composite import LoopSeq, Sequence, SwitchBranch
from engine.core.decorator import Catch, Timeout, Trace


def _mode_key(bb) -> str:
    return bb.mode or "execution"


def _converge_key(bb) -> str:
    val = getattr(bb, "convergence", None) or "done"
    # arch_redo should not reach EscalationGate (LoopSeq re-enters on it),
    # but be defensive — treat it as done so we render whatever we have.
    if val in ("done", "user_input", "exhausted"):
        return val
    return "done"


def build_root(*, global_timeout_s: int = 1800):
    init = InitTick(name="InitTick")
    classify = ModeClassify(name="ModeClassify")

    # Conversation branch.
    direct = DirectReply(name="DirectReply")

    # Three core-agent branches — peer to Work Agent (see module.md
    # §"三大核心 agent 平级直派"). Each branch yields once via
    # DispatchCoreAgent and then runs Respond so the core agent's reply
    # surfaces as bb.final_response (mirrors what ExecutionSeq does for
    # the work pipeline). Respond reads bb.work_results, which
    # DispatchCoreAgent populated under key f"core:{agent_type}".
    architect_branch = Sequence(
        [
            DispatchCoreAgent(agent_type="architect",
                              name="DispatchCoreAgent#architect"),
            Respond(name="Respond#architect"),
        ],
        name="ArchitectBranch",
    )
    hr_branch = Sequence(
        [
            DispatchCoreAgent(agent_type="hr",
                              name="DispatchCoreAgent#hr"),
            Respond(name="Respond#hr"),
        ],
        name="HrBranch",
    )
    audit_branch = Sequence(
        [
            DispatchCoreAgent(agent_type="auditor",
                              name="DispatchCoreAgent#auditor"),
            Respond(name="Respond#audit"),
        ],
        name="AuditBranch",
    )

    # Execution branch — the Architect → Work pipeline with bounded
    # loop-back (PR-C). ArchExecYield sits as the first child of
    # WorkLoop so each retry re-runs the architect dispatch too;
    # ConvergeJudge is the last child and writes bb.convergence, which
    # EscalationGate then routes on. ArchExecYield is a single-yield
    # leaf — the architect agent does all the decomposition work
    # outside the kernel and returns arch_plan in its receipt trailer.
    arch_exec_yield = ArchExecYield(name="ArchExecYield")
    dispatch_work = DispatchWork(name="DispatchWork")
    converge_judge = ConvergeJudge(max_iters=DEFAULT_MAX_ITERS,
                                   name="ConvergeJudge")
    work_loop = LoopSeq(
        [arch_exec_yield, dispatch_work, converge_judge],
        max_iters=DEFAULT_MAX_ITERS,
        name="WorkLoop",
    )

    respond = Respond(name="Respond")
    respond_need_user = Respond(name="Respond#need_user", mode="need_user")
    respond_exhausted = Respond(name="Respond#exhausted", mode="exhausted")

    escalation_gate = SwitchBranch(
        key_fn=_converge_key,
        cases={
            "done":       respond,
            "user_input": respond_need_user,
            "exhausted":  respond_exhausted,
        },
        default=respond,
        name="EscalationGate",
    )

    flush = Catch(FlushMemory(name="FlushMemory"),
                  fallback="swallow", name="CatchFlush")

    execution_seq = Sequence(
        [work_loop, escalation_gate, flush],
        name="ExecutionSeq",
    )

    mode_switch = SwitchBranch(
        key_fn=_mode_key,
        cases={
            "conversation": direct,
            "architect":    architect_branch,
            "hr":           hr_branch,
            "audit":        audit_branch,
            "execution":    execution_seq,
        },
        default=execution_seq,
        name="ModeSwitch",
    )

    body = Sequence([init, classify, mode_switch], name="RootSeq")

    return Trace(Timeout(body, seconds=global_timeout_s, name="GlobalTimeout"),
                 name="Root")


ROOT = build_root()
