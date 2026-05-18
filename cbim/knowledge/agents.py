"""
agents.py — Agent (capability) CRUD CLI.

Usage (from project root):
  python cbim/knowledge/agents.py list
  python cbim/knowledge/agents.py show <name>
  python cbim/knowledge/agents.py scaffold <name> --description "..." [--model claude-sonnet-4-6]
  python cbim/knowledge/agents.py archive <name>
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from knowledge.engine import list_agents, load_agent, scaffold_agent, archive_agent  # noqa: E402

AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude" / "agents"


def cmd_list(args: argparse.Namespace) -> int:
    agents = list_agents(AGENTS_DIR)
    if not agents:
        print("  No agents found.")
        return 0
    for a in agents:
        skills = f"  [{', '.join(a['skills'])}]" if a["skills"] else ""
        print(f"  {a['name']:16s}  {a['model']:24s}  {a['description'][:48]}{skills}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    agent = load_agent(AGENTS_DIR / args.name)
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
    try:
        md = scaffold_agent(AGENTS_DIR, args.name, args.description, args.model)
        print(f"Created: {md}")
    except FileExistsError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    try:
        archived = archive_agent(AGENTS_DIR / args.name)
        print(f"Archived: {archived}")
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="cbim/knowledge/agents.py")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list")

    p_show = sub.add_parser("show")
    p_show.add_argument("name")

    p_scaffold = sub.add_parser("scaffold")
    p_scaffold.add_argument("name")
    p_scaffold.add_argument("--description", default="")
    p_scaffold.add_argument("--model", default="claude-sonnet-4-6")

    p_archive = sub.add_parser("archive")
    p_archive.add_argument("name")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    return {"list": cmd_list, "show": cmd_show,
            "scaffold": cmd_scaffold, "archive": cmd_archive}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
