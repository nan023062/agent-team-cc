"""actions/dispatch_hr.py — yield to HR, assign agent_file to every Task.

First tick (when any Task in bb.arch_plan lacks an agent_file): emits a
DispatchRequest for HR and returns RUNNING. on_resume parses HR's
assignment list into bb.agent_assignments and merges agent_file back into
the corresponding Task dicts in bb.arch_plan.

Prompt scaffolding and JSON-response normalization are delegated to
`engine.execution.loops.hr_execution` — the design flowchart NodeSpec
list is the single source of truth. This action only owns:
  - the yield gesture (DispatchRequest)
  - the agent_gap short-circuit
  - the merge of agent_file back into arch_plan

Reply parsing falls back to the legacy line-format path
(``task_id=... agent_file=... capability=...``) so existing agent replies
keep working unchanged.
"""

from __future__ import annotations

from ..api.result import DispatchRequest
from engine.core.node import Node, Status


def _loop():
    # Lazy import to break the import cycle (see dispatch_architect.py).
    import engine.execution.loops.hr_execution as m
    return m


_HR_AGENT_FILE = ".claude/agents/hr/hr.md"


class DispatchHR(Node):
    def __init__(self, *, name: str = "DispatchHR") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        if bb.interrupt_reason and "agent_gap" in bb.interrupt_reason:
            return Status.FAILURE
        plan = bb.arch_plan or []
        if not plan:
            # No tasks → nothing to assign; Architect already short-circuited.
            return Status.SUCCESS
        missing = [t for t in plan if not t.get("agent_file")]
        if not missing:
            return Status.SUCCESS
        bb.pending_dispatch = DispatchRequest(
            agent_type="hr",
            agent_file=_HR_AGENT_FILE,
            prompt=_loop().compose_prompt(bb),
            subtask_id=None,
        )
        return Status.RUNNING

    def on_resume(self, bb, payload) -> None:
        text = _payload_text(payload)
        if "agent_gap:" in text:
            tail = text.split("agent_gap:", 1)[1].strip().splitlines()[0]
            bb.interrupt_reason = f"agent_gap: {tail}"
            bb.pending_dispatch = None
            return
        assignments = self._extract_assignments(payload, text)
        if not assignments:
            bb.interrupt_reason = "agent_gap: hr returned empty assignment"
            bb.pending_dispatch = None
            return
        bb.agent_assignments = assignments
        # Merge agent_file back into the matching Task entries.
        by_id = {a["task_id"]: a for a in assignments}
        new_plan = []
        for t in bb.arch_plan or []:
            t2 = dict(t)
            assigned = by_id.get(t2.get("id"))
            if assigned and not t2.get("agent_file"):
                t2["agent_file"] = assigned.get("agent_file")
            new_plan.append(t2)
        bb.arch_plan = new_plan
        bb.pending_dispatch = None

    # --------------------------------------------------------------
    # Internals
    # --------------------------------------------------------------

    @staticmethod
    def _extract_assignments(payload, text: str) -> list[dict]:
        """Coerce HR's reply into the canonical assignment list.

        Strategy:
          1. Run `loop.parse_response(payload)` — it handles dict / JSON
             string / list shapes carrying agent_assignments. If a usable
             list comes back, normalize each entry to the expected keys.
          2. Otherwise fall back to legacy line-format parsing so existing
             text-based replies (``task_id=... agent_file=...``) work.
        """
        normalized = _loop().parse_response(payload)
        raw_assigns = normalized.get("agent_assignments")
        if isinstance(raw_assigns, list):
            out: list[dict] = []
            for a in raw_assigns:
                if not isinstance(a, dict):
                    continue
                tid = a.get("task_id") or a.get("subtask_id") or a.get("id")
                agent_file = a.get("agent_file")
                if tid and agent_file:
                    out.append({
                        "task_id": tid,
                        "agent_file": agent_file,
                        "capability": a.get("capability", ""),
                    })
            if out:
                return out

        # Legacy line-format fallback.
        out2: list[dict] = []
        for line in (text or "").splitlines():
            line = line.strip()
            # Accept both `task_id=` (v3) and legacy `subtask_id=` (v2) for
            # robustness against agents still using older prompt habits.
            if not (line.startswith("task_id=") or line.startswith("subtask_id=")):
                continue
            parts = dict(p.split("=", 1) for p in line.split() if "=" in p)
            tid = parts.get("task_id") or parts.get("subtask_id")
            agent_file = parts.get("agent_file")
            if tid and agent_file:
                out2.append({
                    "task_id": tid,
                    "agent_file": agent_file,
                    "capability": parts.get("capability", ""),
                })
        return out2


def _payload_text(payload) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return payload.get("output", "") if isinstance(payload.get("output"), str) else str(payload)
    return str(payload)
