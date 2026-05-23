"""
engine/cli.py — Unified CBIM CLI entry point.

Usage (from project root):
  .cbim/run <domain> <command> [args]

Domains:
  memory      create | add | query | delete | reindex | cleanup
  dna         list | show | init | reindex | edit | write-doc (deprecated) | write-section (deprecated)
  agent       list | show | scaffold | archive
  snapshot    [--root PATH]
  skill       list | show <name>
  soul        list | show <name>
  config      get <key> | set <key> <value> | show
  dashboard   [--port N] [--no-browser]   (preview = deprecated alias)
  debug       on | off | status
  log         show | tail
  init        Bootstrap a new CBIM project in cwd
  project     sync (refresh kernel-managed templates)
  mcp         Start the CBIM MCP server (stdio)
"""
import argparse
import importlib
import json
import pkgutil
import sys
from pathlib import Path

from .import_log import log_import
from .log_view import cmd_log_show, cmd_log_tail


def main() -> int:
    parser = argparse.ArgumentParser(prog=".cbim/run")
    sub = parser.add_subparsers(dest="domain")

    # memory ------------------------------------------------------------------
    from memory.engine import cli as mcli
    from memory.engine.config import load_config
    cfg = load_config()
    pm = sub.add_parser("memory", help="Memory engine commands")
    msub = pm.add_subparsers(dest="command")
    _p = msub.add_parser("create"); _p.add_argument("--slug", required=True); _p.add_argument("--content", required=True); _p.add_argument("--tier", default="short", choices=["short", "medium"]); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("add"); _p.add_argument("path"); _p.add_argument("--tier", default="short", choices=["short", "medium"]); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("query"); _p.add_argument("text"); _p.add_argument("--tier", choices=["short", "medium"], default=None); _p.add_argument("--top-k", type=int, default=cfg["query"]["default_top_k"], dest="top_k"); _p.add_argument("--verbose", action="store_true"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("delete"); _p.add_argument("path"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("reindex"); _p.add_argument("--tier", choices=["short", "medium"], default=None); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("cleanup"); _p.add_argument("--keep-days", type=int, default=cfg["short_term"]["keep_days"], dest="keep_days"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    mem_cmds = {
        "create": mcli.cmd_create, "add": mcli.cmd_add, "query": mcli.cmd_query,
        "delete": mcli.cmd_delete, "reindex": mcli.cmd_reindex,
        "cleanup": mcli.cmd_cleanup,
    }

    # dna ---------------------------------------------------------------------
    pd = sub.add_parser("dna", help="Module (.dna) commands")
    dsub = pd.add_subparsers(dest="command")
    _p = dsub.add_parser("list"); _p.add_argument("--root", default=None)
    _p = dsub.add_parser("show"); _p.add_argument("path")
    _p = dsub.add_parser("init"); _p.add_argument("dir"); _p.add_argument("--type", required=True, choices=["root", "parent", "leaf"]); _p.add_argument("--name", required=True); _p.add_argument("--owner", required=True); _p.add_argument("--description", default=""); _p.add_argument("--with-contract", action="store_true", dest="with_contract"); _p.add_argument("--status", default=None, choices=["spec", "planned", "implemented"], help="Declared intent (default: spec for parent/leaf, implemented for root)")
    _p = dsub.add_parser("reindex"); _p.add_argument("--root", default=None)
    _p = dsub.add_parser(
        "edit",
        help=(
            "Unified module edit: frontmatter / body / section / contract / "
            "contract-section / workflow. Replaces write-doc and write-section."
        ),
    )
    _p.add_argument("module_path", help="Path to the module directory (the one containing .dna/)")
    _p.add_argument("--target", required=True,
                    choices=["frontmatter", "body", "section", "contract", "contract-section", "workflow"],
                    help="What to edit")
    _p.add_argument("--field", default=None, help="Frontmatter field name (for --target frontmatter)")
    _p.add_argument("--value", default=None,
                    help="Frontmatter scalar value (for --target frontmatter); "
                         "use --value-list for list-typed fields")
    _p.add_argument("--value-list", dest="value_list", nargs="+", default=None,
                    metavar="ITEM",
                    help="Frontmatter list value (one or more items, space-separated); "
                         "mutually exclusive with --value")
    _p.add_argument("--clear", dest="clear", action="store_true",
                    help="Clear a list-typed frontmatter field (set to []). "
                         "Only valid with --target frontmatter and a list-typed --field.")
    _p.add_argument("--content", default=None, help="Inline markdown content")
    _p.add_argument("--content-file", dest="content_file", default=None, help="Read content from this path")
    _p.add_argument("--stdin", action="store_true", help="Read content from stdin")
    _p.add_argument("--heading", default=None, help="Exact heading text (for section / contract-section)")
    _p.add_argument("--level", type=int, default=2, choices=[2, 3], help="Heading level (default: 2)")
    _p.add_argument("--mode", default=None, choices=["replace", "append", "insert-after", "delete"],
                    help="Section edit mode (default: replace; ignored for non-section targets)")
    _p.add_argument("--name", default=None, help="Workflow slug (for --target workflow)")
    _p.add_argument("--create-if-missing", dest="create_if_missing", action="store_true",
                    help="For section replace/append: if heading absent, append a new section at EOF")
    _pos = _p.add_mutually_exclusive_group()
    _pos.add_argument("--insert-after", dest="insert_after", default=None,
                      metavar="HEADING",
                      help="When creating a new section, insert it after the section with this heading.")
    _pos.add_argument("--insert-at-top", dest="insert_at_top", action="store_true",
                      help="When creating a new section, insert it at the top of the body "
                           "(after frontmatter, before first section).")
    _p.add_argument("--dry-run", dest="dry_run", action="store_true",
                    help="Print rendered result to stdout; do not write to disk")

    _p = dsub.add_parser("write-doc", help="[deprecated] use `dna edit --target body` instead")
    _p.add_argument("module_path", help="Path to the module directory (the one containing .dna/)")
    _p.add_argument("--file", required=True, choices=["module.md", "contract.md"], help="Which file in .dna/ to write")
    _p.add_argument("--content", default=None, help="Body markdown as an inline string")
    _p.add_argument("--content-file", dest="content_file", default=None, help="Read body markdown from this path")
    _p = dsub.add_parser(
        "write-section",
        help="[deprecated] use `dna edit --target section` instead",
    )
    _p.add_argument("module_path", help="Path to the module directory (the one containing .dna/)")
    _p.add_argument("--file", required=True, choices=["module.md", "contract.md"], help="Which file in .dna/ to edit")
    _p.add_argument("--heading", required=True, help="Exact heading text (without leading '#'s)")
    _p.add_argument("--level", type=int, default=2, choices=[2, 3], help="Heading level (default: 2)")
    _p.add_argument("--mode", required=True, choices=["replace", "append", "insert-after", "delete"], help="Edit mode")
    _p.add_argument("--content", default=None, help="Inline markdown content")
    _p.add_argument("--content-file", dest="content_file", default=None, help="Read content from this path")
    _p.add_argument("--stdin", action="store_true", help="Read content from stdin")
    _p.add_argument("--create-if-missing", dest="create_if_missing", action="store_true",
                    help="For replace/append: if heading absent, append a new section at EOF")
    _pos = _p.add_mutually_exclusive_group()
    _pos.add_argument("--insert-after", dest="insert_after", default=None,
                      metavar="HEADING",
                      help="When creating a new section, insert it after the section with this heading.")
    _pos.add_argument("--insert-at-top", dest="insert_at_top", action="store_true",
                      help="When creating a new section, insert it at the top of the body "
                           "(after frontmatter, before first section).")
    _p.add_argument("--dry-run", dest="dry_run", action="store_true",
                    help="Print resulting file to stdout; do not write")
    _p = dsub.add_parser(
        "split",
        help=(
            "Atomically decompose one source module into one source + N new "
            "modules by extracting named H2 sections. Reports (does NOT "
            "rewrite) other modules whose dependencies reference the source."
        ),
    )
    _p.add_argument("source", help="Source module directory (the one containing .dna/)")
    _p.add_argument("--into", action="append", default=[], dest="into",
                    metavar="PATH:NAME:HEADINGS",
                    help="Repeatable. PATH:NAME:H1|H2|... — H is a literal H2 heading "
                         "text (no leading '##'); multiple headings separated by '|'. "
                         "Example: --into packages/foo:Foo:Positioning|Key Decisions")
    _p.add_argument("--owner-override", dest="owner_override", default=None,
                    help="Override owner for every new split (default: inherit source owner)")
    _p.add_argument("--keep-source", dest="keep_source", action="store_true", default=True,
                    help="(default) Leave split sections in source body with a "
                         "'<!-- split: moved ... -->' comment beneath each heading")
    _p.add_argument("--no-keep-source", dest="keep_source", action="store_false",
                    help="Remove the migrated sections from source entirely")
    _p.add_argument("--dry-run", dest="dry_run", action="store_true",
                    help="Print the plan + dependency_refs report; touch zero files")

    dna_cmds = {
        "list": _handle_dna_list,
        "show": _handle_dna_show,
        "init": _handle_dna_init,
        "reindex": _handle_dna_reindex,
        "edit": _handle_dna_edit,
        "split": _handle_dna_split,
        "write-doc": _handle_dna_write_doc,
        "write-section": _handle_dna_write_section,
    }

    # agent -------------------------------------------------------------------
    pa = sub.add_parser("agent", help="Agent roster commands")
    asub = pa.add_subparsers(dest="command")
    asub.add_parser("list")
    _p = asub.add_parser("show"); _p.add_argument("name")
    _p = asub.add_parser("scaffold"); _p.add_argument("name"); _p.add_argument("--description", default=""); _p.add_argument("--model", default="claude-sonnet-4-6")
    _p = asub.add_parser("archive"); _p.add_argument("name")
    _p = asub.add_parser(
        "update",
        help=(
            "Edit an agent's frontmatter / body / section. The agent's `name` "
            "and the on-disk basename are NOT editable here (rename is a "
            "different operation)."
        ),
    )
    _p.add_argument("name", help="Agent id (directory name under .claude/agents/)")
    _p.add_argument("--target", required=True,
                    choices=["frontmatter", "body", "section"],
                    help="What to edit")
    _p.add_argument("--field", default=None,
                    help="Frontmatter field (frontmatter only): "
                         "description | model | tools")
    _p.add_argument("--value", default=None,
                    help="Frontmatter scalar value; mutually exclusive with --value-list")
    _p.add_argument("--value-list", dest="value_list", nargs="+", default=None,
                    metavar="ITEM",
                    help="Frontmatter list value (one or more items)")
    _p.add_argument("--clear", dest="clear", action="store_true",
                    help="Clear a list-typed frontmatter field (set to []). "
                         "Only valid with --target frontmatter and a list-typed --field.")
    _p.add_argument("--content", default=None, help="Inline markdown content (body/section)")
    _p.add_argument("--content-file", dest="content_file", default=None,
                    help="Read content from this path (body/section)")
    _p.add_argument("--stdin", action="store_true", help="Read content from stdin (body/section)")
    _p.add_argument("--heading", default=None, help="Exact heading text (section only)")
    _p.add_argument("--level", type=int, default=2, choices=[2, 3],
                    help="Heading level (section only; default: 2)")
    _p.add_argument("--mode", default=None,
                    choices=["replace", "append", "insert-after", "delete"],
                    help="Section edit mode (default: replace; section only)")
    _p.add_argument("--create-if-missing", dest="create_if_missing", action="store_true",
                    help="For section replace/append: if heading absent, append at EOF")
    _pos = _p.add_mutually_exclusive_group()
    _pos.add_argument("--insert-after", dest="insert_after", default=None,
                      metavar="HEADING",
                      help="When creating a new section, insert it after the section with this heading.")
    _pos.add_argument("--insert-at-top", dest="insert_at_top", action="store_true",
                      help="When creating a new section, insert it at the top of the body "
                           "(after frontmatter, before first section).")
    _p.add_argument("--dry-run", dest="dry_run", action="store_true",
                    help="Print rendered result to stdout; do not write to disk")

    _p = asub.add_parser(
        "add-skill",
        help="Create a new skill markdown file under an agent's skills/ directory",
    )
    _p.add_argument("agent_name", help="Agent id (directory name under .claude/agents/)")
    _p.add_argument("skill_name", help="Skill file stem (no .md suffix)")
    _p.add_argument("--content", default=None, help="Inline markdown content")
    _p.add_argument("--content-file", dest="content_file", default=None,
                    help="Read content from this path")
    _p.add_argument("--stdin", action="store_true", help="Read content from stdin")
    _p.add_argument("--dry-run", dest="dry_run", action="store_true",
                    help="Print content to stdout; do not create the file")

    agent_cmds = {
        "list": _handle_agent_list,
        "show": _handle_agent_show,
        "scaffold": _handle_agent_scaffold,
        "archive": _handle_agent_archive,
        "update": _handle_agent_update,
        "add-skill": _handle_agent_add_skill,
    }

    # snapshot ----------------------------------------------------------------
    from cbi._primitives.snapshot import build_snapshot
    ps = sub.add_parser("snapshot", help="Project knowledge snapshot")
    ps.add_argument("--root", default=".")

    # skill -------------------------------------------------------------------
    pk = sub.add_parser("skill", help="List or show skill content")
    ksub = pk.add_subparsers(dest="command")
    ksub.add_parser("list")
    _p = ksub.add_parser("show"); _p.add_argument("name")

    # soul
    psl = sub.add_parser("soul", help="List or show built-in agent soul content")
    slsub = psl.add_subparsers(dest="command")
    slsub.add_parser("list")
    _p = slsub.add_parser("show"); _p.add_argument("name")

    # log ---------------------------------------------------------------------
    pl = sub.add_parser("log", help="View per-session logs")
    lsub = pl.add_subparsers(dest="command")
    _p = lsub.add_parser("show"); _p.add_argument("--lines", type=int, default=50); _p.add_argument("--session", default=None, help="Session slug substring (default: current)")
    _p = lsub.add_parser("tail"); _p.add_argument("--interval", type=float, default=1.0); _p.add_argument("--session", default=None, help="Session slug substring (default: current)")
    log_cmds = {"show": cmd_log_show, "tail": cmd_log_tail}

    # config ------------------------------------------------------------------
    from .config import cmd_config_get, cmd_config_set, cmd_config_show
    pc = sub.add_parser("config", help="Read/write .cbim/config.json")
    csub = pc.add_subparsers(dest="command")
    _p = csub.add_parser("get"); _p.add_argument("key")
    _p = csub.add_parser("set"); _p.add_argument("key"); _p.add_argument("value")
    csub.add_parser("show")

    # dashboard ---------------------------------------------------------------
    pdash = sub.add_parser("dashboard", help="Start the local CBIM dashboard UI server")
    pdash.add_argument("--port", type=int, default=None,
                       help="TCP port (default: dashboard.port in .cbim/config.json, or 8765)")
    pdash.add_argument("--no-browser", dest="no_browser", action="store_true",
                       help="Do not auto-open a browser window (set automatically when CI env var is present)")

    # preview (deprecated alias for `dashboard`) ------------------------------
    pp = sub.add_parser("preview", help="[deprecated] use `dashboard` instead")
    pp.add_argument("--port", type=int, default=None)
    pp.add_argument("--no-browser", dest="no_browser", action="store_true")

    # debug -------------------------------------------------------------------
    pdb = sub.add_parser("debug", help="Toggle debug logging flag")
    dbsub = pdb.add_subparsers(dest="command")
    dbsub.add_parser("on")
    dbsub.add_parser("off")
    dbsub.add_parser("status")

    # mcp ---------------------------------------------------------------------
    sub.add_parser("mcp", help="Start the CBIM MCP server (stdio transport)")

    # init --------------------------------------------------------------------
    pinit = sub.add_parser("init", help="Bootstrap a new CBIM project in cwd")
    pinit.add_argument("--force", action="store_true",
                       help="Overwrite existing files (default: idempotent)")

    # project -----------------------------------------------------------------
    pproj = sub.add_parser("project", help="Project-level template & layout maintenance")
    projsub = pproj.add_subparsers(dest="command")
    _p = projsub.add_parser(
        "sync",
        help="Refresh kernel-managed project files (CLAUDE.md, agents, settings.json, .gitignore)",
    )
    _p.add_argument("--dry-run", action="store_true", dest="dry_run",
                    help="Print what would be synced without writing anything")

    args = parser.parse_args()
    domain = args.domain

    if domain == "memory":
        if not args.command:
            pm.print_help(); return 1
        return mem_cmds[args.command](args)
    if domain == "dna":
        if not args.command:
            pd.print_help(); return 1
        return dna_cmds[args.command](args)
    if domain == "agent":
        if not args.command:
            pa.print_help(); return 1
        return agent_cmds[args.command](args)
    if domain == "snapshot":
        print(build_snapshot(Path(args.root).resolve()))
        return 0
    if domain == "skill":
        return _cmd_skill(args, pk)
    if domain == "soul":
        return _cmd_soul(args, psl)
    if domain == "log":
        if not args.command:
            pl.print_help(); return 1
        return log_cmds[args.command](args)
    if domain == "config":
        if not args.command:
            pc.print_help(); return 1
        return {"get": cmd_config_get, "set": cmd_config_set, "show": cmd_config_show}[args.command](args)
    if domain == "dashboard":
        return cmd_dashboard(args)
    if domain == "preview":
        print("[deprecated] `preview` is now `dashboard`; please use "
              "`python .cbim/engine dashboard`", file=sys.stderr)
        return cmd_dashboard(args)
    if domain == "debug":
        if not args.command:
            pdb.print_help(); return 1
        return _cmd_debug(args)
    if domain == "mcp":
        from mcp_server import server as mcp_server
        mcp_server.mcp.run()
        return 0
    if domain == "init":
        return _cmd_init(args)
    if domain == "project":
        if not args.command:
            pproj.print_help(); return 1
        return _cmd_project(args)
    parser.print_help()
    return 1


def _cmd_init(args) -> int:
    """Bootstrap a new CBIM project at the current working directory.

    `init` MUST target cwd, never `project_root()`. The latter walks up to find
    an existing `.cbim/`, which is the wrong semantics for bootstrap and has
    historically caused init to clobber the user-global `~/.cbim/` when run
    from a non-project subdirectory.
    """
    from project.init import init_project

    target = Path.cwd().resolve()
    init_project(target, force=args.force)
    return 0


def _cmd_project(args) -> int:
    """Route `cbim project <subcommand>`.

    Currently only `sync` is wired. Targets the resolved project root (walks up
    from cwd looking for .cbim/config.json), not bare cwd, because sync is
    meaningless outside a project.
    """
    from context import project_root as find_project_root
    from project.sync import sync_templates

    if args.command != "sync":
        return 1

    # project_root() walks up from cwd looking for .cbim/config.json (or .cbim/).
    # It never returns None; on miss it degrades to cwd. Validate that the
    # resolved root actually has .cbim/config.json — sync is meaningless without
    # a real project.
    try:
        root = find_project_root()
    except RuntimeError as e:
        print(f"project sync: {e}", file=sys.stderr)
        return 1
    if not (root / ".cbim" / "config.json").is_file():
        print(
            "project sync: no CBIM project found (no .cbim/config.json in cwd "
            "or any ancestor); cd into a project root first",
            file=sys.stderr,
        )
        return 1

    prefix = "[cbim] [dry-run] " if args.dry_run else "[cbim] "
    print(f"{prefix}Syncing kernel-managed templates in {root}")
    for action in sync_templates(root, dry_run=args.dry_run):
        print(f"{prefix}{action}")
    if args.dry_run:
        print(f"{prefix}--- DRY RUN complete ---")
    else:
        print("[cbim] Sync complete.")
    return 0


def cmd_dashboard(args) -> int:
    """Top-level `dashboard` command. Launches the HTTP UI server.

    Honours $CI to force --no-browser (server still starts; we just
    don't try to spawn a browser on a headless box).
    """
    import os
    from context import cbim_dir as _cbim_dir, project_root, kernel_root
    from dashboard.server import start_server, load_port

    cbim_dir = _cbim_dir()
    dashboard_dir = kernel_root() / "dashboard"
    root_dir = project_root()

    open_browser = not args.no_browser and not os.environ.get("CI")
    port = args.port if args.port is not None else load_port(cbim_dir)
    start_server(dashboard_dir, cbim_dir, root_dir,
                 port=port, open_browser=open_browser)
    return 0


def _find_settings() -> Path | None:
    p = Path.cwd().resolve()
    for _ in range(5):
        s = p / ".claude" / "settings.json"
        if s.exists():
            return s
        if p.parent == p:
            break
        p = p.parent
    return None


def _debug_flag_path() -> Path | None:
    """The flag lives at <project>/.cbim/.debug, controlling extra [ENG]/[IMP]
    log entries from call_log/import_log. Session-level signals
    ([SESSION]/[USER]/[TOOL]/[RESULT]/[TURN]) always log, no flag needed."""
    from context import cbim_dir
    return cbim_dir() / ".debug"


def _cmd_debug(args) -> int:
    """Toggle the .cbim/.debug flag. Controls extra engine internals only;
    base session signals are always logged."""
    flag = _debug_flag_path()
    if flag is None:
        print("debug: cannot locate project root")
        return 1
    if args.command == "on":
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.touch()
        print(f"debug: on (flag at {flag})")
        return 0
    if args.command == "off":
        if flag.exists():
            flag.unlink()
        print(f"debug: off (flag removed)")
        return 0
    if args.command == "status":
        state = "on" if flag.exists() else "off"
        print(f"debug: {state}")
        return 0
    return 1


def _cmd_skill(args, parser):
    from cbi.resources import Skill

    if not args.command:
        parser.print_help(); return 1
    if args.command == "list":
        for name in Skill.list_builtin():
            print(name)
        return 0
    if args.command == "show":
        try:
            skill = Skill.load_builtin(args.name, trigger="skill.show")
        except FileNotFoundError:
            print(f"Skill not found: {args.name}", file=sys.stderr)
            return 1
        print(skill.body.read())
        return 0
    parser.print_help()
    return 1


def _load_souls(trigger: str | None = None) -> dict[str, str]:
    from cbi import agents as souls_pkg
    souls: dict[str, str] = {}
    for info in pkgutil.iter_modules(souls_pkg.__path__):
        module_path = f"{souls_pkg.__name__}.{info.name}.agent"
        try:
            mod = importlib.import_module(module_path)
            if trigger is not None:
                log_import(module_path, "ok", trigger)
        except ModuleNotFoundError:
            if trigger is not None:
                log_import(module_path, "miss", trigger)
            continue
        for attr in dir(mod):
            if attr.endswith("_MD"):
                souls[info.name] = getattr(mod, attr)
                break

    coord_template = "CLAUDE.md.tmpl"
    try:
        from project.sync import read_template
        souls["assistant"] = read_template(coord_template)
        if trigger is not None:
            log_import(f"project.templates.{coord_template}", "ok", trigger)
    except FileNotFoundError:
        if trigger is not None:
            log_import(f"project.templates.{coord_template}", "miss", trigger)

    return souls


def _cmd_soul(args, parser):
    if not args.command:
        parser.print_help(); return 1
    if args.command == "list":
        souls = _load_souls()
        for name in sorted(souls): print(name)
        return 0
    if args.command == "show":
        souls = _load_souls(trigger="soul.show")
        if args.name not in souls:
            print(f"Soul not found: {args.name}", file=sys.stderr); return 1
        print(souls[args.name]); return 0
    parser.print_help(); return 1


# ---------------------------------------------------------------------------
# Agent handlers — drive cbi.resources.Agent directly. Previously these lived
# in cbi/_primitives/cli.py as cmd_agents_*; that thin wrapper layer was deleted
# in P3 Wave 1 so the CLI dispatch calls the resource model with no detour.
# ---------------------------------------------------------------------------

def _handle_agent_list(args: argparse.Namespace) -> int:
    from cbi.resources import Agent
    agents = Agent.list_all()
    if not agents:
        print("  No agents found.")
        return 0
    for a in agents:
        skills_list = a.skills.list()
        skills = f"  [{', '.join(skills_list)}]" if skills_list else ""
        name = a.frontmatter.get("name", a.id)
        model = a.frontmatter.get("model", "")
        desc = a.frontmatter.get("description", "")
        print(f"  {name:16s}  {model:24s}  {desc[:48]}{skills}")
    return 0


def _handle_agent_show(args: argparse.Namespace) -> int:
    from cbi.resources import Agent
    try:
        agent = Agent.load(args.name)
    except FileNotFoundError:
        print(f"Agent not found: {args.name}", file=sys.stderr)
        return 1
    name = agent.frontmatter.get("name", agent.id)
    model = agent.frontmatter.get("model", "")
    tools = agent.frontmatter.get("tools", "")
    skills_list = agent.skills.list()
    description = agent.frontmatter.get("description", "")
    print(f"Name    : {name}")
    print(f"Model   : {model}")
    print(f"Tools   : {tools}")
    print(f"Skills  : {', '.join(skills_list) or '—'}")
    print(f"\nDescription:\n  {description}")
    print(f"\n{agent.body.read()}")
    return 0


def _handle_agent_scaffold(args: argparse.Namespace) -> int:
    from services import scaffold_agent
    try:
        path = scaffold_agent(
            args.name,
            description=args.description,
            model=args.model,
        )
        print(f"Created: {path}")
    except FileExistsError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def _handle_agent_archive(args: argparse.Namespace) -> int:
    from services import archive_agent
    try:
        archived = archive_agent(args.name)
        print(f"Archived: {archived}")
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


# Frontmatter fields that `agent update --target frontmatter` is allowed to
# touch. `name` (and the on-disk basename) is intentionally NOT editable —
# renaming an agent is a separate operation, not a frontmatter edit.
_AGENT_FM_EDITABLE: tuple[str, ...] = ("description", "model", "tools")


def _render_agent(agent) -> str:
    """Mirror Agent.save() rendering without touching disk (for --dry-run)."""
    fm = agent.frontmatter.render()
    body = agent.body.read()
    if body and not body.startswith("\n"):
        text = fm + "\n" + body
    else:
        text = fm + body
    if not text.endswith("\n"):
        text += "\n"
    return text


def _warn_if_kernel_managed(name: str) -> None:
    """Warn (on stderr) when the user is mutating a kernel-managed agent.

    The 4 built-in agents are overwritten by `cbim project sync`; edits will
    not survive the next sync. Warning only — does not block.
    """
    from project.sync import KERNEL_AGENT_NAMES
    if name in KERNEL_AGENT_NAMES:
        print(
            f"warning: '{name}' is a kernel-managed agent; "
            f"your edits will be overwritten on the next `cbim project sync`",
            file=sys.stderr,
        )


def _handle_agent_update(args: argparse.Namespace) -> int:
    """Edit an existing agent's frontmatter, body, or a single body section.

    Routes by --target to the appropriate sub-object on the in-memory Agent.
    Frontmatter edits use --field plus --value (scalar) or --value-list
    (multi-item). The `name` field is locked. Body / section edits use the
    shared --content / --content-file / --stdin trio. Dry-run prints the
    rendered file to stdout and never touches disk.
    """
    from cbi.resources import Agent
    from services import update_agent

    target = args.target
    dry_run = bool(getattr(args, "dry_run", False))

    try:
        payload = _build_agent_update_payload(args, target)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if dry_run:
        try:
            agent = Agent.load(args.name)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        try:
            _apply_agent_update_in_memory(agent, target, payload)
        except (ValueError, LookupError, FileNotFoundError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        sys.stdout.write(_render_agent(agent))
        return 0

    try:
        path = update_agent(args.name, target, payload)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (ValueError, LookupError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    _warn_if_kernel_managed(args.name)
    print(path)
    return 0


def _build_agent_update_payload(args: argparse.Namespace, target: str) -> dict:
    """Convert argparse Namespace into the dict shape expected by services.update_agent."""
    if target == "frontmatter":
        if args.field is None:
            raise ValueError("--field is required for --target frontmatter")
        value_given = args.value is not None
        list_given = getattr(args, "value_list", None) is not None
        clear_given = bool(getattr(args, "clear", False))
        if sum([value_given, list_given, clear_given]) > 1:
            raise ValueError("--value, --value-list, --clear are mutually exclusive")
        if not (value_given or list_given or clear_given):
            raise ValueError(
                "one of --value / --value-list / --clear is required for --target frontmatter"
            )
        payload = {"field": args.field}
        if clear_given:
            payload["value_list"] = []
        elif list_given:
            payload["value_list"] = args.value_list
        else:
            payload["value"] = args.value
        return payload

    if target == "body":
        content = _read_content_arg(args)
        if content is None:
            raise ValueError("one of --content / --content-file / --stdin is required")
        return {"content": content}

    if target == "section":
        if args.heading is None:
            raise ValueError("--heading is required for --target section")
        mode = args.mode or "replace"
        needs_content = mode != "delete"
        content = _read_content_arg(args)
        if needs_content and content is None:
            raise ValueError("one of --content / --content-file / --stdin is required")
        if not needs_content and content is not None:
            raise ValueError("content sources are forbidden with --mode delete")
        return {
            "heading": args.heading,
            "content": content,
            "mode": mode,
            "level": args.level,
            "create_if_missing": bool(args.create_if_missing),
            "insert_after": getattr(args, "insert_after", None),
            "insert_at_top": bool(getattr(args, "insert_at_top", False)),
        }

    raise ValueError(f"unknown --target: {target!r}")


def _apply_agent_update_in_memory(agent, target: str, payload: dict) -> None:
    """Dry-run helper: apply the same mutations the service would, without saving."""
    if target == "frontmatter":
        if payload["field"] not in _AGENT_FM_EDITABLE:
            raise ValueError(
                f"field {payload['field']!r} is not editable; "
                f"allowed: {', '.join(_AGENT_FM_EDITABLE)} "
                f"(rename is a separate operation, not handled here)"
            )
        new_value = payload.get("value_list", payload.get("value"))
        agent.frontmatter.set(payload["field"], new_value)
    elif target == "body":
        agent.body.write(payload["content"])
    elif target == "section":
        agent.body.write_section(
            payload["heading"], payload.get("content"),
            level=int(payload.get("level", 2)),
            mode=payload.get("mode", "replace"),
            create_if_missing=bool(payload.get("create_if_missing", False)),
            insert_after=payload.get("insert_after"),
            insert_at_top=bool(payload.get("insert_at_top", False)),
        )


def _handle_agent_add_skill(args: argparse.Namespace) -> int:
    """Create a new skill markdown file under <agent>/skills/.

    Refuses to overwrite an existing skill (exit code 2). For modifying an
    existing skill, a future `cbim agent edit-skill` is planned but not yet
    implemented.
    """
    from services import add_skill_to_agent

    try:
        content = _read_content_arg(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if content is None:
        print(
            "Error: one of --content / --content-file / --stdin is required",
            file=sys.stderr,
        )
        return 1

    if args.dry_run:
        sys.stdout.write(content if content.endswith("\n") else content + "\n")
        return 0

    try:
        path = add_skill_to_agent(args.agent_name, args.skill_name, content)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except FileExistsError as e:
        print(
            f"Error: {e} "
            f"(modifying an existing skill is not yet supported; "
            f"edit the file directly via the kernel in a future release)",
            file=sys.stderr,
        )
        return 2

    _warn_if_kernel_managed(args.agent_name)
    print(path)
    return 0


# ---------------------------------------------------------------------------
# DNA handlers — drive cbi.resources.DNAModule directly. write-doc and
# write-section retain their stderr DeprecationWarning and continue calling
# the surgical engine primitives (write_module_doc / write_module_section)
# that preserve frontmatter byte-for-byte; the object model's save() path
# re-renders frontmatter and would break that guarantee.
# ---------------------------------------------------------------------------

def _read_content_arg(args: argparse.Namespace, *, allow_stdin: bool = True) -> str | None:
    """Resolve --content / --content-file / --stdin into one body string.

    Shared by `dna edit`, `agent update`, and `agent add-skill`. Returns the
    resolved string, None when no source was provided. Raises ValueError on
    mutually-exclusive misuse or unreadable --content-file.
    """
    sources = [
        ("--content", args.content is not None),
        ("--content-file", getattr(args, "content_file", None) is not None),
    ]
    if allow_stdin:
        sources.append(("--stdin", bool(getattr(args, "stdin", False))))
    provided = [name for name, ok in sources if ok]

    if len(provided) == 0:
        return None
    if len(provided) > 1:
        raise ValueError(f"{', '.join(provided)} are mutually exclusive")

    if args.content is not None:
        return args.content
    if getattr(args, "content_file", None) is not None:
        src = Path(args.content_file)
        if not src.is_file():
            raise ValueError(f"--content-file not found: {src}")
        return src.read_text(encoding="utf-8")
    return sys.stdin.read()


def _handle_dna_list(args: argparse.Namespace) -> int:
    from cbi.resources import DNAModule
    root = Path(args.root) if args.root else Path.cwd()
    modules = DNAModule.list_all(root=root)
    if not modules:
        print("  No .dna modules found.")
        return 0
    for m in modules:
        keywords = m.frontmatter.get("keywords") or []
        kw = f"  [{', '.join(keywords)}]" if keywords else ""
        owner = m.frontmatter.get("owner", "") or ""
        desc = m.frontmatter.get("description", "") or ""
        # Status default = "implemented" matches load_module()'s back-compat
        # default; here we render straight from frontmatter for the same effect.
        status = m.frontmatter.get("status", "implemented") or "implemented"
        print(f"  {m.id:32s}  [{owner:12s}]  <{status:11s}>  {desc[:40]}{kw}")
    return 0


def _handle_dna_show(args: argparse.Namespace) -> int:
    from cbi.resources import DNAModule
    mod_dir = Path(args.path)
    root = mod_dir.parent if mod_dir.parent != mod_dir else Path.cwd()
    try:
        m = DNAModule.load(mod_dir, root=root)
    except FileNotFoundError:
        print(f"No .dna/ found in: {mod_dir}", file=sys.stderr)
        return 1

    name = m.frontmatter.get("name", m.id)
    owner = m.frontmatter.get("owner", "") or ""
    description = m.frontmatter.get("description", "") or ""
    keywords = m.frontmatter.get("keywords") or []
    dependencies = m.frontmatter.get("dependencies") or []
    status = m.frontmatter.get("status", "implemented") or "implemented"
    workflows = m.workflows.list()
    architecture = m.body.read()
    contract = m.contract.body.read() if m.contract.exists() else ""

    print(f"Name        : {name}")
    print(f"Owner       : {owner}")
    print(f"Status      : {status}")
    print(f"Description : {description}")
    if keywords:     print(f"Keywords    : {', '.join(keywords)}")
    if dependencies: print(f"Dependencies: {', '.join(dependencies)}")
    if workflows:    print(f"Workflows   : {', '.join(workflows)}")
    if architecture: print(f"\n--- module.md (body) ---\n{architecture[:600]}")
    if contract:     print(f"\n--- contract.md ---\n{contract[:600]}")
    return 0


def _handle_dna_init(args: argparse.Namespace) -> int:
    from services import init_module
    try:
        aimod_dir = init_module(
            args.dir,
            kind=args.type,
            name=args.name,
            owner=args.owner,
            description=args.description,
            with_contract=args.with_contract,
            status=args.status,
        )
        # init_module returns the absolute path to .dna/ (the directory containing module.md).
        print(f"Initialized [{args.type}]: {aimod_dir}/")
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


def _handle_dna_reindex(args: argparse.Namespace) -> int:
    from cbi._primitives.modules import update_index
    from cbi.resources import DNAModule
    root = Path(args.root) if args.root else Path.cwd()
    update_index(root)
    modules = DNAModule.list_all(root=root)
    print(f"Rebuilt index.md  ({len(modules)} modules)")
    return 0


def _handle_dna_write_doc(args: argparse.Namespace) -> int:
    """[DEPRECATED] Write body into <module-path>/.dna/<file>, preserving frontmatter."""
    from services import write_doc
    print(
        "DeprecationWarning: 'dna write-doc' is deprecated, "
        "use 'dna edit --target body' instead.",
        file=sys.stderr,
    )
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
        path = write_doc(args.module_path, args.file, body)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(path)
    return 0


def _handle_dna_write_section(args: argparse.Namespace) -> int:
    """[DEPRECATED] Section-level surgical edit of .dna/{module.md,contract.md}."""
    print(
        "DeprecationWarning: 'dna write-section' is deprecated, "
        "use 'dna edit --target section' instead.",
        file=sys.stderr,
    )
    if getattr(args, "insert_after", None) or getattr(args, "insert_at_top", False):
        print(
            "Error: --insert-after / --insert-at-top are not supported by the "
            "deprecated 'dna write-section'; use 'dna edit --target section' instead.",
            file=sys.stderr,
        )
        return 1
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

    # Dry-run preserves the primitive-layer rendering (returns the would-be
    # file text as a string); the service is commit-only and cannot do this.
    if bool(getattr(args, "dry_run", False)):
        from cbi._primitives.modules import write_module_section
        try:
            result = write_module_section(
                Path(args.module_path),
                args.file,
                args.heading,
                args.level,
                args.mode,
                body,
                create_if_missing=bool(getattr(args, "create_if_missing", False)),
                dry_run=True,
            )
        except (ValueError, FileNotFoundError, LookupError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        sys.stdout.write(result if isinstance(result, str) else str(result))
        if isinstance(result, str) and not result.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    from services import write_section
    try:
        path = write_section(
            args.module_path,
            args.file,
            args.heading,
            body,
            args.mode,
            level=args.level,
            create_if_missing=bool(getattr(args, "create_if_missing", False)),
        )
    except (ValueError, FileNotFoundError, LookupError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(path)
    return 0


def _handle_dna_edit(args: argparse.Namespace) -> int:
    """Unified module-edit entry point.

    Routes by --target to the appropriate sub-object on the in-memory
    DNAModule. Frontmatter edits use --field/--value; everything else uses
    the --content / --content-file / --stdin trio resolved by _read_content_arg.

    Dry-run prints the rendered result to stdout and does NOT touch disk.
    """
    from cbi.resources import DNAModule
    from services import edit_module

    target = args.target
    dry_run = bool(getattr(args, "dry_run", False))

    try:
        payload = _build_dna_edit_payload(args, target)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if target == "workflow" and dry_run:
        sys.stdout.write(payload["content"] if payload["content"].endswith("\n")
                         else payload["content"] + "\n")
        return 0

    if dry_run:
        try:
            m = DNAModule.load(Path(args.module_path))
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        try:
            _apply_dna_edit_in_memory(m, target, payload)
        except (ValueError, LookupError, FileNotFoundError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        if target in ("contract", "contract-section"):
            out = m.contract.body.read()
        else:
            out = m._render()
        sys.stdout.write(out)
        if out and not out.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    try:
        path = edit_module(args.module_path, target, payload)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (ValueError, LookupError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(path)
    return 0


def _build_dna_edit_payload(args: argparse.Namespace, target: str) -> dict:
    """Convert argparse Namespace into the dict shape expected by services.edit_module."""
    if target == "frontmatter":
        if args.field is None:
            raise ValueError("--field is required for --target frontmatter")
        value_given = args.value is not None
        list_given = getattr(args, "value_list", None) is not None
        clear_given = bool(getattr(args, "clear", False))
        if sum([value_given, list_given, clear_given]) > 1:
            raise ValueError("--value, --value-list, --clear are mutually exclusive")
        if not (value_given or list_given or clear_given):
            raise ValueError(
                "one of --value / --value-list / --clear is required for --target frontmatter"
            )
        from cbi._primitives.modules import _MODULE_FM_LIST_FIELDS
        if args.field in _MODULE_FM_LIST_FIELDS and value_given:
            raise ValueError(
                f"field {args.field!r} is a list-typed field; "
                f"use --value-list instead of --value\n"
                f"       example: cbim dna edit ... --field {args.field} "
                f"--value-list item_a item_b"
            )
        if args.field == "status" and (list_given or clear_given):
            raise ValueError(
                "field 'status' is a scalar enum; use --value, not --value-list / --clear"
            )
        payload = {"field": args.field}
        if clear_given:
            payload["value_list"] = []
        elif list_given:
            payload["value_list"] = args.value_list
        else:
            payload["value"] = args.value
        return payload

    if target in ("body", "contract"):
        content = _read_content_arg(args)
        if content is None:
            raise ValueError("one of --content / --content-file / --stdin is required")
        return {"content": content}

    if target in ("section", "contract-section"):
        if args.heading is None:
            raise ValueError(f"--heading is required for --target {target}")
        mode = args.mode or "replace"
        needs_content = mode != "delete"
        content = _read_content_arg(args)
        if needs_content and content is None:
            raise ValueError("one of --content / --content-file / --stdin is required")
        if not needs_content and content is not None:
            raise ValueError("content sources are forbidden with --mode delete")
        return {
            "heading": args.heading,
            "content": content,
            "mode": mode,
            "level": args.level,
            "create_if_missing": bool(args.create_if_missing),
            "insert_after": getattr(args, "insert_after", None),
            "insert_at_top": bool(getattr(args, "insert_at_top", False)),
        }

    if target == "workflow":
        if not args.name:
            raise ValueError("--name is required for --target workflow")
        content = _read_content_arg(args)
        if content is None:
            raise ValueError("one of --content / --content-file / --stdin is required")
        return {"name": args.name, "content": content}

    raise ValueError(f"unknown --target: {target!r}")


def _apply_dna_edit_in_memory(m, target: str, payload: dict) -> None:
    """Dry-run helper: apply the same mutations the service would, without saving."""
    if target == "frontmatter":
        from cbi._primitives.modules import _MODULE_FM_STATUS_VALUES
        new_value = payload.get("value_list", payload.get("value"))
        if payload["field"] == "status" and new_value not in _MODULE_FM_STATUS_VALUES:
            raise ValueError(
                f"status must be one of {_MODULE_FM_STATUS_VALUES}, got: {new_value!r}"
            )
        m.frontmatter.set(payload["field"], new_value)
    elif target == "body":
        m.body.write(payload["content"])
    elif target == "section":
        m.body.write_section(
            payload["heading"], payload.get("content"),
            level=int(payload.get("level", 2)),
            mode=payload.get("mode", "replace"),
            create_if_missing=bool(payload.get("create_if_missing", False)),
            insert_after=payload.get("insert_after"),
            insert_at_top=bool(payload.get("insert_at_top", False)),
        )
    elif target == "contract":
        m.contract.body.write(payload["content"])
    elif target == "contract-section":
        m.contract.body.write_section(
            payload["heading"], payload.get("content"),
            level=int(payload.get("level", 2)),
            mode=payload.get("mode", "replace"),
            create_if_missing=bool(payload.get("create_if_missing", False)),
            insert_after=payload.get("insert_after"),
            insert_at_top=bool(payload.get("insert_at_top", False)),
        )


def _parse_into_spec(spec: str) -> dict:
    """Parse one --into PATH:NAME:H1|H2|... value into a split dict.

    Format: <path>:<name>:<heading>[|<heading>...]
    Headings are literal H2 text (no leading '##'); pipe-separated.
    """
    parts = spec.split(":")
    if len(parts) < 3:
        raise ValueError(
            f"--into value must be PATH:NAME:HEADINGS, got: {spec!r}"
        )
    # Path may itself contain a drive letter on Windows (e.g. C:\foo). To stay
    # cross-platform we accept the FIRST colon as the path/name delimiter and
    # the LAST as the name/headings delimiter; everything between is the name.
    # For simplicity in this v1 surface, we require POSIX-style paths in --into
    # (the typical usage is project-relative). Document this in --help if it
    # ever causes friction.
    path = parts[0]
    name = parts[1]
    headings_raw = ":".join(parts[2:])
    headings = [h.strip() for h in headings_raw.split("|") if h.strip()]
    if not headings:
        raise ValueError(f"--into has no headings after the second colon: {spec!r}")
    return {
        "path": path,
        "name": name,
        "headings": headings,
    }


def _handle_dna_split(args: argparse.Namespace) -> int:
    """Atomic cross-module split. See `cbim dna split --help`.

    Prints the report (created paths + dependency_refs warnings) to stdout.
    Returns 0 on success, 1 on validation / atomicity failure.
    """
    from cbi.resources import DNAModule

    if not args.into:
        print(
            "Error: at least one --into PATH:NAME:HEADINGS is required",
            file=sys.stderr,
        )
        return 1

    try:
        splits = [_parse_into_spec(s) for s in args.into]
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.owner_override:
        for s in splits:
            s["owner"] = args.owner_override

    if args.dry_run:
        try:
            result = DNAModule.split(
                Path(args.source),
                splits,
                dry_run=True,
                keep_source=bool(args.keep_source),
            )
        except (ValueError, LookupError, FileNotFoundError, FileExistsError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print("[dry-run] Would create:")
        for s in splits:
            print(f"  - {s['path']}/.dna/module.md  (name={s['name']}, "
                  f"sections={s['headings']})")
        refs = result.dependency_refs_report
        if refs:
            print(
                f"\nWARNING: {len(refs)} module(s) have `dependencies:` entries "
                f"pointing at the source. These are NOT rewritten automatically "
                f"(out of scope for `dna split`):"
            )
            for r in refs:
                print(f"  - {r['module']}: {r['action_required']}")
        return 0

    from services import split_module as _split_module
    try:
        result = _split_module(
            args.source,
            splits,
            strategy="comment" if args.keep_source else "move",
        )
    except (ValueError, LookupError, FileNotFoundError, FileExistsError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print("Created:")
    for p in result["created"]:
        print(f"  - {p}")
    refs = result.get("dependency_refs") or []
    if refs:
        print(
            f"\nWARNING: {len(refs)} module(s) have `dependencies:` entries "
            f"pointing at the source. These are NOT rewritten automatically "
            f"(out of scope for `dna split`):"
        )
        for r in refs:
            print(f"  - {r['module']}: {r['action_required']}")
    return 0
