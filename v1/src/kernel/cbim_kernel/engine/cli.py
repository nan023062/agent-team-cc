"""
engine/cli.py — Unified CBIM CLI entry point.

Usage (cwd=.cbim/):
  python .cbim/engine <domain> <command> [args]

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
"""
import argparse
import importlib
import json
import pkgutil
import sys
from pathlib import Path

from cbim_kernel.engine.import_log import log_import
from cbim_kernel.engine.log_view import cmd_log_show, cmd_log_tail


def main() -> int:
    parser = argparse.ArgumentParser(prog="python .cbim/engine")
    sub = parser.add_subparsers(dest="domain")

    # memory ------------------------------------------------------------------
    from cbim_kernel.memory.engine import cli as mcli
    from cbim_kernel.memory.engine.config import load_config
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
    _p = dsub.add_parser("init"); _p.add_argument("dir"); _p.add_argument("--type", required=True, choices=["root", "parent", "leaf"]); _p.add_argument("--name", required=True); _p.add_argument("--owner", required=True); _p.add_argument("--description", default=""); _p.add_argument("--with-contract", action="store_true", dest="with_contract")
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
    _p.add_argument("--dry-run", dest="dry_run", action="store_true",
                    help="Print resulting file to stdout; do not write")
    dna_cmds = {
        "list": _handle_dna_list,
        "show": _handle_dna_show,
        "init": _handle_dna_init,
        "reindex": _handle_dna_reindex,
        "edit": _handle_dna_edit,
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
    agent_cmds = {
        "list": _handle_agent_list,
        "show": _handle_agent_show,
        "scaffold": _handle_agent_scaffold,
        "archive": _handle_agent_archive,
    }

    # snapshot ----------------------------------------------------------------
    from cbim_kernel.cbi._primitives.snapshot import build_snapshot
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
    from cbim_kernel.engine.config import cmd_config_get, cmd_config_set, cmd_config_show
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

    # hook --------------------------------------------------------------------
    phook = sub.add_parser("hook", help="Dispatch a Claude Code hook event (reads JSON on stdin)")
    phook.add_argument("event", help="Hook event name (session-start, session-end, stop, log-prompt, log-pre-tool, log-post-tool)")

    # mcp ---------------------------------------------------------------------
    sub.add_parser("mcp", help="Start the CBIM MCP server (stdio transport)")

    # init --------------------------------------------------------------------
    pinit = sub.add_parser("init", help="Bootstrap a new CBIM project in cwd")
    pinit.add_argument("--force", action="store_true",
                       help="Overwrite existing files (default: idempotent)")
    pinit.add_argument("--version", default=None,
                       help="Kernel version to pin in config.json "
                            "(default: $CBIM_LAUNCHER_VERSION or kernel __version__)")

    # migrate -----------------------------------------------------------------
    pmig = sub.add_parser("migrate", help="Upgrade a kernel-in-project layout to global-kernel model")
    pmig.add_argument("--dry-run", action="store_true", dest="dry_run",
                      help="Show what would happen without making changes")
    pmig.add_argument("--force", action="store_true",
                      help="Skip confirmation prompt")
    pmig.add_argument("--version", default=None,
                      help="Kernel version to pin in config.json (default: kernel __version__)")

    # project -----------------------------------------------------------------
    pproj = sub.add_parser("project", help="Project-level template & layout maintenance")
    projsub = pproj.add_subparsers(dest="command")
    _p = projsub.add_parser(
        "sync",
        help="Refresh kernel-managed project files (CLAUDE.md, agents, settings.json, .gitignore)",
    )
    _p.add_argument("--dry-run", action="store_true", dest="dry_run",
                    help="Print what would be synced without writing anything")

    # upgrade -----------------------------------------------------------------
    from cbim_kernel.project.upgrade import cli as upgrade_cli
    upgrade_cli.build_parser(sub)

    # update ------------------------------------------------------------------
    pupd = sub.add_parser(
        "update",
        help="Update CBIM to the latest available version (one-liner)",
    )
    pupd.add_argument("--dry-run", action="store_true", dest="dry_run",
                      help="Print the plan; do not mutate anything")
    pupd.add_argument("-y", "--yes", action="store_true", dest="yes",
                      help="Skip the interactive confirmation prompt")

    # release-notes -----------------------------------------------------------
    pnotes = sub.add_parser(
        "release-notes",
        help="Print GitHub release notes for a kernel version",
    )
    pnotes.add_argument("version", help="Version tag (e.g. v2.1.0 or 2.1.0)")

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
    if domain == "hook":
        from cbim_kernel.hooks import dispatch
        return dispatch(args.event)
    if domain == "mcp":
        from cbim_kernel.mcp_server import server as mcp_server
        mcp_server.mcp.run()
        return 0
    if domain == "init":
        return _cmd_init(args)
    if domain == "migrate":
        return _cmd_migrate(args)
    if domain == "project":
        if not args.command:
            pproj.print_help(); return 1
        return _cmd_project(args)
    if domain == "upgrade":
        return _cmd_upgrade(args)
    if domain == "update":
        return _cmd_update(args)
    if domain == "release-notes":
        return _cmd_release_notes(args)
    parser.print_help()
    return 1


def _cmd_init(args) -> int:
    """Bootstrap a new CBIM project at the current working directory.

    `init` MUST target cwd, never `project_root()`. The latter walks up to find
    an existing `.cbim/`, which is the wrong semantics for bootstrap and has
    historically caused init to clobber the user-global `~/.cbim/` when run
    from a non-project subdirectory.
    """
    import os
    from cbim_kernel import __version__ as _kernel_version
    from cbim_kernel.project.init import init_project

    # Priority: explicit --version > kernel's own __version__ > env fallbacks.
    # __version__ is the authoritative version of the kernel that's actually
    # executing init; CBIM_LAUNCHER_VERSION is the launcher's self-version
    # (unrelated to the kernel) and is only used as a last resort.
    version = (
        args.version
        or _kernel_version
        or os.environ.get("CBIM_DEFAULT_VERSION")
        or os.environ.get("CBIM_LAUNCHER_VERSION")
    )
    target = Path.cwd().resolve()
    init_project(target, version=version, force=args.force)
    return 0


def _cmd_migrate(args) -> int:
    """Migrate a kernel-in-project layout to the global-kernel model.

    Subprocess facade onto ``python -m updater migrate``. The migration logic
    lives in the updater (not the kernel) so it stays reachable even when the
    pinned kernel cannot start.
    """
    import subprocess
    cmd = [sys.executable, "-m", "updater", "migrate"]
    if getattr(args, "version", None):
        cmd += ["--version", args.version]
    if getattr(args, "dry_run", False):
        cmd.append("--dry-run")
    if getattr(args, "force", False):
        cmd.append("--force")
    return subprocess.run(cmd).returncode


def _cmd_project(args) -> int:
    """Route `cbim project <subcommand>`.

    Currently only `sync` is wired. Targets the resolved project root (walks up
    from cwd looking for .cbim/config.json), not bare cwd, because sync is
    meaningless outside a project.
    """
    from cbim_kernel.project.sync import sync_templates
    from updater.upgrade.project_state import find_project_root

    if args.command != "sync":
        return 1

    root = find_project_root(Path.cwd())
    if root is None:
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


def _cmd_upgrade(args) -> int:
    """Route `cbim upgrade <subcommand>` to the upgrade module."""
    from cbim_kernel.project.upgrade import cli as upgrade_cli

    sub = getattr(args, "upgrade_command", None)
    if sub == "check":
        return upgrade_cli.cmd_check(args)
    if sub == "apply":
        return upgrade_cli.cmd_apply(args)
    sys.stderr.write(
        "usage: cbim upgrade {check,apply} [...]\n"
        "  check   Diagnose joint app + project state\n"
        "  apply   --to <version>  Upgrade the app-side install in place\n"
    )
    return 1


def _cmd_update(args) -> int:
    """Route top-level `cbim update` to the upgrade module."""
    from cbim_kernel.project.upgrade import cli as upgrade_cli
    return upgrade_cli.cmd_update(args)


def _cmd_release_notes(args) -> int:
    """Route `cbim release-notes <version>` to ``python -m updater release-notes``.

    Subprocess facade — the release-notes implementation lives in the updater
    (it does network I/O against GitHub), matching the migrate fan-out pattern.
    """
    import subprocess
    cmd = [sys.executable, "-m", "updater", "release-notes", args.version]
    return subprocess.run(cmd).returncode


def cmd_dashboard(args) -> int:
    """Top-level `dashboard` command. Launches the HTTP UI server.

    Honours $CI to force --no-browser (server still starts; we just
    don't try to spawn a browser on a headless box).
    """
    import os
    from cbim_kernel.context import cbim_dir as _cbim_dir, project_root, kernel_root
    from cbim_kernel.dashboard.server import start_server, load_port

    cbim_dir = _cbim_dir()
    dashboard_dir = kernel_root() / "cbim_kernel" / "dashboard"
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
    from cbim_kernel.context import cbim_dir
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
    from cbim_kernel.cbi.resources import Skill

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
    import cbim_kernel.cbi.agents as souls_pkg
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
        from cbim_kernel.project.sync import read_template
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
    from cbim_kernel.cbi.resources import Agent
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
    from cbim_kernel.cbi.resources import Agent
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
    from cbim_kernel.cbi.resources import Agent
    try:
        agent = Agent.create(
            args.name,
            description=args.description,
            model=args.model,
        )
        print(f"Created: {agent.path}")
    except FileExistsError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def _handle_agent_archive(args: argparse.Namespace) -> int:
    from cbim_kernel.cbi.resources import Agent
    try:
        agent = Agent.load(args.name)
        archived = agent.archive()
        print(f"Archived: {archived}")
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------------------
# DNA handlers — drive cbi.resources.DNAModule directly. write-doc and
# write-section retain their stderr DeprecationWarning and continue calling
# the surgical engine primitives (write_module_doc / write_module_section)
# that preserve frontmatter byte-for-byte; the object model's save() path
# re-renders frontmatter and would break that guarantee.
# ---------------------------------------------------------------------------

def _read_dna_content(args: argparse.Namespace, *, allow_stdin: bool = True) -> str | None:
    """Resolve --content / --content-file / --stdin into one body string.

    Returns the resolved string, None when no source was provided. Raises
    ValueError on mutually-exclusive misuse or unreadable --content-file.
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
    from cbim_kernel.cbi.resources import DNAModule
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
        print(f"  {m.id:32s}  [{owner:12s}]  {desc[:40]}{kw}")
    return 0


def _handle_dna_show(args: argparse.Namespace) -> int:
    from cbim_kernel.cbi.resources import DNAModule
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
    workflows = m.workflows.list()
    architecture = m.body.read()
    contract = m.contract.body.read() if m.contract.exists() else ""

    print(f"Name        : {name}")
    print(f"Owner       : {owner}")
    print(f"Description : {description}")
    if keywords:     print(f"Keywords    : {', '.join(keywords)}")
    if dependencies: print(f"Dependencies: {', '.join(dependencies)}")
    if workflows:    print(f"Workflows   : {', '.join(workflows)}")
    if architecture: print(f"\n--- module.md (body) ---\n{architecture[:600]}")
    if contract:     print(f"\n--- contract.md ---\n{contract[:600]}")
    return 0


def _handle_dna_init(args: argparse.Namespace) -> int:
    from cbim_kernel.cbi.resources import DNAModule
    try:
        m = DNAModule.create(
            Path(args.dir),
            name=args.name,
            owner=args.owner,
            description=args.description,
            with_contract=args.with_contract,
            type=args.type,
        )
        aimod = m.path.parent  # <mod_dir>/.dna
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


def _handle_dna_reindex(args: argparse.Namespace) -> int:
    from cbim_kernel.cbi._primitives.modules import update_index
    from cbim_kernel.cbi.resources import DNAModule
    root = Path(args.root) if args.root else Path.cwd()
    update_index(root)
    modules = DNAModule.list_all(root=root)
    print(f"Rebuilt index.md  ({len(modules)} modules)")
    return 0


def _handle_dna_write_doc(args: argparse.Namespace) -> int:
    """[DEPRECATED] Write body into <module-path>/.dna/<file>, preserving frontmatter."""
    from cbim_kernel.cbi._primitives.modules import write_module_doc
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
        written = write_module_doc(Path(args.module_path), args.file, body)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(str(written.resolve()))
    return 0


def _handle_dna_write_section(args: argparse.Namespace) -> int:
    """[DEPRECATED] Section-level surgical edit of .dna/{module.md,contract.md}."""
    from cbim_kernel.cbi._primitives.modules import write_module_section
    print(
        "DeprecationWarning: 'dna write-section' is deprecated, "
        "use 'dna edit --target section' instead.",
        file=sys.stderr,
    )
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
        sys.stdout.write(result if isinstance(result, str) else str(result))
        if isinstance(result, str) and not result.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    print(str(Path(result).resolve()))
    return 0


def _handle_dna_edit(args: argparse.Namespace) -> int:
    """Unified module-edit entry point.

    Routes by --target to the appropriate sub-object on the in-memory
    DNAModule. Frontmatter edits use --field/--value; everything else uses
    the --content / --content-file / --stdin trio resolved by _read_dna_content.

    Dry-run prints the rendered result to stdout and does NOT touch disk.
    """
    from cbim_kernel.cbi.resources import DNAModule

    target = args.target
    dry_run = bool(getattr(args, "dry_run", False))

    try:
        m = DNAModule.load(Path(args.module_path))
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        if target == "frontmatter":
            from cbim_kernel.cbi._primitives.modules import _MODULE_FM_LIST_FIELDS

            if args.field is None:
                raise ValueError("--field is required for --target frontmatter")
            value_given = args.value is not None
            list_given = getattr(args, "value_list", None) is not None
            if value_given and list_given:
                raise ValueError("--value and --value-list are mutually exclusive")
            if not value_given and not list_given:
                raise ValueError(
                    "one of --value or --value-list is required for --target frontmatter"
                )
            if args.field in _MODULE_FM_LIST_FIELDS and value_given:
                raise ValueError(
                    f"field {args.field!r} is a list-typed field; "
                    f"use --value-list instead of --value\n"
                    f"       example: cbim dna edit ... --field {args.field} "
                    f"--value-list item_a item_b"
                )
            new_value = args.value_list if list_given else args.value
            m.frontmatter.set(args.field, new_value)

        elif target == "body":
            content = _read_dna_content(args)
            if content is None:
                raise ValueError("one of --content / --content-file / --stdin is required")
            m.body.write(content)

        elif target == "section":
            if args.heading is None:
                raise ValueError("--heading is required for --target section")
            mode = args.mode or "replace"
            needs_content = mode != "delete"
            content = _read_dna_content(args)
            if needs_content and content is None:
                raise ValueError("one of --content / --content-file / --stdin is required")
            if not needs_content and content is not None:
                raise ValueError("content sources are forbidden with --mode delete")
            m.body.write_section(
                args.heading, content,
                level=args.level, mode=mode,
                create_if_missing=bool(args.create_if_missing),
            )

        elif target == "contract":
            content = _read_dna_content(args)
            if content is None:
                raise ValueError("one of --content / --content-file / --stdin is required")
            if not dry_run:
                m.contract.ensure()
            m.contract.body.write(content)

        elif target == "contract-section":
            if args.heading is None:
                raise ValueError("--heading is required for --target contract-section")
            mode = args.mode or "replace"
            needs_content = mode != "delete"
            content = _read_dna_content(args)
            if needs_content and content is None:
                raise ValueError("one of --content / --content-file / --stdin is required")
            if not needs_content and content is not None:
                raise ValueError("content sources are forbidden with --mode delete")
            if not dry_run:
                m.contract.ensure()
            m.contract.body.write_section(
                args.heading, content,
                level=args.level, mode=mode,
                create_if_missing=bool(args.create_if_missing),
            )

        elif target == "workflow":
            if not args.name:
                raise ValueError("--name is required for --target workflow")
            content = _read_dna_content(args)
            if content is None:
                raise ValueError("one of --content / --content-file / --stdin is required")
            if dry_run:
                sys.stdout.write(content if content.endswith("\n") else content + "\n")
                return 0
            m.workflows.add(args.name, content)
            print(str((m.path.parent / "workflows" / args.name / "workflow.md").resolve()))
            return 0

        else:
            raise ValueError(f"unknown --target: {target!r}")

    except (ValueError, LookupError, FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if dry_run:
        if target in ("contract", "contract-section"):
            out = m.contract.body.read()
        else:
            out = m._render()
        sys.stdout.write(out)
        if out and not out.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    m.save()
    if target in ("contract", "contract-section"):
        print(str(m.contract.path.resolve()))
    else:
        print(str(m.path.resolve()))
    return 0
