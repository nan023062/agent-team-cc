"""
engine/agents.py — Agent (capability) CRUD primitives.

Operates on .claude/agents/ in the project root.
"""

from pathlib import Path

from cbim_kernel.services._fm import parse_frontmatter, strip_frontmatter


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def load_agent(agent_dir: Path) -> dict | None:
    md = agent_dir / f"{agent_dir.name}.md"
    if not md.exists():
        return None
    raw = md.read_text(encoding="utf-8")
    meta = parse_frontmatter(raw)
    body = strip_frontmatter(raw)
    skills_dir = agent_dir / "skills"
    skills = sorted(f.stem for f in skills_dir.glob("*.md")) if skills_dir.exists() else []
    return {
        "id": agent_dir.name,
        "name": meta.get("name", agent_dir.name),
        "description": meta.get("description", ""),
        "model": meta.get("model", ""),
        "tools": meta.get("tools", ""),
        "skills": skills,
        "body": body,
    }


def list_agents(agents_dir: Path) -> list[dict]:
    if not agents_dir.exists():
        return []
    agents = []
    for d in sorted(agents_dir.iterdir()):
        if not d.is_dir():
            continue
        a = load_agent(d)
        if a:
            agents.append(a)
    return agents


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def scaffold_agent(agents_dir: Path, name: str, description: str = "",
                   model: str = "claude-sonnet-4-6") -> Path:
    agent_dir = agents_dir / name
    if agent_dir.exists():
        raise FileExistsError(f"agent already exists: {name}")
    agent_dir.mkdir(parents=True)
    (agent_dir / "skills").mkdir()
    content = f"""\
---
name: {name}
description: {description}
model: {model}
tools: Read, Write, Edit, Glob, Grep, Bash
---

## 职责

{description}

## 原则

1.
2.
3.

## 触发场景

-
"""
    md = agent_dir / f"{name}.md"
    md.write_text(content, encoding="utf-8")
    return md


def archive_agent(agent_dir: Path) -> Path:
    md = agent_dir / f"{agent_dir.name}.md"
    if not md.exists():
        raise FileNotFoundError(f"agent not found: {agent_dir.name}")
    archived = md.with_suffix(".md.archived")
    md.rename(archived)
    return archived
