"""`cbim migrate` — upgrade a kernel-in-project layout to the global-kernel model.

Lives in the updater package (not the kernel) so the migration path stays
available even when the project's pinned kernel cannot start. The kernel-side
``cbim migrate`` command is a thin subprocess facade onto ``python -m updater
migrate``.
"""
from __future__ import annotations

import json
import shutil
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from cbim_kernel.project import sync as project_sync

_AGENT_NAMES = project_sync.KERNEL_AGENT_NAMES

_KERNEL_DIRS = ["engine", "hooks", "mcp_server", "services", "dashboard", "cbi"]

_PIN_FILE = ".pin"


def _read_pin(project_root: Path) -> Optional[str]:
    """Inlined — format frozen: plain text, single line, trailing newline."""
    try:
        text = (project_root / ".cbim" / _PIN_FILE).read_text(encoding="utf-8").strip()
        return text if text else None
    except (OSError, UnicodeDecodeError):
        return None


def _write_pin(project_root: Path, version: str) -> None:
    """Atomic write of ``<project_root>/.cbim/.pin``.

    Format frozen: plain text, single line, trailing newline.
    """
    cbim_dir = project_root / ".cbim"
    cbim_dir.mkdir(parents=True, exist_ok=True)
    pin_path = cbim_dir / _PIN_FILE
    tmp = pin_path.with_suffix(".pin.tmp")
    tmp.write_text(version + "\n", encoding="utf-8")
    tmp.replace(pin_path)


def _is_old_layout(cbim_dir: Path) -> bool:
    """Return True if project has at least one old kernel code directory."""
    return any((cbim_dir / d).is_dir() for d in ["engine", "hooks", "mcp_server"])


def _create_backup(project_root: Path, cbim_dir: Path, dry_run: bool) -> Optional[Path]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"cbim_migration_backup_{ts}.tar.gz"
    backup_path = project_root / backup_name

    if dry_run:
        print(f"[cbim] [dry-run] would create backup -> {backup_name}")
        return backup_path

    print(f"[cbim] creating backup -> {backup_name}")
    with tarfile.open(backup_path, "w:gz") as tar:
        if cbim_dir.is_dir():
            tar.add(cbim_dir, arcname=".cbim")
        claude_settings = project_root / ".claude" / "settings.json"
        if claude_settings.is_file():
            tar.add(claude_settings, arcname=".claude/settings.json")

    size_kb = backup_path.stat().st_size // 1024
    print(f"[cbim] backup created ({size_kb} KB)")
    return backup_path


def _has_legacy_pin(cbim_dir: Path) -> bool:
    """True if ``config.json`` still carries the legacy ``cbim_version`` key."""
    cfg_path = cbim_dir / "config.json"
    if not cfg_path.is_file():
        return False
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return isinstance(cfg, dict) and "cbim_version" in cfg


def _inject_version(cbim_dir: Path, version: str, dry_run: bool) -> None:
    project_root = cbim_dir.parent
    current = _read_pin(project_root)
    if current == version:
        print(f"[cbim] .cbim/.pin already pinned to \"{version}\"")
        return

    if dry_run:
        print(f"[cbim] [dry-run] would write .cbim/.pin = \"{version}\"")
        return

    _write_pin(project_root, version)
    print(f"[cbim] wrote .cbim/.pin = \"{version}\"")


def _migrate_legacy_pin(cbim_dir: Path, dry_run: bool) -> None:
    """One-time compat: lift ``cbim_version`` out of ``config.json`` into ``.cbim/.pin``.

    No-op when ``config.json`` is missing, unreadable, or no longer contains the
    legacy key. Also ensures the project ``.gitignore`` lists ``.cbim/.pin``.
    """
    project_root = cbim_dir.parent
    cfg_path = cbim_dir / "config.json"
    if not cfg_path.is_file():
        return
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("[cbim] WARNING: config.json is not valid JSON; skipping legacy pin migration")
        return
    if not isinstance(cfg, dict) or "cbim_version" not in cfg:
        return

    legacy = cfg.get("cbim_version")
    if dry_run:
        print(
            f"[cbim] [dry-run] would lift cbim_version=\"{legacy}\" from config.json "
            "into .cbim/.pin and remove the key"
        )
        _ensure_pin_gitignored(project_root, dry_run=True)
        return

    if isinstance(legacy, str) and legacy.strip():
        _write_pin(project_root, legacy.strip())
        print(f"[cbim] lifted legacy cbim_version=\"{legacy.strip()}\" into .cbim/.pin")

    del cfg["cbim_version"]
    cfg_path.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("[cbim] removed cbim_version from config.json")

    _ensure_pin_gitignored(project_root, dry_run=False)


def _ensure_pin_gitignored(project_root: Path, dry_run: bool) -> None:
    entry = ".cbim/.pin"
    gi_path = project_root / ".gitignore"
    if gi_path.is_file():
        existing = gi_path.read_text(encoding="utf-8")
        if any(line.strip() == entry for line in existing.splitlines()):
            return
        if dry_run:
            print(f"[cbim] [dry-run] would append {entry} to .gitignore")
            return
        suffix = "" if existing.endswith("\n") or not existing else "\n"
        gi_path.write_text(existing + suffix + entry + "\n", encoding="utf-8")
        print(f"[cbim] appended {entry} to .gitignore")
        return

    if dry_run:
        print(f"[cbim] [dry-run] would create .gitignore with {entry}")
        return
    gi_path.write_text("# CBIM\n" + entry + "\n", encoding="utf-8")
    print(f"[cbim] created .gitignore with {entry}")


def _update_settings(project_root: Path, dry_run: bool) -> None:
    action = project_sync.sync_settings(project_root, dry_run=dry_run)
    prefix = "[cbim] [dry-run] " if dry_run else "[cbim] "
    print(f"{prefix}{action}")


def _update_agents(project_root: Path, dry_run: bool) -> None:
    prefix = "[cbim] [dry-run] " if dry_run else "[cbim] "
    for action in project_sync.sync_agents(project_root, dry_run=dry_run):
        print(f"{prefix}{action}")


def _update_commands(project_root: Path, dry_run: bool) -> None:
    prefix = "[cbim] [dry-run] " if dry_run else "[cbim] "
    for action in project_sync.sync_commands(project_root, dry_run=dry_run):
        print(f"{prefix}{action}")


def _remove_old_dirs(cbim_dir: Path, dry_run: bool) -> None:
    for d in _KERNEL_DIRS:
        target = cbim_dir / d
        if not target.is_dir():
            continue
        rel = f".cbim/{d}/"
        if dry_run:
            print(f"[cbim] [dry-run] would remove {rel}")
            continue
        shutil.rmtree(target)
        print(f"[cbim] removed {rel}")


def migrate_project(
    project_root: Path,
    version: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
) -> int:
    """Upgrade an old-layout CBIM project to the global-kernel model.

    Returns 0 on success, 1 on error / user-abort.
    """
    project_root = Path(project_root).resolve()
    cbim_dir = project_root / ".cbim"

    if version is None:
        # Fall back to the kernel's __version__ so callers can omit --version.
        try:
            from cbim_kernel import __version__ as _kernel_version
            version = _kernel_version
        except Exception:  # noqa: BLE001
            version = ""

    print(f"[cbim] Migrating project at {project_root}")
    print(f"[cbim] Target kernel version: {version}")

    if not cbim_dir.is_dir():
        print(f"[cbim] no .cbim/ directory found; nothing to migrate")
        return 0

    if not _is_old_layout(cbim_dir):
        # Layout is already global-kernel; this is a pure pin-bump path.
        # No backup tarball (no old kernel dirs to preserve) and no
        # confirmation prompt (config.json + settings + agents only).
        legacy_pending = _has_legacy_pin(cbim_dir)
        pin_matches = _read_pin(project_root) == version and not legacy_pending

        if pin_matches:
            settings_action = project_sync.sync_settings(project_root, dry_run=True)
            agent_actions = project_sync.sync_agents(project_root, dry_run=True)
            command_actions = project_sync.sync_commands(project_root, dry_run=True)
            if (
                settings_action.startswith("unchanged ")
                and all(a.startswith("unchanged ") for a in agent_actions)
                and all(a.startswith("unchanged ") for a in command_actions)
            ):
                print(f"[cbim] already aligned with .cbim/.pin = \"{version}\"; nothing to do")
                return 0

        _migrate_legacy_pin(cbim_dir, dry_run)
        _inject_version(cbim_dir, version, dry_run)
        _update_settings(project_root, dry_run)
        _update_agents(project_root, dry_run)
        _update_commands(project_root, dry_run)

        if dry_run:
            print("[cbim] --- DRY RUN complete ---")
        return 0

    if not (dry_run or force):
        print(
            f"[cbim] This will modify .cbim/, .claude/settings.json, "
            f".claude/agents/, and .claude/commands/."
        )
        print(f"[cbim] A full backup will be created at the project root first.")
        try:
            answer = input("[cbim] Proceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[cbim] Aborted.")
            return 1
        if answer not in ("y", "yes"):
            print("[cbim] Aborted.")
            return 1

    backup_path = _create_backup(project_root, cbim_dir, dry_run)

    _migrate_legacy_pin(cbim_dir, dry_run)
    _inject_version(cbim_dir, version, dry_run)
    _update_settings(project_root, dry_run)
    _update_agents(project_root, dry_run)
    _update_commands(project_root, dry_run)
    _remove_old_dirs(cbim_dir, dry_run)

    if dry_run:
        print("[cbim] --- DRY RUN complete ---")
        return 0

    print("[cbim] Migration complete!")
    if backup_path is not None:
        print(f"[cbim] Backup saved to {backup_path.name}")
    print("[cbim] Restart Claude Code in this directory to use the new kernel.")
    return 0
