"""
cli.py — Knowledge engine command implementations.

These cmd_* functions are dispatched by the unified `engine` CLI
(see cbim-prompt/engine/cli.py). This module no longer exposes a `main()`
or `__main__` block — invoke via `python .cbim-prompt/engine <domain> <command>`.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from cbi.engine import list_agents, load_agent, scaffold_agent, archive_agent  # noqa: E402
from cbi.engine import list_modules, load_module, init_module                  # noqa: E402
from cbi.engine.modules import update_index                                     # noqa: E402

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
                            args.description, with_contract=args.with_contract,
                            type_=args.type)
        print(f"Initialized [{args.type}]: {aimod}/")
        files = ".dna/module.md"
        if args.type == "root":
            files += ", index.md"
        if args.with_contract:
            files += ", contract.md"
        print(f"  Edit {files}")
        if args.type != "root":
            print(f"  Then run: python .cbim-prompt/engine dna reindex")
    except (FileExistsError, FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_modules_reindex(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    update_index(root)
    modules = list_modules(root)
    print(f"Rebuilt index.md  ({len(modules)} modules)")
    return 0
