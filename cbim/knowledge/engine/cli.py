"""
cli.py — Knowledge engine CLI.

Usage (from project root):
  python cbim/knowledge/engine/cli.py agents list
  python cbim/knowledge/engine/cli.py agents show <name>
  python cbim/knowledge/engine/cli.py agents scaffold <name> --description "..." [--model ...]
  python cbim/knowledge/engine/cli.py agents archive <name>

  python cbim/knowledge/engine/cli.py modules list [--root <path>]
  python cbim/knowledge/engine/cli.py modules show <module-dir>
  python cbim/knowledge/engine/cli.py modules init <dir> --name <name> --owner <owner>
  python cbim/knowledge/engine/cli.py modules reindex [--root <path>]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from knowledge.engine import list_agents, load_agent, scaffold_agent, archive_agent  # noqa: E402
from knowledge.engine import list_modules, load_module, init_module                  # noqa: E402
from knowledge.engine.modules import update_index                                     # noqa: E402

AGENTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "agents"


# ---------------------------------------------------------------------------
# Agents commands
# ---------------------------------------------------------------------------

def cmd_agents_list(args: argparse.Namespace) -> int:
    agents = list_agents(AGENTS_DIR)
    if not agents:
        print("  No agents found.")
        return 0
    for a in agents:
        skills = f"  [{', '.join(a['skills'])}]" if a["skills"] else ""
        print(f"  {a['name']:16s}  {a['model']:24s}  {a['description'][:48]}{skills}")
    return 0


def cmd_agents_show(args: argparse.Namespace) -> int:
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


def cmd_agents_scaffold(args: argparse.Namespace) -> int:
    try:
        md = scaffold_agent(AGENTS_DIR, args.name, args.description, args.model)
        print(f"Created: {md}")
    except FileExistsError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_agents_archive(args: argparse.Namespace) -> int:
    try:
        archived = archive_agent(AGENTS_DIR / args.name)
        print(f"Archived: {archived}")
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------------------
# Modules commands
# ---------------------------------------------------------------------------

def cmd_modules_list(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    modules = list_modules(root)
    if not modules:
        print("  No .dna modules found.")
        return 0
    for m in modules:
        kw = f"  [{', '.join(m['keywords'])}]" if m["keywords"] else ""
        print(f"  {m['path']:32s}  [{m['owner']:12s}]  {m['description'][:40]}{kw}")
    return 0


def cmd_modules_show(args: argparse.Namespace) -> int:
    mod_dir = Path(args.path)
    root = mod_dir.parent if mod_dir.parent != mod_dir else Path.cwd()
    m = load_module(mod_dir, root)
    if not m:
        print(f"No .dna/ found in: {mod_dir}", file=sys.stderr)
        return 1
    print(f"Name        : {m['name']}")
    print(f"Owner       : {m['owner']}")
    print(f"Description : {m['description']}")
    if m["keywords"]:     print(f"Keywords    : {', '.join(m['keywords'])}")
    if m["dependencies"]: print(f"Dependencies: {', '.join(m['dependencies'])}")
    if m["workflows"]:    print(f"Workflows   : {', '.join(m['workflows'])}")
    if m["architecture"]: print(f"\n--- module.md (body) ---\n{m['architecture'][:600]}")
    if m["contract"]:     print(f"\n--- contract.md ---\n{m['contract'][:600]}")
    return 0


def cmd_modules_init(args: argparse.Namespace) -> int:
    try:
        aimod = init_module(Path(args.dir), args.name, args.owner,
                            args.description, with_contract=args.with_contract)
        print(f"Initialized: {aimod}/")
        files = ".dna/module.md"
        if args.with_contract:
            files += ", contract.md"
        print(f"  Edit {files}")
        print(f"  Then run: python cbim/knowledge/engine/cli.py modules reindex")
    except FileExistsError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_modules_reindex(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    update_index(root)
    modules = list_modules(root)
    print(f"Rebuilt index.md  ({len(modules)} modules)")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(prog="cbim/knowledge/engine/cli.py")
    sub = parser.add_subparsers(dest="domain")

    # ── agents ──────────────────────────────────────────────────────────────
    p_agents = sub.add_parser("agents")
    agents_sub = p_agents.add_subparsers(dest="command")

    agents_sub.add_parser("list")

    p_show = agents_sub.add_parser("show")
    p_show.add_argument("name")

    p_scaffold = agents_sub.add_parser("scaffold")
    p_scaffold.add_argument("name")
    p_scaffold.add_argument("--description", default="")
    p_scaffold.add_argument("--model", default="claude-sonnet-4-6")

    p_archive = agents_sub.add_parser("archive")
    p_archive.add_argument("name")

    # ── modules ─────────────────────────────────────────────────────────────
    p_modules = sub.add_parser("modules")
    modules_sub = p_modules.add_subparsers(dest="command")

    p_list = modules_sub.add_parser("list")
    p_list.add_argument("--root", default=None)

    p_mshow = modules_sub.add_parser("show")
    p_mshow.add_argument("path")

    p_init = modules_sub.add_parser("init")
    p_init.add_argument("dir")
    p_init.add_argument("--name", required=True)
    p_init.add_argument("--owner", required=True)
    p_init.add_argument("--description", default="")
    p_init.add_argument("--with-contract", action="store_true",
                        help="Generate contract.md (for protocol-boundary modules only)")

    p_reindex = modules_sub.add_parser("reindex")
    p_reindex.add_argument("--root", default=None)

    # ────────────────────────────────────────────────────────────────────────
    args = parser.parse_args()

    if args.domain == "agents":
        if not args.command:
            p_agents.print_help(); return 1
        return {
            "list":     cmd_agents_list,
            "show":     cmd_agents_show,
            "scaffold": cmd_agents_scaffold,
            "archive":  cmd_agents_archive,
        }[args.command](args)

    if args.domain == "modules":
        if not args.command:
            p_modules.print_help(); return 1
        return {
            "list":    cmd_modules_list,
            "show":    cmd_modules_show,
            "init":    cmd_modules_init,
            "reindex": cmd_modules_reindex,
        }[args.command](args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
