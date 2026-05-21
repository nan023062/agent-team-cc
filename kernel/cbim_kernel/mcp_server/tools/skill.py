"""
mcp_server/tools/skill.py — MCP tools for skill discovery.

Exposes:
  skill_list()          — list all skill keys
  skill_show(name)      — print the SKILL markdown body
"""

from __future__ import annotations

import importlib
import pkgutil


def _load_skills() -> dict[str, str]:
    """Walk cbim_kernel.cbi.agents.*.skills and cbim_kernel.cbi.skills.* — same logic as engine/cli.py."""
    skills: dict[str, str] = {}
    try:
        import cbim_kernel.cbi.agents as agents_pkg
    except ImportError:
        return skills

    for agent_info in pkgutil.iter_modules(agents_pkg.__path__):
        try:
            agent_skills_pkg = importlib.import_module(
                f"{agents_pkg.__name__}.{agent_info.name}.skills"
            )
            for skill_info in pkgutil.iter_modules(agent_skills_pkg.__path__):
                module_path = f"{agent_skills_pkg.__name__}.{skill_info.name}.skill"
                try:
                    mod = importlib.import_module(module_path)
                    if hasattr(mod, "SKILL"):
                        key = f"{agent_info.name}.{skill_info.name}"
                        skills[key] = mod.SKILL
                except ModuleNotFoundError:
                    pass
        except ModuleNotFoundError:
            pass

    try:
        import cbim_kernel.cbi.skills as coord_skills_pkg
        for skill_info in pkgutil.iter_modules(coord_skills_pkg.__path__):
            module_path = f"{coord_skills_pkg.__name__}.{skill_info.name}.skill"
            try:
                mod = importlib.import_module(module_path)
                if hasattr(mod, "SKILL"):
                    skills[skill_info.name] = mod.SKILL
            except ModuleNotFoundError:
                pass
    except ModuleNotFoundError:
        pass

    return skills


def register(mcp) -> None:
    @mcp.tool()
    def skill_list() -> str:
        """List all CBIM skill keys (agent-scoped + global)."""
        skills = _load_skills()
        if not skills:
            return "(no skills found)"
        return "\n".join(sorted(skills))

    @mcp.tool()
    def skill_show(name: str) -> str:
        """Print the SKILL markdown content for the given key.

        Keys look like 'architect.arch_modules' (agent-scoped) or 'memory_write' (global).
        """
        skills = _load_skills()
        if name not in skills:
            return f"ERROR: skill not found: {name}\n\nAvailable: {', '.join(sorted(skills))}"
        return skills[name]
