"""
services/agent_service.py — read-only agent roster service.

Wraps cbi.engine.agents with a stable, preview/MCP-facing surface.
Filters out the built-in framework agents (architect / hr / auditor /
programmer) so the preview UI only shows user-defined work agents.
"""

from __future__ import annotations

from pathlib import Path

from ._fm import find_project_root, parse_frontmatter, strip_frontmatter

# Built-in roles managed by the framework itself — never surfaced as
# "work agents" in the UI. Keep this list in sync with cbi/agents/.
_BUILTIN_AGENTS = frozenset({"architect", "hr", "auditor", "programmer"})


def list_agents(cwd=None, include_builtin: bool = False) -> list[dict]:
    """Return all agent definitions found under `.claude/agents/`.

    Args:
        cwd:             Project search base; walks up to find `.cbim/`.
        include_builtin: When True, framework agents are included
                         (default False — preview wants user agents only).

    Returns:
        List of dicts shaped like::

            {
              "id":          <directory name>,
              "name":        <frontmatter name or id>,
              "description": <frontmatter description>,
              "model":       <frontmatter model>,
              "tools":       <frontmatter tools string>,
              "skills":      [ {"id": <stem>, "body": <md body>}, ... ],
              "body":        <agent .md body with frontmatter stripped>,
            }
    """
    root = Path(find_project_root(cwd))
    agents_dir = root / ".claude" / "agents"
    if not agents_dir.exists():
        return []

    agents: list[dict] = []
    for agent_dir in sorted(agents_dir.iterdir()):
        if not agent_dir.is_dir():
            continue
        if not include_builtin and agent_dir.name in _BUILTIN_AGENTS:
            continue
        md = agent_dir / f"{agent_dir.name}.md"
        if not md.exists():
            continue
        try:
            raw = md.read_text(encoding="utf-8")
        except (FileNotFoundError, PermissionError):
            continue
        meta = parse_frontmatter(raw)
        agents.append({
            "id": agent_dir.name,
            "name": meta.get("name", agent_dir.name),
            "description": meta.get("description", ""),
            "model": meta.get("model", ""),
            "tools": meta.get("tools", ""),
            "skills": _load_skills(agent_dir),
            "body": strip_frontmatter(raw),
        })
    return agents


def _load_skills(agent_dir: Path) -> list[dict]:
    skills_dir = agent_dir / "skills"
    if not skills_dir.exists():
        return []
    out = []
    for skill_file in sorted(skills_dir.glob("*.md")):
        try:
            raw = skill_file.read_text(encoding="utf-8")
        except (FileNotFoundError, PermissionError):
            raw = ""
        out.append({"id": skill_file.stem, "body": strip_frontmatter(raw)})
    return out
