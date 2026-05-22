"""
mcp_server/tools/skill.py — MCP tools for skill discovery.

Exposes:
  skill_list()          — list all skill keys
  skill_show(name)      — print the SKILL markdown body

Implementation note (P3 Wave 1): discovery is delegated to
`cbim_kernel.cbi.resources.Skill` so there is exactly one place in the
codebase that knows how to walk cbi/agents/*/skills/* and cbi/skills/*.
The previous _load_skills() helper duplicated that walk and has been removed.
"""

from __future__ import annotations

from cbim_kernel.cbi.resources import Skill


def register(mcp) -> None:
    @mcp.tool()
    def skill_list() -> str:
        """List all CBIM skill keys (agent-scoped + global)."""
        keys = Skill.list_builtin()
        if not keys:
            return "(no skills found)"
        return "\n".join(keys)

    @mcp.tool()
    def skill_show(name: str) -> str:
        """Print the SKILL markdown content for the given key.

        Keys look like 'architect.arch_modules' (agent-scoped) or
        'memory_write' (global).
        """
        try:
            skill = Skill.load_builtin(name, trigger="mcp.skill_show")
        except FileNotFoundError:
            available = ", ".join(Skill.list_builtin())
            return f"ERROR: skill not found: {name}\n\nAvailable: {available}"
        return skill.body.read()
