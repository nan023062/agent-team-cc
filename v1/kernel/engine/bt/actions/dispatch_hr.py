"""actions/dispatch_hr.py — yield to HR, assign agent_file to every Task.

First tick (when any Task in bb.arch_plan lacks an agent_file): emits a
DispatchRequest for HR and returns RUNNING. on_resume parses HR's
assignment list into bb.agent_assignments and merges agent_file back into
the corresponding Task dicts in bb.arch_plan.

Idempotent: a tick where every Task already has an agent_file returns
SUCCESS without re-dispatching. Safe to wrap in @Retry.

agent_gap handling: if HR replies with "agent_gap:" prefix the action
writes bb.interrupt_reason and returns FAILURE on the next tick.

Accepted reply formats:
  - "task_id=t1 agent_file=.claude/agents/x/x.md capability=py" lines
  - dict with key "agent_assignments": list[{task_id, agent_file, capability}]
"""

from __future__ import annotations

from ..api.result import DispatchRequest
from ..core.node import Node, Status


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
            prompt=self._compose_prompt(bb, missing),
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
        assignments = self._parse_assignments(payload, text)
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

    def _compose_prompt(self, bb, missing: list[dict]) -> str:
        lines = ["# HR — Agent Assignment Request (execution mode)", "",
                 "## User request", bb.user_request or "", "",
                 "## Tasks needing agent assignment"]
        for t in missing:
            lines.append(
                f"- task_id={t.get('id')} "
                f"capability={t.get('required_capability', 'generalist')} "
                f"description={(t.get('description') or '')[:120]}"
            )
        lines += ["", "## Asked of HR",
                  "Return one line per task in the form:",
                  "  task_id=<id> agent_file=<path> capability=<short tag>",
                  "If no suitable agent exists for some task, emit:",
                  "  agent_gap: <capability or note>"]
        return "\n".join(lines)

    @staticmethod
    def _parse_assignments(payload, text: str) -> list[dict]:
        if isinstance(payload, dict) and isinstance(payload.get("agent_assignments"), list):
            out: list[dict] = []
            for a in payload["agent_assignments"]:
                if isinstance(a, dict) and "task_id" in a and "agent_file" in a:
                    out.append({
                        "task_id": a["task_id"],
                        "agent_file": a["agent_file"],
                        "capability": a.get("capability", ""),
                    })
            if out:
                return out
        out: list[dict] = []
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
                out.append({
                    "task_id": tid,
                    "agent_file": agent_file,
                    "capability": parts.get("capability", ""),
                })
        return out


def _payload_text(payload) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return payload.get("output", "") if isinstance(payload.get("output"), str) else str(payload)
    return str(payload)
