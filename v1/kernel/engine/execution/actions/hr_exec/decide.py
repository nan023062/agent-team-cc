"""hr_exec/decide.py — CoreAgentSelector deterministic leaf.

Runs on the `miss` branch. Consults the shared core-agent capability table
(see ``actions/core_agents.py``); if the current task's
``required_capability`` is a known core role, upgrades the match to ``fit``
and writes the canonical agent file path. Otherwise leaves the match as
``miss`` so the downstream Append step logs an agent_gap.

No LLM call. Always returns SUCCESS — even on miss, that's a successful
"checked the table" outcome; the gap is what downstream records.

The table itself lives in ``actions/core_agents.py`` (single source of
truth shared with ``actions/dispatch_core_agent.py``).
"""

from __future__ import annotations

from engine.core.node import Node, Status

from ..core_agents import CORE_AGENT_CAPABILITY_TABLE


class CoreAgentSelector(Node):
    def __init__(self, *, name: str = "CoreAgentSelector") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        task = getattr(bb, "hr_current_task", None) or {}
        cap = task.get("required_capability")
        if isinstance(cap, str):
            agent_file = CORE_AGENT_CAPABILITY_TABLE.get(cap.strip().lower())
            if agent_file:
                bb.hr_current_match = {
                    "kind": "fit",
                    "agent_file": agent_file,
                    "note": f"core agent direct-match on capability={cap}",
                }
        # If no upgrade applied, the existing miss verdict stays as-is.
        return Status.SUCCESS


def build() -> CoreAgentSelector:
    return CoreAgentSelector()
