"""Kernel-side upgrade CLI facade — delegates to `python -m updater`."""
from __future__ import annotations
import os, subprocess, sys
from pathlib import Path


def _install_root() -> Path:
    """Mirror of installer/paths.py:install_root() / launcher's _install_root().

    Kept inline so this facade has no import dependency on installer/ — the
    subprocess we spawn needs <install_root> on PYTHONPATH precisely because
    sibling packages (updater/) live there as version-less singletons.
    """
    env = os.environ.get("CBIM_INSTALL_ROOT")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "Cbim-CC"
        return Path.home() / "AppData" / "Local" / "Cbim-CC"
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "Cbim-CC"
    return Path.home() / ".local" / "share" / "Cbim-CC"


def build_parser(subparsers) -> None:
    p_up = subparsers.add_parser("upgrade", help="upgrade commands")
    up_sub = p_up.add_subparsers(dest="upgrade_command")
    p_check = up_sub.add_parser("check")
    p_check.add_argument("--json", action="store_true", dest="as_json")
    p_check.add_argument("--no-network", action="store_true", dest="no_network")
    p_check.add_argument("--refresh-cache", action="store_true", dest="refresh_cache")
    p_apply = up_sub.add_parser("apply")
    p_apply.add_argument("--to", required=True, dest="target")
    p_apply.add_argument("--source", default="github", choices=["local", "git", "github"])
    p_apply.add_argument("--from", default=None, dest="source_from")
    p_apply.add_argument("--dry-run", action="store_true", dest="dry_run")


def _fwd(subcmd: str, extra: list) -> int:
    # The subprocess inherits sys.executable (often the shared venv python),
    # whose site-packages does NOT contain `updater`. updater/ lives at
    # <install_root>/updater/ as a sibling-package singleton, so we must put
    # <install_root> on PYTHONPATH for `python -m updater` to resolve.
    env = os.environ.copy()
    install_root = _install_root()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(install_root) + (os.pathsep + existing_pp if existing_pp else "")
    )
    return subprocess.run(
        [sys.executable, "-m", "updater", subcmd] + extra, env=env
    ).returncode


def cmd_check(args) -> int:
    extra: list = []
    if getattr(args, "as_json", False): extra.append("--json")
    if getattr(args, "no_network", False): extra.append("--no-network")
    if getattr(args, "refresh_cache", False): extra.append("--refresh-cache")
    return _fwd("check", extra)


def cmd_apply(args) -> int:
    extra: list = ["--to", args.target, "--source", getattr(args, "source", "github")]
    if getattr(args, "source_from", None): extra += ["--from", args.source_from]
    if getattr(args, "dry_run", False): extra.append("--dry-run")
    return _fwd("apply", extra)


def cmd_update(args) -> int:
    extra: list = []
    if getattr(args, "dry_run", False): extra.append("--dry-run")
    if getattr(args, "yes", False): extra.append("--yes")
    if getattr(args, "reinstall", False): extra.append("--reinstall")
    local = getattr(args, "local", None)
    if local: extra += ["--local", str(local)]
    return _fwd("update", extra)
