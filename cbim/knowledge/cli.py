"""
cli.py — Knowledge module (.aimodule) CRUD operations.

Usage (from project root):
  python cbim/knowledge/cli.py list [--root <path>]
  python cbim/knowledge/cli.py show <module-dir>
  python cbim/knowledge/cli.py init <dir> --name <name> --owner <owner> [--description "..."]
"""

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_root() -> Path:
    return Path.cwd()


def _load_module(mod_dir: Path, root: Path) -> dict | None:
    aimod = mod_dir / ".aimodule"
    mj = aimod / "module.json"
    if not mj.exists():
        return None
    try:
        data = json.loads(mj.read_text(encoding="utf-8"))
    except Exception:
        return None

    rel = str(mod_dir.relative_to(root))
    arch = (aimod / "architecture.md").read_text(encoding="utf-8") \
        if (aimod / "architecture.md").exists() else ""
    contract = (aimod / "contract.md").read_text(encoding="utf-8") \
        if (aimod / "contract.md").exists() else ""
    workflows_dir = aimod / "workflows"
    workflows = sorted(w.parent.name for w in workflows_dir.glob("*/workflow.md")) \
        if workflows_dir.exists() else []

    return {
        "id": rel or ".",
        "path": rel or ".",
        "name": data.get("name", rel),
        "owner": data.get("owner", ""),
        "description": data.get("description", ""),
        "keywords": data.get("keywords", []),
        "dependencies": data.get("dependencies", []),
        "architecture": arch,
        "contract": contract,
        "workflows": workflows,
    }


def _collect_modules(root: Path) -> list[dict]:
    modules = []
    for mj in sorted(root.rglob(".aimodule/module.json")):
        mod_dir = mj.parent.parent
        m = _load_module(mod_dir, root)
        if m:
            modules.append(m)
    return modules


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else _find_root()
    modules = _collect_modules(root)
    if not modules:
        print("  No .aimodule modules found.")
        return 0
    for m in modules:
        kw = f"  [{', '.join(m['keywords'])}]" if m["keywords"] else ""
        print(f"  {m['path']:32s}  [{m['owner']:12s}]  {m['description'][:40]}{kw}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    mod_dir = Path(args.path)
    root = mod_dir.parent if mod_dir.parent != mod_dir else _find_root()
    m = _load_module(mod_dir, root)
    if not m:
        print(f"No .aimodule/ found in: {mod_dir}", file=sys.stderr)
        return 1

    print(f"Name        : {m['name']}")
    print(f"Owner       : {m['owner']}")
    print(f"Description : {m['description']}")
    if m["keywords"]:
        print(f"Keywords    : {', '.join(m['keywords'])}")
    if m["dependencies"]:
        print(f"Dependencies: {', '.join(m['dependencies'])}")
    if m["workflows"]:
        print(f"Workflows   : {', '.join(m['workflows'])}")

    if m["architecture"]:
        print(f"\n--- architecture.md ---\n{m['architecture'][:600]}")
    if m["contract"]:
        print(f"\n--- contract.md ---\n{m['contract'][:600]}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    mod_dir = Path(args.dir)
    aimod = mod_dir / ".aimodule"
    if aimod.exists():
        print(f".aimodule already exists: {aimod}", file=sys.stderr)
        return 1

    aimod.mkdir(parents=True)
    (aimod / "workflows").mkdir()

    meta: dict = {"name": args.name, "owner": args.owner}
    if args.description:
        meta["description"] = args.description

    (aimod / "module.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (aimod / "architecture.md").write_text(
        f"# {args.name} — Architecture\n\n## Overview\n\n## Structure\n\n## Key Decisions\n",
        encoding="utf-8",
    )
    (aimod / "contract.md").write_text(
        f"# {args.name} — Contract\n\n## Interfaces\n\n## Events\n",
        encoding="utf-8",
    )

    print(f"Initialized: {aimod}/")
    print(f"  Edit .aimodule/module.json, architecture.md, contract.md")
    print(f"  Then add this module path to your root .aimodule/index.md")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(prog="cbim/knowledge/cli.py")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list")
    p_list.add_argument("--root", default=None, help="Project root (default: cwd)")

    p_show = sub.add_parser("show")
    p_show.add_argument("path", help="Module directory path")

    p_init = sub.add_parser("init")
    p_init.add_argument("dir", help="Directory to initialize as a module")
    p_init.add_argument("--name", required=True)
    p_init.add_argument("--owner", required=True)
    p_init.add_argument("--description", default="")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    return {"list": cmd_list, "show": cmd_show, "init": cmd_init}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
