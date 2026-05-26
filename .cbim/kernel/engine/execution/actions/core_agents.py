"""actions/core_agents.py — canonical {core agent → .claude/agents/*.md} table.

Single source of truth for the three first-class core agents that the
execution root may dispatch directly (peer to Work Agent, without HR
routing). See module.md §"5 分支模式拓扑 + 三大核心 agent 平级直派".

Importers:
  - actions/dispatch_core_agent.py — DispatchCoreAgent reads CORE_AGENT_FILES
    keyed by agent_type to fill DispatchRequest.agent_file.
  - actions/hr_exec/decide.py — CoreAgentSelector also routes
    `required_capability ∈ {architect, hr, auditor, ...}` to the same files
    via the alias-broadened CORE_AGENT_CAPABILITY_TABLE.

The two tables share the three core-agent rows; capability aliases
(programmer / coder / tester / ...) are HR-side concerns and stay in the
capability table only.
"""

from __future__ import annotations


# Authoritative mapping for the three core agents that execution_root
# can dispatch as first-class peers of Work Agent.
#
# Keys are exactly the `agent_type` values that may appear on
# DispatchRequest for non-work dispatches (see api/result.py + contract.md).
CORE_AGENT_FILES: dict[str, str] = {
    "architect": ".claude/agents/architect/architect.md",
    "hr":        ".claude/agents/hr/hr.md",
    "auditor":   ".claude/agents/auditor/auditor.md",
}


# Capability-keyed lookup used by HR's CoreAgentSelector. The three core
# rows mirror CORE_AGENT_FILES; programmer/coder/tester aliases are HR's
# routing concern and live here only.
CORE_AGENT_CAPABILITY_TABLE: dict[str, str] = {
    # Core agents — same paths as CORE_AGENT_FILES.
    "architect":               CORE_AGENT_FILES["architect"],
    "hr":                      CORE_AGENT_FILES["hr"],
    "auditor":                 CORE_AGENT_FILES["auditor"],
    # Work-agent capability aliases.
    "programmer":              ".claude/agents/programmer/programmer.md",
    "coder":                   ".claude/agents/programmer/programmer.md",
    "tester":                  ".claude/agents/programmer/programmer.md",
    "python-backend-engineer": ".claude/agents/programmer/programmer.md",
    "prompt-engineer":         ".claude/agents/programmer/programmer.md",
}
