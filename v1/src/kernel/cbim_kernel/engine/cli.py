"""
engine/cli.py — Unified CBIM CLI entry point.

Usage (cwd=.cbim/):
  python .cbim/engine <domain> <command> [args]

Domains:
  memory      write-session | load-context | create | add | query | delete | reindex | cleanup
  dna         list | show | init | reindex
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
    _p = msub.add_parser("write-session"); _p.add_argument("transcript_path"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("load-context"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("create"); _p.add_argument("--slug", required=True); _p.add_argument("--content", required=True); _p.add_argument("--tier", default="short", choices=["short", "medium"]); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("add"); _p.add_argument("path"); _p.add_argument("--tier", default="short", choices=["short", "medium"]); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("query"); _p.add_argument("text"); _p.add_argument("--tier", choices=["short", "medium"], default=None); _p.add_argument("--top-k", type=int, default=cfg["query"]["default_top_k"], dest="top_k"); _p.add_argument("--verbose", action="store_true"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("delete"); _p.add_argument("path"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("reindex"); _p.add_argument("--tier", choices=["short", "medium"], default=None); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("cleanup"); _p.add_argument("--keep-days", type=int, default=cfg["short_term"]["keep_days"], dest="keep_days"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("preview"); _p.add_argument("--port", type=int, default=8765); _p.add_argument("--store-dir", dest="store_dir", default=None)
    mem_cmds = {
        "write-session": mcli.cmd_write_session, "load-context": mcli.cmd_load_context,
        "create": mcli.cmd_create, "add": mcli.cmd_add, "query": mcli.cmd_query,
        "delete": mcli.cmd_delete, "reindex": mcli.cmd_reindex,
        "cleanup": mcli.cmd_cleanup, "preview": mcli.cmd_preview,
    }

    # dna ---------------------------------------------------------------------
    from cbim_kernel.cbi.engine import cli as kcli
    pd = sub.add_parser("dna", help="Module (.dna) commands")
    dsub = pd.add_subparsers(dest="command")
    _p = dsub.add_parser("list"); _p.add_argument("--root", default=None)
    _p = dsub.add_parser("show"); _p.add_argument("path")
    _p = dsub.add_parser("init"); _p.add_argument("dir"); _p.add_argument("--type", required=True, choices=["root", "parent", "leaf"]); _p.add_argument("--name", required=True); _p.add_argument("--owner", required=True); _p.add_argument("--description", default=""); _p.add_argument("--with-contract", action="store_true", dest="with_contract")
    _p = dsub.add_parser("reindex"); _p.add_argument("--root", default=None)
    _p = dsub.add_parser("write-doc", help="Write body content into <module>/.dna/{module.md,contract.md}, preserving frontmatter")
    _p.add_argument("module_path", help="Path to the module directory (the one containing .dna/)")
    _p.add_argument("--file", required=True, choices=["module.md", "contract.md"], help="Which file in .dna/ to write")
    _p.add_argument("--content", default=None, help="Body markdown as an inline string")
    _p.add_argument("--content-file", dest="content_file", default=None, help="Read body markdown from this path")
    _p = dsub.add_parser(
        "write-section",
        help=(
            "Section-level (H2/H3) surgical edit of .dna/{module.md,contract.md}. "
            "Frontmatter is preserved verbatim. "
            "Setext-style headings (underline with ===) are not supported."
        ),
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
    dna_cmds = {"list": kcli.cmd_modules_list, "show": kcli.cmd_modules_show, "init": kcli.cmd_modules_init, "reindex": kcli.cmd_modules_reindex, "write-doc": kcli.cmd_modules_write_doc, "write-section": kcli.cmd_modules_write_section}

    # agent -------------------------------------------------------------------
    pa = sub.add_parser("agent", help="Agent roster commands")
    asub = pa.add_subparsers(dest="command")
    asub.add_parser("list")
    _p = asub.add_parser("show"); _p.add_argument("name")
    _p = asub.add_parser("scaffold"); _p.add_argument("name"); _p.add_argument("--description", default=""); _p.add_argument("--model", default="claude-sonnet-4-6")
    _p = asub.add_parser("archive"); _p.add_argument("name")
    agent_cmds = {"list": kcli.cmd_agents_list, "show": kcli.cmd_agents_show, "scaffold": kcli.cmd_agents_scaffold, "archive": kcli.cmd_agents_archive}

    # snapshot ----------------------------------------------------------------
    from cbim_kernel.cbi.engine.snapshot import build_snapshot
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

    Like `init`, this targets cwd explicitly. We additionally require that
    `cwd/.cbim` exists, because migrate is meaningless without an existing
    project to upgrade.
    """
    import os
    from cbim_kernel import __version__ as _kernel_version
    from cbim_kernel.project.migrate import migrate_project

    version = (
        args.version
        or _kernel_version
        or os.environ.get("CBIM_DEFAULT_VERSION")
        or os.environ.get("CBIM_LAUNCHER_VERSION")
    )
    target = Path.cwd().resolve()
    if not (target / ".cbim").is_dir():
        print(
            f"migrate: no CBIM project in current directory ({target}); "
            "cd into the project root first",
            file=sys.stderr,
        )
        return 1
    return migrate_project(
        target,
        version=version,
        dry_run=args.dry_run,
        force=args.force,
    )


def _cmd_project(args) -> int:
    """Route `cbim project <subcommand>`.

    Currently only `sync` is wired. Targets the resolved project root (walks up
    from cwd looking for .cbim/config.json), not bare cwd, because sync is
    meaningless outside a project.
    """
    from cbim_kernel.project.sync import sync_templates
    from cbim_kernel.project.upgrade.project_state import find_project_root

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


# Backwards-compatible alias - the deprecated `memory preview` shim and any
# other legacy caller still import `cmd_preview` from here.
cmd_preview = cmd_dashboard


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


def _load_skills(trigger: str | None = None) -> dict[str, str]:
    import cbim_kernel.cbi.agents as agents_pkg
    skills: dict[str, str] = {}
    for agent_info in pkgutil.iter_modules(agents_pkg.__path__):
        try:
            agent_skills_pkg = importlib.import_module(
                f"{agents_pkg.__name__}.{agent_info.name}.skills"
            )
            for skill_info in pkgutil.iter_modules(agent_skills_pkg.__path__):
                module_path = f"{agent_skills_pkg.__name__}.{skill_info.name}.skill"
                try:
                    mod = importlib.import_module(module_path)
                    if trigger is not None:
                        log_import(module_path, "ok", trigger)
                    if hasattr(mod, "SKILL"):
                        key = f"{agent_info.name}.{skill_info.name}"
                        skills[key] = mod.SKILL
                except ModuleNotFoundError:
                    if trigger is not None:
                        log_import(module_path, "miss", trigger)
        except ModuleNotFoundError:
            pass

    try:
        import cbim_kernel.cbi.skills as coord_skills_pkg
        for skill_info in pkgutil.iter_modules(coord_skills_pkg.__path__):
            module_path = f"{coord_skills_pkg.__name__}.{skill_info.name}.skill"
            try:
                mod = importlib.import_module(module_path)
                if trigger is not None:
                    log_import(module_path, "ok", trigger)
                if hasattr(mod, "SKILL"):
                    skills[skill_info.name] = mod.SKILL
            except ModuleNotFoundError:
                if trigger is not None:
                    log_import(module_path, "miss", trigger)
    except ModuleNotFoundError:
        pass

    return skills


def _cmd_skill(args, parser):
    if not args.command:
        parser.print_help(); return 1
    if args.command == "list":
        skills = _load_skills()
        for name in sorted(skills):
            print(name)
        return 0
    if args.command == "show":
        skills = _load_skills(trigger="skill.show")
        if args.name not in skills:
            print(f"Skill not found: {args.name}", file=sys.stderr)
            return 1
        print(skills[args.name])
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
