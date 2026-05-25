"""hr_exec/decide.py — CoreAgentSelector deterministic leaf.

Runs on the `miss` branch. Consults a static core-agent lookup table; if
the current task's `required_capability` is a known core role, upgrades
the match to `fit` and writes the canonical agent file path. Otherwise
leaves the match as `miss` so the downstream Append step logs an
agent_gap.

No LLM call. Always returns SUCCESS — even on miss, that's a successful
"checked the table" outcome; the gap is what downstream records.
"""

from __future__ import annotations

from engine.core.node import Node, Status


# Static lookup. Capability aliases collapse to the same agent file.
CORE_AGENT_TABLE: dict[str, str] = {
    "architect":               ".claude/agents/architect/architect.md",
    "hr":                      ".claude/agents/hr/hr.md",
    "auditor":                 ".claude/agents/auditor/auditor.md",
    "programmer":              ".claude/agents/programmer/programmer.md",
    "coder":                   ".claude/agents/programmer/programmer.md",
    "tester":                  ".claude/agents/programmer/programmer.md",
    "python-backend-engineer": ".claude/agents/programmer/programmer.md",
    "prompt-engineer":         ".claude/agents/programmer/programmer.md",
}


class CoreAgentSelector(Node):
    def __init__(self, *, name: str = "CoreAgentSelector") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        task = getattr(bb, "hr_current_task", None) or {}
        cap = task.get("required_capability")
        if isinstance(cap, str):
            agent_file = CORE_AGENT_TABLE.get(cap.strip().lower())
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
