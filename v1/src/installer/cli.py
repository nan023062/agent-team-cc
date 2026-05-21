"""argparse CLI for ``python -m installer``."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Optional, Sequence

from installer import registry
from installer.install import install_from_github, install_from_local


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m installer",
        description="CBIM machine-level installer.",
    )
    sub = parser.add_subparsers(dest="command")

    # install
    p_install = sub.add_parser("install", help="Install a kernel version")
    p_install.add_argument(
        "version",
        nargs="?",
        help="Version to install from GitHub (omit for latest)",
    )
    p_install.add_argument(
        "--local",
        metavar="PATH",
        help="Install from local kernel/ directory instead of GitHub",
    )
    p_install.add_argument(
        "--set-default",
        action="store_true",
        dest="set_default",
        help="Set the installed version as active_default",
    )

    # use
    p_use = sub.add_parser("use", help="Switch the active default kernel version")
    p_use.add_argument("version", help="Version to activate (must be installed)")

    # uninstall
    p_uninstall = sub.add_parser("uninstall", help="Remove an installed kernel version")
    p_uninstall.add_argument("version", help="Version to remove")
    p_uninstall.add_argument(
        "--force",
        action="store_true",
        help="Remove even if it is the active_default",
    )

    # pin
    p_pin = sub.add_parser(
        "pin",
        help="Pin the current project to a specific kernel version (writes .cbim/config.json)",
    )
    p_pin.add_argument("version", help="Version to pin (must be installed)")

    # list
    sub.add_parser("list", help="List installed kernel versions")

    # version
    p_ver = sub.add_parser("version", help="Show installer + installed kernels")
    p_ver.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit machine-readable JSON to stdout",
    )
    # versions is an alias
    p_vers = sub.add_parser("versions", help="Alias for 'version'")
    p_vers.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit machine-readable JSON to stdout",
    )

    return parser


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _cmd_install(args: argparse.Namespace) -> int:
    if args.local:
        src = Path(args.local).resolve()
        install_from_local(src, version=args.version)
        return 0
    try:
        install_from_github(version=args.version, set_default=args.set_default)
    except (RuntimeError, OSError) as exc:
        sys.stderr.write("[cbim] install failed: {}\n".format(exc))
        return 1
    return 0


def _cmd_use(args: argparse.Namespace) -> int:
    installed = registry.list_installed()
    if args.version not in installed:
        sys.stderr.write(
            "[cbim] version '{}' is not installed. "
            "Run: cbim install {}\n".format(args.version, args.version)
        )
        return 1
    registry.set_default(args.version)
    print("[cbim] active_default -> {}".format(args.version))
    return 0


def _find_cbim_project_root() -> Optional[Path]:
    """Walk up from cwd looking for the .cbim/config.json marker."""
    cur = Path.cwd().resolve()
    for _ in range(40):
        if (cur / ".cbim" / "config.json").is_file():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def _cmd_pin(args: argparse.Namespace) -> int:
    """Pin <project>/.cbim/config.json to a specific kernel version."""
    import json as _json

    project_root = _find_cbim_project_root()
    if project_root is None:
        sys.stderr.write(
            "[cbim] not a CBIM project (no .cbim/config.json found in cwd or any parent).\n"
            "       Run 'cbim init' first.\n"
        )
        return 1

    installed = registry.list_installed()
    if args.version not in installed:
        sys.stderr.write(
            "[cbim] version '{}' is not installed. "
            "Run: cbim install {}\n".format(args.version, args.version)
        )
        return 1

    cfg_path = project_root / ".cbim" / "config.json"
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = _json.load(f)
    except (OSError, _json.JSONDecodeError) as exc:
        sys.stderr.write("[cbim] failed to read {}: {}\n".format(cfg_path, exc))
        return 1

    old_version = cfg.get("cbim_version", "<unset>")
    if old_version == args.version:
        print("[cbim] {} already pinned to {}".format(project_root, args.version))
        return 0

    cfg["cbim_version"] = args.version
    payload = _json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
    cfg_path.write_text(payload, encoding="utf-8")

    print("[cbim] {} : cbim_version {} -> {}".format(project_root, old_version, args.version))
    return 0


def _cmd_uninstall(args: argparse.Namespace) -> int:
    version = args.version
    installed = registry.list_installed()
    if version not in installed:
        sys.stderr.write("[cbim] version '{}' is not installed.\n".format(version))
        return 1

    current_default = registry.get_default()
    if version == current_default and not args.force:
        sys.stderr.write(
            "[cbim] '{}' is the active_default. "
            "Use 'cbim use <other>' first, or pass --force.\n".format(version)
        )
        return 1

    kernel_path = registry.get_kernel_path(version)
    if kernel_path and kernel_path.is_dir():
        shutil.rmtree(str(kernel_path))
        print("[cbim] removed {}".format(kernel_path))

    # Remove from registry
    data = registry.load()
    data["installed"].pop(version, None)
    if data.get("active_default") == version:
        data["active_default"] = None
    registry.save(data)
    print("[cbim] uninstalled kernel {}".format(version))
    return 0


def _cmd_list(_args: argparse.Namespace) -> int:
    versions = registry.list_installed()
    if not versions:
        print("(no kernels installed)")
        return 0
    default = registry.get_default()
    for v in versions:
        marker = " *" if v == default else ""
        print("{}{}".format(v, marker))
    return 0


def _cmd_version(args: argparse.Namespace) -> int:
    from installer.paths import install_root
    from installer.venv_mgr import is_provisioned, venv_path

    if getattr(args, "as_json", False):
        return _cmd_version_json()

    print("cbim installer (stdlib)")
    print("install root: {}".format(registry.cbim_home()))
    default = registry.get_default()
    print("active_default: {}".format(default or "(none)"))
    versions = registry.list_installed()
    if not versions:
        print("installed: (none)")
    else:
        print("installed:")
        data = registry.load()
        for v in versions:
            entry = data["installed"].get(v, {})
            marker = " *" if v == default else ""
            print(
                "  {}{}: {}  [source={}, installed_at={}]".format(
                    v,
                    marker,
                    entry.get("kernel_path", "?"),
                    entry.get("source", "?"),
                    entry.get("installed_at", "?"),
                )
            )
    print(
        "venv: {}  ({})".format(
            venv_path(),
            "provisioned" if is_provisioned() else "not provisioned",
        )
    )
    return 0


def _cmd_version_json() -> int:
    """Emit installer state as JSON.

    Stable machine-readable read surface consumed by
    ``cbim_kernel.project.upgrade.app_state``. Schema is additive — never
    rename or remove existing keys without coordinating with consumers.
    """
    import json as _json
    from installer.paths import install_root
    from installer.venv_mgr import is_provisioned, venv_path

    try:
        data = registry.load()
    except Exception as exc:  # noqa: BLE001 — top-level CLI boundary
        sys.stderr.write("[cbim] failed to read versions registry: {}\n".format(exc))
        return 1

    payload = {
        "install_root": str(install_root()),
        "active_default": data.get("active_default"),
        "installed": data.get("installed", {}),
        "venv": {
            "path": str(venv_path()),
            "provisioned": bool(is_provisioned()),
        },
    }
    sys.stdout.write(_json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "install":
        return _cmd_install(args)
    if args.command == "use":
        return _cmd_use(args)
    if args.command == "pin":
        return _cmd_pin(args)
    if args.command == "uninstall":
        return _cmd_uninstall(args)
    if args.command == "list":
        return _cmd_list(args)
    if args.command in ("version", "versions"):
        return _cmd_version(args)

    parser.print_help()
    return 0
