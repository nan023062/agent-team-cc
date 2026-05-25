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
          ArchitectExecution (BT subtree)
          DispatchWork
          Respond
          CatchFlush(FlushMemory)
      default      → ExecutionSeq (mirror — defensive fallback)

The three core-agent branches each produce exactly one yield with a
distinct ``agent_type`` (``architect`` / ``hr`` / ``auditor``); the main
agent dispatches to the fixed ``.claude/agents/*.md`` paths held by
``actions/core_agents.CORE_AGENT_FILES``.
"""

from __future__ import annotations

from typing import Any

from ..actions.arch_exec import build_architect_execution_subtree
from ..actions.direct_reply import DirectReply
from ..actions.dispatch_core_agent import DispatchCoreAgent
from ..actions.dispatch_work import DispatchWork
from ..actions.flush_memory import FlushMemory
from ..actions.init_tick import InitTick
from ..actions.llm_hook import NullLLM
from ..actions.mode_classify import ModeClassify
from ..actions.respond import Respond
from engine.core.composite import Sequence, SwitchBranch
from engine.core.decorator import Catch, Timeout, Trace


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


def _mode_key(bb) -> str:
    return bb.mode or "execution"


def build_root(*, llm: Any = None, global_timeout_s: int = 1800):
    llm = llm if llm is not None else _default_llm()

    init = InitTick(name="InitTick")
    classify = ModeClassify(llm=llm, name="ModeClassify")

    # Conversation branch.
    direct = DirectReply(llm=llm, name="DirectReply")

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

    # Execution branch — the Architect → Work pipeline (v3.6: hr_exec removed).
    arch_exec = build_architect_execution_subtree(llm)
    work = DispatchWork(name="DispatchWork")
    respond = Respond(name="Respond")
    flush = Catch(FlushMemory(name="FlushMemory"),
                  fallback="swallow", name="CatchFlush")

    execution_seq = Sequence(
        [arch_exec, work, respond, flush],
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
