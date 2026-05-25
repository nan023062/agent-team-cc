"""actions/dispatch_architect.py — yield to Architect, capture arch_plan.

First tick (when bb.arch_plan is None): emits a DispatchRequest for the
Architect agent and returns RUNNING. on_resume parses the Architect reply
into bb.arch_plan: list[Task].

Idempotent: a tick where bb.arch_plan is already populated returns SUCCESS
without re-dispatching. Safe to wrap in @Retry.

Reply parsing — three accepted shapes:
  1. dict with key "arch_plan" → list[dict]  → list[Task]
  2. list[dict]                              → list[Task]
  3. anything else (str / dict without plan) → single fallback Task
     wrapping the raw text as arch_context.

agent_gap-style errors from Architect: if the reply contains the literal
token "arch_error:" the action writes bb.interrupt_reason and returns
FAILURE on the next tick.
"""

from __future__ import annotations

import json

from ..api.result import DispatchRequest, Task
from ..core.node import Node, Status


_ARCH_AGENT_FILE = ".claude/agents/architect/architect.md"


class DispatchArchitect(Node):
    def __init__(self, *, name: str = "DispatchArchitect") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        if bb.interrupt_reason and "arch_error" in bb.interrupt_reason:
            return Status.FAILURE
        if bb.arch_plan is not None:
            return Status.SUCCESS
        bb.pending_dispatch = DispatchRequest(
            agent_type="architect",
            agent_file=_ARCH_AGENT_FILE,
            prompt=self._compose_prompt(bb),
            subtask_id=None,
        )
        return Status.RUNNING

    def on_resume(self, bb, payload) -> None:
        text = self._payload_text(payload)
        if "arch_error:" in text:
            tail = text.split("arch_error:", 1)[1].strip().splitlines()[0]
            bb.interrupt_reason = f"arch_error: {tail}"
            bb.pending_dispatch = None
            return
        plan = self._parse_plan(payload, text)
        if not plan:
            plan = [Task(
                id="t1",
                description=(bb.user_request or "")[:200] or "execute user request",
                required_capability="generalist",
                arch_context=text,
            )]
        bb.arch_plan = [t.to_dict() for t in plan]
        bb.pending_dispatch = None

    # --------------------------------------------------------------
    # Internals
    # --------------------------------------------------------------

    def _compose_prompt(self, bb) -> str:
        return (
            "# Architect — Plan Request (execution mode)\n\n"
            "## User request\n"
            f"{bb.user_request or ''}\n\n"
            "## Asked of Architect\n"
            "Produce an execution plan. Reply with EITHER:\n"
            "  (a) a JSON object {\"arch_plan\": [Task, Task, ...]} where each\n"
            "      Task is {id, description, required_capability, params, arch_context};\n"
            "  (b) a JSON array [Task, ...] directly; OR\n"
            "  (c) free-form text — the engine will wrap it as a single task.\n\n"
            "Use option (a) or (b) for anything multi-step. Use (c) only for\n"
            "single-step requests where the description IS the context."
        )

    @staticmethod
    def _payload_text(payload) -> str:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            return payload.get("output", "") if isinstance(payload.get("output"), str) else json.dumps(payload, ensure_ascii=False)
        return str(payload)

    @staticmethod
    def _parse_plan(payload, text: str) -> list[Task]:
        # Case 1: dict payload may carry the plan directly.
        if isinstance(payload, dict):
            if isinstance(payload.get("arch_plan"), list):
                return _coerce_task_list(payload["arch_plan"])
            if isinstance(payload.get("plan"), list):
                return _coerce_task_list(payload["plan"])

        # Case 2: try to extract JSON from the text.
        stripped = (text or "").strip()
        if not stripped:
            return []
        # Strip ```json ... ``` fences.
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].lstrip("\n")
        try:
            parsed = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            # Try to locate the first {...} or [...] substring.
            start = min((i for i in (stripped.find("{"), stripped.find("["))
                         if i != -1), default=-1)
            end = max(stripped.rfind("}"), stripped.rfind("]"))
            if start == -1 or end <= start:
                return []
            try:
                parsed = json.loads(stripped[start:end + 1])
            except (json.JSONDecodeError, ValueError):
                return []

        if isinstance(parsed, dict):
            if isinstance(parsed.get("arch_plan"), list):
                return _coerce_task_list(parsed["arch_plan"])
            if isinstance(parsed.get("plan"), list):
                return _coerce_task_list(parsed["plan"])
            return []
        if isinstance(parsed, list):
            return _coerce_task_list(parsed)
        return []


def _coerce_task_list(items: list) -> list[Task]:
    out: list[Task] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item.setdefault("id", f"t{i + 1}")
        try:
            out.append(Task.from_dict(item))
        except (KeyError, TypeError):
            continue
    return out
