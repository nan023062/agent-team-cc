"""
mcp_server/tools/agent.py — MCP tools for the agent registry.

Exposes:
  agent_list(cwd)        — list installed agents in .claude/agents/
  agent_show(name, cwd)  — full agent .md (description + body)
"""

from __future__ import annotations

from pathlib import Path


def _agents_dir(cwd: str) -> Path:
    p = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    for _ in range(6):
        if (p / ".claude" / "agents").is_dir():
            return p / ".claude" / "agents"
        if p.parent == p:
            break
        p = p.parent
    return (Path(cwd).resolve() if cwd else Path.cwd().resolve()) / ".claude" / "agents"


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
        from cbim_kernel.services import list_agents as _list_agents
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
        from cbim_kernel.cbi.engine.agents import load_agent
        a = load_agent(_agents_dir(cwd) / name)
        if not a:
            return f"ERROR: agent not found: {name}"
        return (
            f"Name    : {a['name']}\n"
            f"Model   : {a['model']}\n"
            f"Tools   : {a['tools']}\n"
            f"Skills  : {', '.join(a.get('skills', [])) or '—'}\n\n"
            f"Description:\n  {a['description']}\n\n"
            f"{a['body']}"
        )
