"""actions/respond.py — render bb.final_response from bb.work_results.

v3 contract: if bb.final_response is already populated (e.g. DirectReply
already wrote one), leave it alone. If bb.interrupt_reason is set, leave
final_response empty so the Runner routes to BtResult.Error. Otherwise
concatenate work_results outputs into a single user-facing message.

PR-C adds two mode variants used by EscalationGate:
  - "need_user"  → render the pending clarifying questions and pause the run.
  - "exhausted"  → render the architect-loop escalation summary and ask
                    the user to step in.
"""

from __future__ import annotations

from engine.core.node import Node, Status


class Respond(Node):
    def __init__(
        self,
        *,
        name: str = "Respond",
        mode: str = "default",
    ) -> None:
        self.name = name
        if mode not in ("default", "need_user", "exhausted"):
            raise ValueError(f"Respond mode must be one of default/need_user/exhausted, got {mode!r}")
        self._mode = mode

    def tick(self, bb) -> Status:
        # Interrupt path: leave final_response empty so the Runner emits
        # BtResult(kind="error", interrupt_reason=...).
        if bb.interrupt_reason:
            return Status.SUCCESS
        if bb.final_response:
            return Status.SUCCESS

        if self._mode == "need_user":
            rendered = self._render_need_user(bb)
            if rendered is not None:
                bb.final_response = rendered
                return Status.SUCCESS
            # Defensive fall-through to default aggregation.
        elif self._mode == "exhausted":
            rendered = self._render_exhausted(bb)
            if rendered is not None:
                bb.final_response = rendered
                return Status.SUCCESS
            # Defensive fall-through to default aggregation.

        # Default — existing aggregation path.
        bb.final_response = self._render_default(bb)
        return Status.SUCCESS

    # ------------------------------------------------------------------
    # Renderers
    # ------------------------------------------------------------------

    @staticmethod
    def _render_default(bb) -> str:
        results = bb.work_results or {}
        if not results:
            return "(empty response)"
        parts: list[str] = []
        order = [t.get("id") for t in (bb.arch_plan or []) if t.get("id") in results]
        if not order:
            order = list(results.keys())
        for tid in order:
            r = results.get(tid) or {}
            out = (r.get("output") or "").strip() if isinstance(r, dict) else ""
            if out:
                parts.append(out)
        return "\n\n---\n\n".join(parts) if parts else "(no output)"

    @staticmethod
    def _render_need_user(bb) -> str | None:
        results = bb.work_results or {}
        order = [t.get("id") for t in (bb.arch_plan or []) if t.get("id") in results]
        if not order:
            order = list(results.keys())
        blocks: list[str] = []
        for tid in order:
            r = results.get(tid) or {}
            if not isinstance(r, dict) or r.get("status") != "needs_user_input":
                continue
            agent = r.get("agent") or "unknown"
            summary = (r.get("summary") or "").strip()
            question = (r.get("question") or "").strip()
            header = f"【任务 {tid} - {agent}】"
            lines = [header]
            if summary:
                lines.append(summary)
            lines.append("")
            lines.append(f"问题：{question}" if question else "问题：(未提供)")
            blocks.append("\n".join(lines))
        if not blocks:
            return None  # Defensive: no entries matched → fall back to default.
        body = "\n\n".join(blocks)
        return (
            "我需要你的确认才能继续：\n\n"
            f"{body}\n\n"
            "请回复你的答案，我会把它传回相应的 agent 继续执行。"
        )

    @staticmethod
    def _render_exhausted(bb) -> str | None:
        # Pull from arch_redo_context (always populated when convergence is
        # exhausted, per ConvergeJudge §4.3).
        from .converge_judge import DEFAULT_MAX_ITERS

        ctx = getattr(bb, "arch_redo_context", None) or {}
        unresolved = ctx.get("unresolved") or []
        if not unresolved:
            return None  # Defensive: fall back to default aggregation.
        max_iters = DEFAULT_MAX_ITERS
        blocks: list[str] = []
        for entry in unresolved:
            tid = entry.get("task_id") or "?"
            agent = entry.get("agent") or "unknown"
            summary = (entry.get("summary") or "").strip()
            question = (entry.get("question") or "").strip()
            blocking = entry.get("blocking_module") or "未指定"
            header = f"【任务 {tid} - {agent}】"
            lines = [header]
            if summary:
                lines.append(summary)
            lines.append("")
            lines.append(f"阻塞模块：{blocking}")
            lines.append(f"架构问题：{question}" if question else "架构问题：(未提供)")
            blocks.append("\n".join(lines))
        body = "\n\n".join(blocks)
        return (
            f"我尝试了 {max_iters} 轮架构师 ↔ 工作 agent 协同，仍未收敛。剩余未解决的问题：\n\n"
            f"{body}\n\n"
            "请你介入决定下一步：\n"
            "  (a) 给架构师补充关键信息后重试\n"
            "  (b) 直接由你回答上述问题\n"
            "  (c) 放弃本次任务"
        )
