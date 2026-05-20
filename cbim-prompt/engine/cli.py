"""
engine/cli.py — Unified CBIM CLI entry point.

Usage (cwd=cbim-prompt/):
  python -m engine <domain> <command> [args]

Domains:
  memory      write-session | load-context | add | query | delete | reindex | cleanup | preview
  dna         list | show | init | reindex
  agent       list | show | scaffold | archive
  snapshot    [--root PATH]
  skill       list | show <name>
  convention  list | show <name>
"""
import argparse
import importlib
import pkgutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m engine")
    sub = parser.add_subparsers(dest="domain")

    # memory ------------------------------------------------------------------
    from memory.engine import cli as mcli
    from memory.engine.config import load_config
    cfg = load_config()
    pm = sub.add_parser("memory", help="Memory engine commands")
    msub = pm.add_subparsers(dest="command")
    _p = msub.add_parser("write-session"); _p.add_argument("transcript_path"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("load-context"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("add"); _p.add_argument("path"); _p.add_argument("--tier", default="short", choices=["short", "medium"]); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("query"); _p.add_argument("text"); _p.add_argument("--tier", choices=["short", "medium"], default=None); _p.add_argument("--top-k", type=int, default=cfg["query"]["default_top_k"], dest="top_k"); _p.add_argument("--verbose", action="store_true"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("delete"); _p.add_argument("path"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("reindex"); _p.add_argument("--tier", choices=["short", "medium"], default=None); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("cleanup"); _p.add_argument("--keep-days", type=int, default=cfg["short_term"]["keep_days"], dest="keep_days"); _p.add_argument("--store-dir", dest="store_dir", default=None)
    _p = msub.add_parser("preview"); _p.add_argument("--port", type=int, default=8765); _p.add_argument("--store-dir", dest="store_dir", default=None)
    mem_cmds = {
        "write-session": mcli.cmd_write_session, "load-context": mcli.cmd_load_context,
        "add": mcli.cmd_add, "query": mcli.cmd_query, "delete": mcli.cmd_delete,
        "reindex": mcli.cmd_reindex, "cleanup": mcli.cmd_cleanup, "preview": mcli.cmd_preview,
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

    # convention --------------------------------------------------------------
    pc = sub.add_parser("convention", help="List or show convention content")
    csub = pc.add_subparsers(dest="command")
    csub.add_parser("list")
    _p = csub.add_parser("show"); _p.add_argument("name")

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
    if domain == "convention":
        return _cmd_convention(args, pc)
    parser.print_help()
    return 1


def _load_skills() -> dict[str, str]:
    skills: dict[str, str] = {}
    import cbi.skills as cbi_skills_pkg
    import memory.skills as mem_skills_pkg
    for pkg, prefix in [(cbi_skills_pkg, "cbi."), (mem_skills_pkg, "memory.")]:
        for info in pkgutil.iter_modules(pkg.__path__):
            full = f"{pkg.__name__}.{info.name}"
            mod = importlib.import_module(full)
            if hasattr(mod, "SKILL"):
                skills[prefix + info.name] = mod.SKILL
            elif info.ispkg:
                # nested skill package (cbi.skills.<name> with skill submodule)
                try:
                    sub = importlib.import_module(f"{full}.skill")
                    if hasattr(sub, "SKILL"):
                        skills[prefix + info.name] = sub.SKILL
                except ModuleNotFoundError:
                    pass
    return skills


def _cmd_skill(args, parser):
    if not args.command:
        parser.print_help(); return 1
    skills = _load_skills()
    if args.command == "list":
        for name in sorted(skills):
            print(name)
        return 0
    if args.command == "show":
        if args.name not in skills:
            print(f"Skill not found: {args.name}", file=sys.stderr)
            return 1
        print(skills[args.name])
        return 0
    parser.print_help()
    return 1


def _load_conventions() -> dict[str, str]:
    import cbi.conventions as conv_pkg
    convs: dict[str, str] = {}
    for info in pkgutil.iter_modules(conv_pkg.__path__):
        mod = importlib.import_module(f"{conv_pkg.__name__}.{info.name}")
        for attr in dir(mod):
            if attr.endswith("_CONVENTION"):
                convs[info.name] = getattr(mod, attr)
                break
    return convs


def _cmd_convention(args, parser):
    if not args.command:
        parser.print_help(); return 1
    convs = _load_conventions()
    if args.command == "list":
        for name in sorted(convs):
            print(name)
        return 0
    if args.command == "show":
        if args.name not in convs:
            print(f"Convention not found: {args.name}", file=sys.stderr)
            return 1
        print(convs[args.name])
        return 0
    parser.print_help()
    return 1
