"""CLI surface for ``cbim upgrade`` (check + apply) and top-level ``cbim update``.

These handlers are reachable both via ``python -m updater <subcommand>`` and via
the kernel-side facade (``cbim_kernel.project.upgrade.cli``) which forwards to
``python -m updater``.
"""
from __future__ import annotations

import argparse
import json as _json
import subprocess
import sys
import time
from pathlib import Path

from updater.upgrade import app_state, notify
from updater.upgrade.apply_flow import run_apply
from updater.upgrade.diagnose import Command, Diagnosis, diagnose
from updater.upgrade.project_state import find_project_root, get_project_state
from updater.upgrade.remote import get_remote_state


def build_parser(subparsers) -> None:
    """Register the ``upgrade`` subcommand and its sub-subcommands."""
    p_up = subparsers.add_parser(
        "upgrade",
        help="Holistic version-state inspector (check) + app-side install repointer (apply)",
    )
    up_sub = p_up.add_subparsers(dest="upgrade_command")

    p_check = up_sub.add_parser("check", help="Diagnose the joint app + project state")
    p_check.add_argument("--json", action="store_true", dest="as_json",
                         help="Emit Diagnosis as JSON to stdout")
    p_check.add_argument("--no-network", action="store_true", dest="no_network",
                         help="Skip remote ls-remote")
    p_check.add_argument("--refresh-cache", action="store_true", dest="refresh_cache",
                         help="(internal) Also write .cbim/.upgrade_cache.json")

    p_apply = up_sub.add_parser("apply", help="Upgrade the app-side install in place")
    p_apply.add_argument("--to", required=True, dest="target",
                         help="Target version (required)")
    p_apply.add_argument("--source", default="github",
                         choices=["local", "git", "github"],
                         help="Where to fetch the target from (default: github)")
    p_apply.add_argument("--from", default=None, dest="source_from",
                         help="Override source location (path for local; URL for git/github)")
    p_apply.add_argument("--dry-run", action="store_true", dest="dry_run",
                         help="Print the plan; do not mutate anything")

    # Store the parser for help-printing.
    p_up.set_defaults(_upgrade_parser=p_up)


def cmd_check(args) -> int:
    """Diagnose, render, optionally update cache. Always exits 0 unless kernel broken."""
    project = get_project_state(Path.cwd())
    cfg = project.upgrade_config
    app = app_state.get_app_state()
    remote = get_remote_state(cfg, skip_network=bool(getattr(args, "no_network", False)))

    diagnosis = diagnose(app, project, remote)

    if getattr(args, "refresh_cache", False) and project.root is not None:
        try:
            notify.write_cache(project.root, _diagnosis_to_cache(diagnosis))
        except OSError as exc:
            sys.stderr.write("[cbim] failed to write upgrade cache: {}\n".format(exc))

    if getattr(args, "as_json", False):
        sys.stdout.write(_json.dumps(_diagnosis_to_json(diagnosis), indent=2, ensure_ascii=False) + "\n")
        return 0

    _print_human(diagnosis)
    return 0


def cmd_apply(args) -> int:
    project = get_project_state(Path.cwd())
    cfg = project.upgrade_config
    app = app_state.get_app_state()
    # Apply always wants live remote — it must confirm the target exists.
    remote = get_remote_state(cfg, skip_network=False)
    diagnosis = diagnose(app, project, remote)
    rc = run_apply(
        diagnosis,
        target_version=args.target,
        dry_run=bool(args.dry_run),
        source=getattr(args, "source", "github"),
        source_from=getattr(args, "source_from", None),
    )
    if rc == 0 and not bool(getattr(args, "dry_run", False)):
        project_root = find_project_root(Path.cwd())
        if project_root is not None:
            _write_pin(project_root, args.target)
            print("[cbim] project pin updated: .cbim/.pin = {}".format(args.target))
    return rc


def _version_key(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def _current_local_version(app) -> str:
    """The 'current' app version for update comparison.

    Prefers active_default (what's pinned as default on the install side);
    falls back to latest_local if no default is set.
    """
    return app.active_default or app.latest_local or ""


def cmd_update(args) -> int:
    """One-liner update to remote latest. See ``upgrade/.dna/module.md``.

    With ``--reinstall`` (alias ``--force``), refreshes the installed snapshot
    of the *current* pinned version instead of upgrading. This is the developer
    escape hatch for "source code changed but version was not bumped, snapshot
    is stale". When combined with ``--local PATH``, the refresh source is a
    local kernel directory rather than GitHub.
    """
    project = get_project_state(Path.cwd())
    cfg = project.upgrade_config
    app = app_state.get_app_state()

    reinstall = bool(getattr(args, "reinstall", False))
    local_src = getattr(args, "local", None)

    if local_src and not reinstall:
        sys.stderr.write("[cbim] --local requires --reinstall (or --force)\n")
        return 2

    # Network is required for normal update (target = remote latest) and for
    # --reinstall without --local (source = github). It is optional for
    # --reinstall --local (source = filesystem).
    skip_network = bool(local_src)
    remote = get_remote_state(cfg, skip_network=skip_network)
    diagnosis = diagnose(app, project, remote)

    current = _current_local_version(app)

    if reinstall:
        # Forced refresh of the currently installed version. No version
        # comparison; no remote-latest lookup required when --local is given.
        if not current:
            sys.stderr.write(
                "[cbim] --reinstall: no kernel currently installed; "
                "run `cbim install <version>` first\n"
            )
            return 1
        target_version = current

        if not local_src:
            # Going through the github path still needs a reachable remote so
            # invoke_updater() can download the tarball.
            if not remote.reachable:
                sys.stderr.write(
                    "[cbim] --reinstall: remote unreachable; "
                    "pass --local <path> to refresh from a local source\n"
                )
                return 3

        print("Reinstalling {} (forced)...".format(target_version))

        if bool(getattr(args, "dry_run", False)):
            return _run_reinstall(
                diagnosis, target_version,
                local_src=local_src, dry_run=True,
            )

        if not bool(getattr(args, "yes", False)) and sys.stdin.isatty():
            try:
                resp = input("Proceed? [y/N] ").strip().lower()
            except EOFError:
                resp = ""
            if resp not in ("y", "yes"):
                print("aborted.")
                return 0

        rc = _run_reinstall(
            diagnosis, target_version,
            local_src=local_src, dry_run=False,
        )
        if rc == 0:
            print("Installed kernel {}".format(target_version))
        return rc

    # ---- normal (non-reinstall) update path ----

    if not remote.reachable:
        sys.stderr.write("[cbim] remote unreachable; cannot check for updates\n")
        return 3
    if remote.latest is None:
        sys.stderr.write("[cbim] no release found on remote\n")
        return 3

    if current and remote.latest == current:
        print("Already up to date ({})".format(remote.latest))
        return 0
    if current and _version_key(current) > _version_key(remote.latest):
        print("Local version {} is ahead of remote {}; nothing to do.".format(
            current, remote.latest))
        return 0

    from_label = current or "(none)"
    print("Updating {} -> {}".format(from_label, remote.latest))

    if bool(getattr(args, "dry_run", False)):
        return run_apply(diagnosis, target_version=remote.latest, dry_run=True)

    if not bool(getattr(args, "yes", False)) and sys.stdin.isatty():
        try:
            resp = input("Proceed? [y/N] ").strip().lower()
        except EOFError:
            resp = ""
        if resp not in ("y", "yes"):
            print("aborted.")
            return 0

    target_version = remote.latest
    rc = run_apply(diagnosis, target_version=target_version, dry_run=False)
    if rc == 0:
        project_root_resolved = find_project_root(Path.cwd())
        if project_root_resolved is not None:
            _write_pin(project_root_resolved, target_version)
            print("[cbim] project pin updated: .cbim/.pin = {}".format(target_version))

            # Bug-B fix: kernel was upgraded but project schema may also need
            # migration (template/agents refresh + .gitignore patch + etc.).
            # Run `cbim migrate --force` to bring the project in line with the
            # newly-active kernel. Failures here do NOT change rc: the install
            # itself succeeded, and the user can always re-run migrate manually.
            migrate_rc = subprocess.run(
                [sys.executable, "-m", "cbim_kernel", "migrate",
                 "--version", str(target_version), "--force"],
                cwd=str(project_root_resolved),
            ).returncode
            if migrate_rc != 0:
                sys.stderr.write(
                    f"[cbim] update: kernel upgraded to {target_version} but "
                    f"project migrate failed (rc={migrate_rc}); "
                    f"run `cbim migrate --version {target_version}` manually\n"
                )
    return rc


# ---------------------------------------------------------------------------
# Project pin write (atomic)
# ---------------------------------------------------------------------------

def _run_reinstall(diagnosis, target_version: str,
                   local_src: "str | None", dry_run: bool) -> int:
    """Force-refresh the snapshot for *target_version*.

    Bypasses the standard apply flow (preflight, snapshot/rollback, remote
    confirmation) because the user has explicitly asked to overwrite the
    current install. Steps:
      1. Remove ``<install_root>/kernel/<target_version>/`` if it exists.
      2. Invoke the installer (local or github) to populate it fresh.

    Returns 0 on success, non-zero per install.py error semantics.
    """
    import shutil as _shutil
    from updater.install import install_from_github, install_from_local

    install_root = diagnosis.app.install_root
    if install_root is None:
        sys.stderr.write(
            "[cbim] --reinstall: no install root resolved; cannot proceed\n"
        )
        return 1

    snapshot_dir = install_root / "kernel" / target_version

    if dry_run:
        if local_src:
            print("[cbim] [dry-run] would remove {}".format(snapshot_dir))
            print("[cbim] [dry-run] would install from local {} as {}".format(
                local_src, target_version))
        else:
            print("[cbim] [dry-run] would remove {}".format(snapshot_dir))
            print("[cbim] [dry-run] would download+install {} from github".format(
                target_version))
        return 0

    if snapshot_dir.is_dir():
        try:
            _shutil.rmtree(str(snapshot_dir))
            print("Removed existing snapshot ({})".format(snapshot_dir))
        except OSError as exc:
            sys.stderr.write(
                "[cbim] --reinstall: failed to remove {}: {}\n".format(
                    snapshot_dir, exc)
            )
            return 1

    try:
        if local_src:
            src = Path(local_src).resolve()
            install_from_local(src, version=target_version)
        else:
            install_from_github(version=target_version)
    except (RuntimeError, OSError, FileNotFoundError) as exc:
        sys.stderr.write("[cbim] --reinstall: install failed: {}\n".format(exc))
        return 1

    return 0


def _write_pin(project_root: Path, version: str) -> None:
    """Atomic write of ``<project_root>/.cbim/.pin``.

    Format frozen: plain text, single line, trailing newline. Inlined here so
    the updater never imports from the kernel for this trivial write.
    """
    pin_path = project_root / ".cbim" / ".pin"
    pin_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = pin_path.with_suffix(".pin.tmp")
    tmp.write_text(version + "\n", encoding="utf-8")
    tmp.replace(pin_path)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _diagnosis_to_json(d: Diagnosis) -> dict:
    return {
        "scenario": d.scenario,
        "scenario_name": d.scenario_name,
        "app": {
            "install_root": str(d.app.install_root) if d.app.install_root else None,
            "installed_versions": d.app.installed_versions,
            "active_default": d.app.active_default,
            "latest_local": d.app.latest_local,
        },
        "project": {
            "root": str(d.project.root) if d.project.root else None,
            "pin": d.project.pin,
            "upgrade_config": d.project.upgrade_config.to_dict(),
        },
        "remote": {
            "url": d.remote.url,
            "latest": d.remote.latest,
            "reachable": d.remote.reachable,
        },
        "recommendation": d.recommendation,
        "commands": [{"shell": c.cmd, "description": c.description} for c in d.commands],
        "ordered": d.ordered,
    }


def _diagnosis_to_cache(d: Diagnosis) -> dict:
    target = d.remote.latest or d.app.latest_local
    update_available = bool(
        d.project.pin
        and target
        and d.project.pin != target
        and d.scenario in (3, 4, 5, 6)
    )
    return {
        "timestamp": time.time(),
        "scenario": d.scenario,
        "scenario_name": d.scenario_name,
        "project_pin": d.project.pin,
        "app_latest_local": d.app.latest_local,
        "remote_latest": d.remote.latest,
        "update_available": update_available,
    }


def _print_human(d: Diagnosis) -> None:
    out = sys.stdout.write
    out("[cbim upgrade check]\n")

    app_line = "  app    : "
    if d.app.install_root is None:
        app_line += "(installer state unavailable)"
    elif not d.app.installed:
        app_line += "(none installed)"
    else:
        parts = []
        if d.app.active_default:
            parts.append("{} installed (default)".format(d.app.active_default))
        if d.app.latest_local and d.app.latest_local != d.app.active_default:
            parts.append("{} available locally".format(d.app.latest_local))
        app_line += ", ".join(parts) if parts else ", ".join(d.app.installed_versions)
    out(app_line + "\n")

    proj_line = "  project: "
    if d.project.root is None:
        proj_line += "(not in a CBIM project)"
    elif d.project.pin is None:
        proj_line += "no pin set  (at {})".format(d.project.root)
    else:
        proj_line += "pinned to {}  (at {})".format(d.project.pin, d.project.root)
    out(proj_line + "\n")

    rem_line = "  remote : "
    cfg = d.project.upgrade_config
    if not d.remote.reachable:
        rem_line += "(unreachable) [{}, tag pattern {}]".format(
            d.remote.url, cfg.branch_or_tag_pattern
        )
    elif d.remote.latest is None:
        rem_line += "(no matching tag) [{}, tag pattern {}]".format(
            d.remote.url, cfg.branch_or_tag_pattern
        )
    else:
        rem_line += "{} ({}, tag pattern {})".format(
            d.remote.latest, d.remote.url, cfg.branch_or_tag_pattern
        )
    out(rem_line + "\n\n")

    out("Scenario {}: {}\n".format(d.scenario, d.scenario_name))
    out("  {}\n".format(d.recommendation))
    if not d.commands:
        return
    if d.ordered:
        out("  Run in order:\n")
        for i, c in enumerate(d.commands, 1):
            out("    {}) {}\n".format(i, c.cmd))
    else:
        out("  Suggested commands:\n")
        for c in d.commands:
            out("    - {}\n".format(c.cmd))
