"""
agents.py — Agent (capability) CRUD operations.

Usage (from project root):
  python cbim/knowledge/agents.py list
  python cbim/knowledge/agents.py show <name>
  python cbim/knowledge/agents.py scaffold <name> --description "..." [--model claude-opus-4-6]
"""

import argparse
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent.parent / "cc-template" / "agents"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict:
    meta: dict = {}
    if not text.startswith("---"):
        return meta
    end = text.find("\n---", 3)
    if end == -1:
        return meta
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].strip()
    return text.strip()


def _load_agent(agent_dir: Path) -> dict | None:
    md = agent_dir / f"{agent_dir.name}.md"
    if not md.exists():
        return None
    raw = md.read_text(encoding="utf-8")
    meta = _parse_frontmatter(raw)
    body = _strip_frontmatter(raw)
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


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    agents = [_load_agent(d) for d in sorted(AGENTS_DIR.iterdir()) if d.is_dir()]
    agents = [a for a in agents if a]
    if not agents:
        print("  No agents found.")
        return 0
    for a in agents:
        skills_str = f"  skills: {', '.join(a['skills'])}" if a["skills"] else ""
        print(f"  {a['name']:16s}  {a['model']:20s}  {a['description'][:50]}")
        if skills_str:
            print(f"  {'':16s}  {skills_str}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    agent_dir = AGENTS_DIR / args.name
    agent = _load_agent(agent_dir)
    if not agent:
        print(f"Agent not found: {args.name}", file=sys.stderr)
        return 1
    print(f"Name    : {agent['name']}")
    print(f"Model   : {agent['model']}")
    print(f"Tools   : {agent['tools']}")
    print(f"Skills  : {', '.join(agent['skills']) or '—'}")
    print(f"\nDescription:\n  {agent['description']}")
    print(f"\n{agent['body']}")
    return 0


def cmd_scaffold(args: argparse.Namespace) -> int:
    agent_dir = AGENTS_DIR / args.name
    if agent_dir.exists():
        print(f"Agent already exists: {args.name}", file=sys.stderr)
        return 1
    agent_dir.mkdir(parents=True)
    (agent_dir / "skills").mkdir()

    content = f"""\
---
name: {args.name}
description: {args.description}
model: {args.model}
tools: Read, Write, Edit, Glob, Grep, Bash
---

## 职责

{args.description}

## 原则

1.
2.
3.

## 触发场景

-
"""
    md = agent_dir / f"{args.name}.md"
    md.write_text(content, encoding="utf-8")
    print(f"Created: {md}")
    print(f"Add skills to: {agent_dir / 'skills'}/")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(prog="cbim/knowledge/agents.py")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list")

    p_show = sub.add_parser("show")
    p_show.add_argument("name")

    p_scaffold = sub.add_parser("scaffold")
    p_scaffold.add_argument("name")
    p_scaffold.add_argument("--description", default="")
    p_scaffold.add_argument("--model", default="claude-opus-4-6")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    return {"list": cmd_list, "show": cmd_show, "scaffold": cmd_scaffold}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
