"""api/result.py — Public dataclasses: BtResult, DispatchRequest, Subtask, TickStatus.

These types appear at the MCP boundary; their field names and string
literals are public contract surfaces (see .dna/contract.md).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DispatchRequest:
    """Returned inside BtResult.Yield to describe a Task-tool dispatch."""

    agent_type: str                       # "architect" | "auditor" | "work"
    agent_file: str | None
    prompt: str
    subtask_id: str | None = None
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
class Subtask:
    """Element of bb.dispatch_plan."""

    id: str
    kind: str                              # 'execution' | 'pure_query' | 'non_requirement'
    target_agent: str                      # logical role: 'programmer' / 'auditor' / ...
    target_agent_file: str | None          # absolute or repo-relative .claude/agents/*.md
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
