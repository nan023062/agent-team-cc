"""
engine/cli.py — Unified CBIM CLI entry point.

Usage (cwd=cbim-prompt/):
  python .cbim-prompt/engine <domain> <command> [args]

Domains:
  memory      write-session | load-context | create | add | query | delete | reindex | cleanup | preview
  dna         list | show | init | reindex
  agent       list | show | scaffold | archive
  snapshot    [--root PATH]
  skill       list | show <name>
  soul        list | show <name>
  config      get <key> | set <key> <value> | show
"""
import argparse
import importlib
import json
import pkgutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.import_log import log_import
from engine.log_view import cmd_log_show, cmd_log_tail


def main() -> int:
    parser = argparse.ArgumentParser(prog="python .cbim-prompt/engine")
    sub = parser.add_subparsers(dest="domain")

    # memory ------------------------------------------------------------------
    from memory.engine import cli as mcli
    from memory.engine.config import load_config
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
    from cbi.engine import cli as kcli
    pd = sub.add_parser("dna", help="Module (.dna) commands")
    dsub = pd.add_subparsers(dest="command")
    _p = dsub.add_parser("list"); _p.add_argument("--root", default=None)
    _p = dsub.add_parser("show"); _p.add_argument("path")
    _p = dsub.add_parser("init"); _p.add_argument("dir"); _p.add_argument("--type", required=True, choices=["root", "parent", "leaf"]); _p.add_argument("--name", required=True); _p.add_argument("--owner", required=True); _p.add_argument("--description", default=""); _p.add_argument("--with-contract", action="store_true", dest="with_contract")
    _p = dsub.add_parser("reindex"); _p.add_argument("--root", default=None)
    dna_cmds = {"list": kcli.cmd_modules_list, "show": kcli.cmd_modules_show, "init": kcli.cmd_modules_init, "reindex": kcli.cmd_modules_reindex}

    # agent -------------------------------------------------------------------
    pa = sub.add_parser("agent", help="Agent roster commands")
    asub = pa.add_subparsers(dest="command")
    asub.add_parser("list")
    _p = asub.add_parser("show"); _p.add_argument("name")
    _p = asub.add_parser("scaffold"); _p.add_argument("name"); _p.add_argument("--description", default=""); _p.add_argument("--model", default="claude-sonnet-4-6")
    _p = asub.add_parser("archive"); _p.add_argument("name")
    agent_cmds = {"list": kcli.cmd_agents_list, "show": kcli.cmd_agents_show, "scaffold": kcli.cmd_agents_scaffold, "archive": kcli.cmd_agents_archive}

    # snapshot ----------------------------------------------------------------
    from cbi.engine.snapshot import build_snapshot
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
    pl = sub.add_parser("log", help="View merged debug logs")
    lsub = pl.add_subparsers(dest="command")
    _p = lsub.add_parser("show"); _p.add_argument("--lines", type=int, default=50)
    _p = lsub.add_parser("tail"); _p.add_argument("--interval", type=float, default=1.0)
    log_cmds = {"show": cmd_log_show, "tail": cmd_log_tail}

    # config ------------------------------------------------------------------
    from engine.config import cmd_config_get, cmd_config_set, cmd_config_show
    pc = sub.add_parser("config", help="Read/write .cbim/config.json")
    csub = pc.add_subparsers(dest="command")
    _p = csub.add_parser("get"); _p.add_argument("key")
    _p = csub.add_parser("set"); _p.add_argument("key"); _p.add_argument("value")
    csub.add_parser("show")

    # debug -------------------------------------------------------------------
    pdb = sub.add_parser("debug", help="Toggle debug logging flag")
    dbsub = pdb.add_subparsers(dest="command")
    dbsub.add_parser("on")
    dbsub.add_parser("off")
    dbsub.add_parser("status")

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
    if domain == "debug":
        if not args.command:
            pdb.print_help(); return 1
        return _cmd_debug(args)
    parser.print_help()
    return 1


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


# PreToolUse log script. Embedded inline in .claude/settings.json as a `python -c`
# command. The script is base64-encoded so the shell argument contains only safe
# ASCII (no quotes, no newlines, no backslashes) — this works identically on
# Windows cmd, PowerShell, and POSIX shells.
_PRETOOLUSE_SCRIPT = '''import sys,json,os
from pathlib import Path
from datetime import datetime
try:
    data=json.load(sys.stdin)
    cwd=Path(data.get("cwd") or os.getcwd())
    cbim=cwd/".cbim-prompt"
    if not (cbim/".debug").exists(): sys.exit(0)
    tool=data.get("tool_name","?")
    inp=data.get("tool_input",{})
    if tool in ("Read","Write","Edit"):
        p=f'path={inp.get("file_path","?")}'
    elif tool=="Glob":
        p=f'pattern={inp.get("pattern","?")}'
    elif tool=="Grep":
        p=f'pattern={inp.get("pattern","?")} path={inp.get("path","")}'
    elif tool=="Bash":
        p=f'cmd={str(inp.get("command","?"))[:200]}'
    else:
        p=f'params={len(inp)}keys'
    target=str(inp.get("file_path",inp.get("path",inp.get("pattern",""))))
    bypass=tool in ("Read","Glob","Grep","Write","Edit") and ".cbim-prompt" in target
    warn=" [WARN]" if bypass else ""
    ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logs=cbim/"logs"
    logs.mkdir(parents=True,exist_ok=True)
    (logs/"tools.txt").open("a",encoding="utf-8").write(f"[TOL]{ts}{warn}: tool={tool} | {p}\\n")
except Exception:
    pass
sys.exit(0)
'''


def _pretooluse_inline_command() -> str:
    import base64
    b64 = base64.b64encode(_PRETOOLUSE_SCRIPT.encode("utf-8")).decode("ascii")
    # Single-line command, only safe ASCII inside the outer "..." — portable across
    # Windows cmd, PowerShell, and POSIX shells.
    return f'python -c "import base64;exec(base64.b64decode(\'{b64}\').decode())"'


def _load_settings(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_settings(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _set_pretooluse(settings: dict, entries: list) -> None:
    hooks = settings.setdefault("hooks", {})
    hooks["PreToolUse"] = entries


def _pretooluse_registered(settings: dict) -> str | None:
    entries = settings.get("hooks", {}).get("PreToolUse") or []
    for group in entries:
        for hook in group.get("hooks", []) if isinstance(group, dict) else []:
            cmd = hook.get("command") if isinstance(hook, dict) else None
            if cmd and ("python -c" in cmd or "pre_tool_use" in cmd):
                return cmd
    return None


def _debug_flag_path() -> Path | None:
    # The inline hook reads <project>/.cbim-prompt/.debug. Locate the project root
    # by walking up from cwd until we find .claude/settings.json (same logic as
    # _find_settings), then place the flag at <root>/.cbim-prompt/.debug.
    settings_path = _find_settings()
    if settings_path is None:
        return None
    return settings_path.parent.parent / ".cbim-prompt" / ".debug"


def _cmd_debug(args) -> int:
    flag = _debug_flag_path()
    if args.command == "on":
        if flag is not None:
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.touch()
        settings_path = _find_settings()
        if settings_path is None:
            print("debug: on (no .claude/settings.json found; hook not registered)")
            return 0
        settings = _load_settings(settings_path)
        command = _pretooluse_inline_command()
        _set_pretooluse(settings, [
            {"hooks": [{"type": "command", "command": command}]}
        ])
        # Validate JSON round-trip before writing.
        json.loads(json.dumps(settings))
        _write_settings(settings_path, settings)
        print("debug: on (inline PreToolUse hook registered)")
        return 0
    if args.command == "off":
        if flag is not None and flag.exists():
            flag.unlink()
        settings_path = _find_settings()
        if settings_path is None:
            print("debug: off (no .claude/settings.json found)")
            return 0
        settings = _load_settings(settings_path)
        _set_pretooluse(settings, [])
        _write_settings(settings_path, settings)
        print("debug: off (hook removed)")
        return 0
    if args.command == "status":
        state = "on" if (flag is not None and flag.exists()) else "off"
        settings_path = _find_settings()
        if settings_path is None:
            print(f"debug: {state} (no .claude/settings.json found)")
            return 0
        settings = _load_settings(settings_path)
        registered = _pretooluse_registered(settings)
        if registered:
            short = registered if len(registered) <= 80 else registered[:77] + "..."
            print(f"debug: {state} (PreToolUse hook: {short})")
        else:
            print(f"debug: {state} (PreToolUse hook: not registered)")
        return 0
    return 1


def _load_skills(trigger: str | None = None) -> dict[str, str]:
    import cbi.agents as agents_pkg
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
        import cbi.coordinator.skills as coord_skills_pkg
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
    import cbi.agents as souls_pkg
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

    coord_module_path = "cbi.coordinator.claude_md"
    try:
        coord_mod = importlib.import_module(coord_module_path)
        if trigger is not None:
            log_import(coord_module_path, "ok", trigger)
        for attr in dir(coord_mod):
            if attr.endswith("_MD"):
                souls["assistant"] = getattr(coord_mod, attr)
                break
    except ModuleNotFoundError:
        if trigger is not None:
            log_import(coord_module_path, "miss", trigger)

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
