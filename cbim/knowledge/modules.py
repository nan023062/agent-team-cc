"""
modules.py — Knowledge module (.aimodule) CRUD CLI.

Usage (from project root):
  python cbim/knowledge/modules.py list [--root <path>]
  python cbim/knowledge/modules.py show <module-dir>
  python cbim/knowledge/modules.py init <dir> --name <name> --owner <owner> [--description "..."]
  python cbim/knowledge/modules.py reindex [--root <path>]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from knowledge.engine import list_modules, load_module, init_module  # noqa: E402
from knowledge.engine.modules import update_index                     # noqa: E402


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    modules = list_modules(root)
    if not modules:
        print("  No .aimodule modules found.")
        return 0
    for m in modules:
        kw = f"  [{', '.join(m['keywords'])}]" if m["keywords"] else ""
        print(f"  {m['path']:32s}  [{m['owner']:12s}]  {m['description'][:40]}{kw}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    mod_dir = Path(args.path)
    root = mod_dir.parent if mod_dir.parent != mod_dir else Path.cwd()
    m = load_module(mod_dir, root)
    if not m:
        print(f"No .aimodule/ found in: {mod_dir}", file=sys.stderr)
        return 1
    print(f"Name        : {m['name']}")
    print(f"Owner       : {m['owner']}")
    print(f"Description : {m['description']}")
    if m["keywords"]:    print(f"Keywords    : {', '.join(m['keywords'])}")
    if m["dependencies"]: print(f"Dependencies: {', '.join(m['dependencies'])}")
    if m["workflows"]:   print(f"Workflows   : {', '.join(m['workflows'])}")
    if m["architecture"]: print(f"\n--- architecture.md ---\n{m['architecture'][:600]}")
    if m["contract"]:    print(f"\n--- contract.md ---\n{m['contract'][:600]}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    try:
        aimod = init_module(Path(args.dir), args.name, args.owner, args.description)
        print(f"Initialized: {aimod}/")
        print(f"  Edit .aimodule/module.json, architecture.md, contract.md")
        print(f"  Then run: python cbim/knowledge/modules.py reindex")
    except FileExistsError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_reindex(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    update_index(root)
    modules = list_modules(root)
    print(f"Rebuilt index.md  ({len(modules)} modules)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="cbim/knowledge/modules.py")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list")
    p_list.add_argument("--root", default=None)

    p_show = sub.add_parser("show")
    p_show.add_argument("path")

    p_init = sub.add_parser("init")
    p_init.add_argument("dir")
    p_init.add_argument("--name", required=True)
    p_init.add_argument("--owner", required=True)
    p_init.add_argument("--description", default="")

    p_reindex = sub.add_parser("reindex")
    p_reindex.add_argument("--root", default=None)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    return {"list": cmd_list, "show": cmd_show,
            "init": cmd_init, "reindex": cmd_reindex}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
