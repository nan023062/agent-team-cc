"""
mcp_server/tools/agent.py — MCP tools for the agent registry.

Exposes:
  agent_list(cwd)        — list installed agents in .claude/agents/
  agent_show(name, cwd)  — full agent .md (description + body)
"""

from __future__ import annotations

from pathlib import Path


def _project_root(cwd: str) -> Path:
    """Walk up from cwd to find a directory containing .claude/agents/."""
    p = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    for _ in range(6):
        if (p / ".claude" / "agents").is_dir():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path(cwd).resolve() if cwd else Path.cwd().resolve()


def register(mcp) -> None:
    @mcp.tool()
    def agent_list(cwd: str = "") -> str:
        """List registered Claude Code agents under `.claude/agents/`.

        Args:
            cwd: Project directory (default: current working dir).
        """
        # Route through the shared service layer so dashboard and MCP
        # see exactly the same roster (including the built-in filter
        # for non-framework agents — opt back in via include_builtin).
        from services import list_agents as _list_agents
        agents = _list_agents(cwd=cwd or None, include_builtin=True)
        if not agents:
            return "(no agents found)"
        return "\n".join(
            f"{a['name']:16s}  {a['model']:24s}  {a['description'][:60]}"
            for a in agents
        )

    @mcp.tool()
    def agent_show(name: str, cwd: str = "") -> str:
        """Show full content of agent `name` (the agent .md file body + frontmatter).

        Args:
            name: Agent directory name (e.g. 'architect', 'hr').
            cwd: Project directory (default: current working dir).
        """
        from cbi.resources import Agent
        root = _project_root(cwd)
        try:
            a = Agent.load(name, root=root)
        except FileNotFoundError:
            return f"ERROR: agent not found: {name}"
        fm = a.frontmatter
        skills = a.skills.list()
        return (
            f"Name    : {fm.get('name', a.id)}\n"
            f"Model   : {fm.get('model', '')}\n"
            f"Tools   : {fm.get('tools', '')}\n"
            f"Skills  : {', '.join(skills) or '—'}\n\n"
            f"Description:\n  {fm.get('description', '')}\n\n"
            f"{a.body.read()}"
        )
