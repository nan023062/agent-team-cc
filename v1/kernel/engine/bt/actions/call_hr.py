"""actions/call_hr.py — capability gate, parallel to ArchGate.

Yields a DispatchRequest(agent_type="hr") on first tick when bb.agent_list
is missing/stale; on resume parses HR's agent assignment list into
bb.agent_list. Per-tick idempotent → safe under Retry.
"""

from __future__ import annotations

from ..api.result import DispatchRequest
from ..core.node import Node, Status


class CallHR(Node):
    def __init__(self, *, name: str = "CallHR") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        if bb.interrupt_reason and "agent_gap" in bb.interrupt_reason:
            return Status.FAILURE
        plan = bb.dispatch_plan or []
        needs_hr = [s for s in plan if "arch_context" in (s.get("depends_on") or [])]
        if not needs_hr:
            return Status.SUCCESS
        existing = {a.get("subtask_id") for a in (bb.agent_list or [])}
        required = {s["id"] for s in needs_hr}
        if required.issubset(existing):
            return Status.SUCCESS
        bb.pending_dispatch = DispatchRequest(
            agent_type="hr",
            agent_file=".claude/agents/hr/hr.md",
            prompt=self._compose_hr_prompt(bb, needs_hr),
            subtask_id=None,
        )
        return Status.RUNNING

    def on_resume(self, bb, payload) -> None:
        parsed = self._parse_agent_list(payload)
        text = payload if isinstance(payload, str) else (
            payload.get("output", "") if isinstance(payload, dict) else ""
        )
        if "agent_gap:" in text:
            bb.interrupt_reason = "agent_gap: " + text.split("agent_gap:", 1)[1].strip().splitlines()[0]
        if parsed:
            bb.agent_list = parsed
        elif not bb.interrupt_reason:
            bb.interrupt_reason = "agent_gap: hr returned empty assignment"
        bb.pending_dispatch = None

    def _compose_hr_prompt(self, bb, needs_hr: list[dict]) -> str:
        arch = bb.arch_context or {}
        ctx = arch.get("output") if isinstance(arch, dict) else str(arch)
        lines = ["# Capability Gate — HR Agent Assignment Request", "",
                 "## User request", bb.user_request or "", "",
                 "## ContextPack (from Architect)", ctx or "(none)", "",
                 "## Subtasks needing agent assignment"]
        for s in needs_hr:
            lines.append(f"- id={s['id']} module={s.get('module_path','?')} "
                         f"requirement={s.get('prompt','')[:80]}")
        lines += ["", "## Asked of HR",
                  "Return a line per subtask:",
                  "  subtask_id=<id> agent_file=<path> capability=<short tag>",
                  "If no suitable agent exists for some subtask, emit:",
                  "  agent_gap: <module_path or capability>"]
        return "\n".join(lines)

    def _parse_agent_list(self, payload) -> list[dict]:
        text = payload if isinstance(payload, str) else (
            payload.get("output", "") if isinstance(payload, dict) else str(payload)
        )
        out: list[dict] = []
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("subtask_id="):
                continue
            parts = dict(p.split("=", 1) for p in line.split() if "=" in p)
            if "subtask_id" in parts and "agent_file" in parts:
                out.append({
                    "subtask_id": parts["subtask_id"],
                    "target_agent_file": parts["agent_file"],
                    "agent_capability": parts.get("capability", ""),
                })
        if not out and isinstance(payload, dict) and isinstance(payload.get("agent_list"), list):
            out = list(payload["agent_list"])
        return out
