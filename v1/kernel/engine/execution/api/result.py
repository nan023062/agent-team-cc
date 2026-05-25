"""api/result.py — Public dataclasses: BtResult, DispatchRequest, Task, TickStatus.

These types appear at the MCP boundary; their field names and string
literals are public contract surfaces (see .dna/contract.md).

v3 note (WORKFLOW-EXECUTION §0): `Subtask` was the v2 element of
`bb.dispatch_plan`. In v3 the plan is `bb.arch_plan: list[Task]`, produced
in one shot by Architect. `Subtask` is retained as deprecated for any
downstream serializer that still reads old snapshots; new code MUST use
`Task`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DispatchRequest:
    """Returned inside BtResult.Yield to describe a Task-tool dispatch."""

    agent_type: str                       # "work" | "architect" | "hr" | "auditor" — see actions/core_agents.CORE_AGENT_FILES for the canonical mapping of the three core-agent values to .claude/agents/*.md paths. Work dispatches carry subtask_id; core-agent dispatches do not.
    agent_file: str | None
    prompt: str
    subtask_id: str | None = None         # In v3, this carries the Task.id for WorkAgentLeaf dispatches.
    timeout_hint_s: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "DispatchRequest | None":
        if d is None:
            return None
        return cls(
            agent_type=d.get("agent_type", "work"),
            agent_file=d.get("agent_file"),
            prompt=d.get("prompt", ""),
            subtask_id=d.get("subtask_id"),
            timeout_hint_s=d.get("timeout_hint_s"),
        )


@dataclass
class Task:
    """Element of bb.arch_plan (v3).

    Produced by Architect in one shot. HR fills in `agent_file` during the
    HR execution subtree. Work Agent receives `description` + `params` +
    `arch_context` in the dispatch prompt.
    """

    id: str
    description: str
    required_capability: str = "generalist"
    params: dict = field(default_factory=dict)
    arch_context: str | None = None
    agent_file: str | None = None
    timeout_hint_s: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            id=d["id"],
            description=d.get("description", ""),
            required_capability=d.get("required_capability", "generalist"),
            params=dict(d.get("params") or {}),
            arch_context=d.get("arch_context"),
            agent_file=d.get("agent_file"),
            timeout_hint_s=d.get("timeout_hint_s"),
        )


@dataclass
class Subtask:
    """DEPRECATED (v3): use Task instead.

    Retained for backward compatibility with serializers reading v2 (schema
    v1) snapshots. v3 main loop does not construct or read Subtask values.
    """

    id: str
    kind: str
    target_agent: str
    target_agent_file: str | None
    prompt: str
    depends_on: list[str] = field(default_factory=list)
    timeout_hint_s: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Subtask":
        return cls(
            id=d["id"],
            kind=d.get("kind", "execution"),
            target_agent=d.get("target_agent", "programmer"),
            target_agent_file=d.get("target_agent_file"),
            prompt=d.get("prompt", ""),
            depends_on=list(d.get("depends_on", [])),
            timeout_hint_s=d.get("timeout_hint_s"),
        )


@dataclass
class BtResult:
    """Public three-state union returned by bt_tick / bt_tick_resume."""

    kind: str                              # 'done' | 'yield' | 'error'

    # kind == 'done'
    user_message: str | None = None

    # kind == 'yield'
    tick_id: str | None = None
    dispatch_request: DispatchRequest | None = None

    # kind == 'error'
    error_code: str | None = None
    error_message: str | None = None
    interrupt_reason: str | None = None

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"kind": self.kind}
        if self.kind == "done":
            out["user_message"] = self.user_message or ""
        elif self.kind == "yield":
            out["tick_id"] = self.tick_id
            out["dispatch_request"] = (
                self.dispatch_request.to_dict() if self.dispatch_request else None
            )
        elif self.kind == "error":
            out["error_code"] = self.error_code or "engine_internal"
            out["error_message"] = self.error_message or ""
            if self.interrupt_reason:
                out["interrupt_reason"] = self.interrupt_reason
        return out


@dataclass
class TickStatus:
    """Returned by bt_list_running_ticks (one entry per running tick)."""

    tick_id: str
    created_at: str | None
    updated_at: str | None
    user_request: str
    last_yield_dispatch_agent: str | None

    def to_dict(self) -> dict:
        return asdict(self)
