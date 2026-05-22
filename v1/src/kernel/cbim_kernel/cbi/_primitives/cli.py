"""
cli.py — Knowledge engine command implementations.

These cmd_* functions are dispatched by the unified `engine` CLI
(see .cbim/engine/cli.py). This module no longer exposes a `main()`
or `__main__` block — invoke via `python .cbim/engine <domain> <command>`.
"""

import argparse
import sys
from pathlib import Path

from cbim_kernel.cbi.engine import list_agents, load_agent, scaffold_agent, archive_agent
from cbim_kernel.cbi.engine import list_modules, load_module, init_module
from cbim_kernel.cbi.engine.modules import update_index, write_module_doc, write_module_section
from cbim_kernel.context import project_root

AGENTS_DIR = project_root() / ".claude" / "agents"


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
            print(f"  Then run: python .cbim/engine dna reindex")
    except (FileExistsError, FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_modules_write_doc(args: argparse.Namespace) -> int:
    """Write body content into <module-path>/.dna/<file>, preserving frontmatter.

    Exactly one of --content / --content-file must be provided.
    """
    if args.content is None and args.content_file is None:
        print("Error: one of --content or --content-file is required", file=sys.stderr)
        return 1
    if args.content is not None and args.content_file is not None:
        print("Error: --content and --content-file are mutually exclusive", file=sys.stderr)
        return 1

    if args.content is not None:
        body = args.content
    else:
        src = Path(args.content_file)
        if not src.is_file():
            print(f"Error: --content-file not found: {src}", file=sys.stderr)
            return 1
        body = src.read_text(encoding="utf-8")

    try:
        written = write_module_doc(Path(args.module_path), args.file, body)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(str(written.resolve()))
    return 0


def cmd_modules_write_section(args: argparse.Namespace) -> int:
    """Section-level (H2/H3) surgical edit of .dna/{module.md,contract.md}.

    Exactly one of --content / --content-file / --stdin must be provided for
    modes that need content (replace / append / insert-after). For --mode
    delete, none of them may be provided.
    """
    needs_content = args.mode != "delete"
    sources = [
        ("--content", args.content is not None),
        ("--content-file", args.content_file is not None),
        ("--stdin", bool(getattr(args, "stdin", False))),
    ]
    provided = [name for name, ok in sources if ok]

    if needs_content:
        if len(provided) == 0:
            print(
                "Error: one of --content, --content-file, or --stdin is required",
                file=sys.stderr,
            )
            return 1
        if len(provided) > 1:
            print(
                f"Error: {', '.join(provided)} are mutually exclusive",
                file=sys.stderr,
            )
            return 1
        if args.content is not None:
            body = args.content
        elif args.content_file is not None:
            src = Path(args.content_file)
            if not src.is_file():
                print(f"Error: --content-file not found: {src}", file=sys.stderr)
                return 1
            body = src.read_text(encoding="utf-8")
        else:
            body = sys.stdin.read()
    else:
        if provided:
            print(
                f"Error: {', '.join(provided)} forbidden with --mode delete",
                file=sys.stderr,
            )
            return 1
        body = None

    try:
        result = write_module_section(
            Path(args.module_path),
            args.file,
            args.heading,
            args.level,
            args.mode,
            body,
            create_if_missing=bool(getattr(args, "create_if_missing", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
        )
    except (ValueError, FileNotFoundError, LookupError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        # result is the rendered file content (str)
        sys.stdout.write(result if isinstance(result, str) else str(result))
        if isinstance(result, str) and not result.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    # result is a Path
    print(str(Path(result).resolve()))
    return 0


def cmd_modules_reindex(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    update_index(root)
    modules = list_modules(root)
    print(f"Rebuilt index.md  ({len(modules)} modules)")
    return 0
