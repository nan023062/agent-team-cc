"""actions/arch_exec_yield.py — single-yield leaf that dispatches the
architect agent and parses ``arch_plan`` out of the receipt trailer.

Replaces the nine-leaf in-process ``arch_exec`` subtree (PR-D). The
architect persona at ``.claude/agents/architect/architect.md`` carries
the procedural knowledge for execution-mode decomposition; this leaf is
the kernel's single touchpoint to that persona.

Cross-tick state rule: nothing on ``self`` survives a tick. The leaf
inspects ``bb.arch_plan`` on each tick to decide whether to yield again
or short-circuit. Receipt parsing happens in ``on_resume``; the very
next tick reads the result off bb.

Result-key scheme: ``subtask_id = f"arch:{iter}"`` where ``iter`` is
``bb.work_loop_iter`` (PR-C field). The Runner's two-level
``agent_subtask_to_leaf`` map (wired in api/bt_tick.py) routes
``("architect", "arch:<n>") → "ArchExecYield"`` so the resume path
resolves correctly even though both this leaf and
``DispatchCoreAgent#architect`` dispatch ``agent_type="architect"``.
"""

from __future__ import annotations

import json
from typing import Any

from engine.core.node import Node, Status

from .core_agents import CORE_AGENT_FILES
from .receipt import parse_trailer
from ..api.result import DispatchRequest


ARCHITECT_AGENT_FILE = CORE_AGENT_FILES["architect"]

# Cap mirrors arch_exec/assemble.py historical behavior.
_MAX_TASKS = 8

# Capabilities the architect may name on a task. Anything else is
# silently collapsed to "generalist" so HR's CoreAgentSelector can route.
_KNOWN_CAPABILITIES: frozenset[str] = frozenset(
    {"programmer", "tester", "doc_writer", "generalist"}
)


class ArchExecYield(Node):
    """First child of WorkLoop — yields once to the architect agent.

    First tick (no result on bb yet):
        Sets ``bb.pending_dispatch`` to a DispatchRequest targeting the
        architect; returns RUNNING.

    on_resume(payload):
        Parses ``payload`` through ``parse_trailer``; pulls
        ``arch_plan`` from ``trailer.extras``; validates and writes
        ``bb.arch_plan``. On ``status="needs_user_input"`` also seeds
        ``bb.convergence="user_input"`` so EscalationGate skips
        ConvergeJudge's verdict.

    Re-tick after resume:
        SUCCESS when ``bb.arch_plan`` is a (possibly empty) list.
        FAILURE when the receipt was malformed / missing the field.
        On ``status="failed"`` the leaf also returns FAILURE.
    """

    name: str = "ArchExecYield"

    def __init__(self, *, name: str = "ArchExecYield") -> None:
        self.name = name

    # ------------------------------------------------------------------
    # Tick / resume
    # ------------------------------------------------------------------

    def tick(self, bb) -> Status:
        # Short-circuit when a previous tick (same iter) already produced
        # a plan. WorkLoop re-enters this leaf on arch_redo, in which
        # case the redo path clears bb.arch_plan upstream so we yield
        # afresh.
        plan = getattr(bb, "arch_plan", None)
        if plan is not None:
            # Defensive: invalid shape → FAILURE so the loop bubbles.
            if not isinstance(plan, list):
                return Status.FAILURE
            return Status.SUCCESS

        # First call (or post-redo with cleared plan) — yield.
        subtask_id = self._subtask_id(bb)
        bb.pending_dispatch = DispatchRequest(
            agent_type="architect",
            agent_file=ARCHITECT_AGENT_FILE,
            prompt=self._compose_prompt(bb),
            subtask_id=subtask_id,
            timeout_hint_s=None,
        )
        return Status.RUNNING

    def on_resume(self, bb, payload: Any) -> None:
        text = _payload_to_text(payload)
        subtask_id = self._subtask_id(bb)
        trailer = parse_trailer(text, dispatch_task_id=subtask_id)

        bb.pending_dispatch = None

        status = trailer.status
        if status == "failed":
            bb.arch_plan = []
            return

        if status == "needs_user_input":
            # Architect determined human input is required — skip the
            # ConvergeJudge verdict entirely and route straight to
            # EscalationGate's user_input branch. Empty plan signals
            # DispatchWork to no-op.
            bb.arch_plan = []
            bb.convergence = "user_input"
            # Surface the question so the need_user Respond can render it.
            new_results = dict(bb.work_results or {})
            new_results[subtask_id] = {
                "status": "needs_user_input",
                "summary": trailer.summary,
                "question": trailer.question or "",
                "agent": trailer.agent,
                "output": text,
            }
            bb.work_results = new_results
            return

        if status == "needs_arch_decision":
            # Not legal for the architect itself — coerce to failed.
            bb.arch_plan = []
            return

        # status == "ok" — pull arch_plan from extras.
        raw = trailer.extras.get("arch_plan")
        plan = _parse_plan(raw)
        if plan is None:
            # Malformed plan JSON → treat as failed.
            bb.arch_plan = []
            return

        bb.arch_plan = plan

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _subtask_id(bb) -> str:
        iter_no = int(getattr(bb, "work_loop_iter", 1) or 1)
        return f"arch:{iter_no}"

    @staticmethod
    def _compose_prompt(bb) -> str:
        user_request = (getattr(bb, "user_request", "") or "").strip()
        snapshot = getattr(bb, "knowledge_snapshot", None) or ""
        if not snapshot:
            snapshot = "(无快照 — 自行调用 dna_list / dna_show 查询)"
        redo_context = getattr(bb, "arch_redo_context", None)
        if redo_context:
            redo_block = json.dumps(redo_context, ensure_ascii=False, indent=2)
        else:
            redo_block = "(首次进入)"
        return (
            "## 执行模式 · ArchExec\n\n"
            "### 用户请求\n"
            f"{user_request}\n\n"
            "### 知识快照\n"
            f"{snapshot}\n\n"
            "### 重入上下文\n"
            f"{redo_block}\n\n"
            "### 任务\n"
            "扫描受影响模块、判断知识/代码同步状态、必要时通过 MCP 写入 .dna/，\n"
            "最终产出 arch_plan（list[dict]）作为给 Work Agent 的 ContextPack 来源。\n\n"
            "每条 task 字段：\n"
            "  id (str, 唯一)\n"
            "  description (str)\n"
            "  required_capability (str, ∈ {programmer, tester, doc_writer, generalist})\n"
            "  params (dict)\n"
            "  arch_context (str, 非空)\n\n"
            "约束：\n"
            f"  - task 总数 ≤ {_MAX_TASKS}\n"
            "  - 依赖关系写入 params.depends_on (list[str])，不能成环\n"
            "  - 不可执行 → arch_plan 留空 list，receipt status=needs_user_input + question\n\n"
            "### 回执格式\n"
            "按 PR-A 回执 trailer 规范，并在 trailer 中追加一行：\n"
            "  arch_plan: <JSON-encoded list[dict]>\n"
        )


# ---------------------------------------------------------------------------
# Module-private helpers
# ---------------------------------------------------------------------------

def _payload_to_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return payload.get("output", "") or ""
    if payload is None:
        return ""
    return str(payload)


def _parse_plan(raw: Any) -> list[dict] | None:
    """Parse and validate the architect's arch_plan trailer field.

    Returns the normalized list on success, None on any structural
    failure. An empty list is a valid result (architect said "no work
    needed") and is returned as ``[]``.
    """
    if raw is None:
        # No arch_plan field at all — treat as empty plan (status=ok
        # with no work). Architect explicitly said no work needed.
        return []
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return []
    try:
        loaded = json.loads(s)
    except (ValueError, TypeError):
        return None
    if not isinstance(loaded, list):
        return None
    if len(loaded) > _MAX_TASKS:
        # Cap-violation is a hard fail per spec — architect was told
        # ≤ 8 tasks; emitting more means it didn't follow the contract.
        return None

    out: list[dict] = []
    for item in loaded:
        if not isinstance(item, dict):
            return None
        task_id = item.get("id")
        description = item.get("description")
        arch_context = item.get("arch_context")
        if not isinstance(task_id, str) or not task_id:
            return None
        if not isinstance(description, str):
            return None
        if not isinstance(arch_context, str) or not arch_context:
            return None
        capability = item.get("required_capability") or "generalist"
        if not isinstance(capability, str):
            capability = "generalist"
        if capability not in _KNOWN_CAPABILITIES:
            capability = "generalist"
        params = item.get("params") or {}
        if not isinstance(params, dict):
            return None
        out.append({
            "id": task_id,
            "description": description,
            "required_capability": capability,
            "params": params,
            "arch_context": arch_context,
        })
    return out


__all__ = ["ArchExecYield", "ARCHITECT_AGENT_FILE"]
