"""actions/dispatch_architect.py — yield to Architect, capture arch_plan.

First tick (when bb.arch_plan is None): emits a DispatchRequest for the
Architect agent and returns RUNNING. on_resume parses the Architect reply
into bb.arch_plan: list[Task].

Prompt scaffolding and JSON-response normalization are delegated to
`engine.loops.architect_execution` — the design flowchart NodeSpec list
is the single source of truth for the prompt and the response shape.
This action only owns:
  - the yield gesture (DispatchRequest)
  - the agent_error short-circuit (arch_error: token)
  - the final coercion from `loop.parse_response()` output to
    `list[Task]` on bb.arch_plan (the BT-level contract)

Reply parsing falls back to the legacy line / free-text path so existing
agent replies (plain text wrap, JSON array directly) keep working.
"""

from __future__ import annotations

import json

from ..api.result import DispatchRequest, Task
from ..core.node import Node, Status


def _loop():
    # Lazy import to break the import cycle: engine.loops/__init__ eagerly
    # imports execution_root → main_loop → this module. Resolved at call time.
    import engine.loops.architect_execution as m
    return m


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
            prompt=_loop().compose_prompt(bb),
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
        plan = self._extract_plan(payload, text)
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

    @staticmethod
    def _payload_text(payload) -> str:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            return payload.get("output", "") if isinstance(payload.get("output"), str) else json.dumps(payload, ensure_ascii=False)
        return str(payload)

    @staticmethod
    def _extract_plan(payload, text: str) -> list[Task]:
        """Coerce a Task list out of whatever the architect returned.

        Strategy:
          1. Run `loop.parse_response(payload)` — it normalizes dict / JSON
             str / list into {"arch_plan": <value>}. If <value> is a list
             of task-shaped dicts, that's our plan.
          2. If <value> is a dict carrying a nested task list (e.g.
             {"context_pack": ..., "items": [...]}), pick the first list
             of dicts inside.
          3. Fall back to substring JSON extraction on the raw text (legacy
             behavior for agents that wrap JSON in prose).
        """
        normalized = _loop().parse_response(payload)
        value = normalized.get("arch_plan")

        plan = _coerce_task_list_maybe(value)
        if plan:
            return plan

        # Substring JSON extraction (legacy fallback for prose-wrapped JSON).
        stripped = (text or "").strip()
        if not stripped:
            return []
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].lstrip("\n")
        try:
            parsed = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
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
            for key in ("arch_plan", "plan"):
                if isinstance(parsed.get(key), list):
                    return _coerce_task_list(parsed[key])
            return []
        if isinstance(parsed, list):
            return _coerce_task_list(parsed)
        return []


def _coerce_task_list_maybe(value) -> list[Task]:
    """Try to find a list of task-dicts inside whatever loop.parse_response gave us."""
    if isinstance(value, list):
        return _coerce_task_list(value)
    if isinstance(value, dict):
        for key in ("arch_plan", "plan", "items", "tasks"):
            inner = value.get(key)
            if isinstance(inner, list):
                tasks = _coerce_task_list(inner)
                if tasks:
                    return tasks
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
