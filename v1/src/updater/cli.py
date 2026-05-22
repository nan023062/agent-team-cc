"""argparse CLI for ``python -m updater``."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Optional, Sequence

from updater import registry
from updater.install import install_from_github, install_from_local


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m updater",
        description="CBIM machine-level updater.",
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
        "--no-set-default",
        action="store_false",
        dest="set_default",
        default=True,
        help="Install without activating as active_default "
        "(default: activate after install)",
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
        help="Pin the current project to a specific kernel version (writes .cbim/.pin)",
    )
    p_pin.add_argument("version", help="Version to pin (must be installed)")

    # list
    sub.add_parser("list", help="List installed kernel versions")

    # version
    p_ver = sub.add_parser("version", help="Show updater + installed kernels")
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

    # upgrade check / apply (the upgrade module registers its own subparsers).
    from updater.upgrade.cli import build_parser as _build_upgrade_parser
    _build_upgrade_parser(sub)

    # Top-level shortcuts: check / apply / update map straight onto the upgrade
    # module so `python -m updater check` works without the `upgrade` prefix
    # (the kernel-side facade forwards bare subcommand names).
    p_check_top = sub.add_parser("check", help="Alias for `upgrade check`")
    p_check_top.add_argument("--json", action="store_true", dest="as_json")
    p_check_top.add_argument("--no-network", action="store_true", dest="no_network")
    p_check_top.add_argument("--refresh-cache", action="store_true", dest="refresh_cache")

    p_apply_top = sub.add_parser("apply", help="Alias for `upgrade apply`")
    p_apply_top.add_argument("--to", required=True, dest="target")
    p_apply_top.add_argument("--source", default="github",
                             choices=["local", "git", "github"])
    p_apply_top.add_argument("--from", default=None, dest="source_from")
    p_apply_top.add_argument("--dry-run", action="store_true", dest="dry_run")

    p_update = sub.add_parser("update", help="Update CBIM to the latest available version")
    p_update.add_argument("--dry-run", action="store_true", dest="dry_run")
    p_update.add_argument("-y", "--yes", action="store_true", dest="yes")

    p_migrate = sub.add_parser("migrate", help="Migrate project schema to a kernel version")
    p_migrate.add_argument("--version", default=None)
    p_migrate.add_argument("--dry-run", action="store_true", dest="dry_run")
    p_migrate.add_argument("--force", action="store_true")

    # release-notes
    p_notes = sub.add_parser(
        "release-notes",
        help="Print GitHub release notes for a kernel version",
    )
    p_notes.add_argument("version", help="Version tag (e.g. v2.1.0 or 2.1.0)")

    return parser


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _cmd_install(args: argparse.Namespace) -> int:
    if args.local:
        src = Path(args.local).resolve()
        install_from_local(
            src, version=args.version, set_default=args.set_default
        )
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
    """Walk up from cwd looking for the .cbim/ marker directory."""
    cur = Path.cwd().resolve()
    for _ in range(40):
        if (cur / ".cbim").is_dir():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def _write_pin(project_root: Path, version: str) -> None:
    """Atomic write of .cbim/.pin (plain text, single line, trailing newline)."""
    pin_path = project_root / ".cbim" / ".pin"
    pin_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = pin_path.with_suffix(".pin.tmp")
    tmp.write_text(str(version) + "\n", encoding="utf-8")
    tmp.replace(pin_path)


def _cmd_pin(args: argparse.Namespace) -> int:
    """Pin <project>/.cbim/.pin to a specific kernel version."""
    project_root = _find_cbim_project_root()
    if project_root is None:
        sys.stderr.write(
            "[cbim] not a CBIM project (no .cbim/ found in cwd or any parent).\n"
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

    _write_pin(project_root, args.version)
    print("[cbim] {} : pinned to {}".format(project_root, args.version))
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
    from updater.paths import install_root
    from updater.venv_mgr import is_provisioned, venv_path

    if getattr(args, "as_json", False):
        return _cmd_version_json()

    print("cbim updater (stdlib)")
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


def _find_project_root(start: Path) -> Optional[Path]:
    """Walk up looking for the .cbim/ marker directory."""
    for p in [start, *start.parents]:
        if (p / ".cbim").is_dir():
            return p
    return None


def _cmd_migrate(args: argparse.Namespace) -> int:
    from updater.migrate import migrate_project
    project_root = _find_project_root(Path.cwd())
    if project_root is None:
        sys.stderr.write("[cbim] not inside a CBIM project\n")
        return 1
    return migrate_project(
        project_root,
        version=args.version,
        dry_run=args.dry_run,
        force=args.force,
    )


def _cmd_release_notes(args: argparse.Namespace) -> int:
    """Print GitHub release notes for a given kernel version.

    Network failure or empty body degrades gracefully: prints a single
    fallback line pointing at the release page and exits 0 so callers
    (notably the `cbim_update` slash command) are never broken by
    release-notes unavailability.
    """
    raw = str(args.version).strip()
    bare = raw[1:] if raw.startswith("v") else raw
    fallback = (
        "(release notes unavailable - see "
        "https://github.com/nan023062/cbim/releases/tag/v{})".format(bare)
    )

    from updater.github import fetch_release

    try:
        data = fetch_release(bare)
    except Exception:  # noqa: BLE001 — any failure degrades to fallback
        print(fallback)
        return 0

    body = (data or {}).get("body") or ""
    body = body.strip()
    if not body:
        print(fallback)
        return 0

    print(body)
    return 0


def _cmd_version_json() -> int:
    """Emit updater state as JSON.

    Stable machine-readable read surface consumed by
    ``updater.upgrade.app_state``. Schema is additive — never
    rename or remove existing keys without coordinating with consumers.
    """
    import json as _json
    from updater.paths import install_root
    from updater.venv_mgr import is_provisioned, venv_path

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
    if args.command in ("check", "apply", "update"):
        from updater.upgrade import cli as upgrade_cli
        if args.command == "check":
            return upgrade_cli.cmd_check(args)
        if args.command == "apply":
            return upgrade_cli.cmd_apply(args)
        return upgrade_cli.cmd_update(args)
    if args.command == "migrate":
        return _cmd_migrate(args)
    if args.command == "release-notes":
        return _cmd_release_notes(args)
    if args.command == "upgrade":
        from updater.upgrade import cli as upgrade_cli
        sub_cmd = getattr(args, "upgrade_command", None)
        if sub_cmd == "check":
            return upgrade_cli.cmd_check(args)
        if sub_cmd == "apply":
            return upgrade_cli.cmd_apply(args)
        sys.stderr.write("usage: python -m updater upgrade {check,apply} [...]\n")
        return 1

    parser.print_help()
    return 0
