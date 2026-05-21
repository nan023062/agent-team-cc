"""`cbim migrate` — upgrade a kernel-in-project layout to the global-kernel model."""
from __future__ import annotations

import json
import shutil
import tarfile
from datetime import datetime
from pathlib import Path

from cbim_kernel.project import sync as _sync

_AGENT_NAMES = _sync.KERNEL_AGENT_NAMES

_KERNEL_DIRS = ["engine", "hooks", "mcp_server", "services", "dashboard", "cbi"]


def _is_old_layout(cbim_dir: Path) -> bool:
    """Return True if project has at least one old kernel code directory."""
    return any((cbim_dir / d).is_dir() for d in ["engine", "hooks", "mcp_server"])


def _create_backup(project_root: Path, cbim_dir: Path, dry_run: bool) -> Path | None:
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


def _inject_version(cbim_dir: Path, version: str, dry_run: bool) -> None:
    cfg_path = cbim_dir / "config.json"
    if not cfg_path.is_file():
        if dry_run:
            print(f"[cbim] [dry-run] would create config.json with cbim_version=\"{version}\"")
        else:
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(
                json.dumps({"cbim_version": version}, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"[cbim] created config.json with cbim_version=\"{version}\"")
        return

    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"[cbim] WARNING: config.json is not valid JSON; skipping version injection")
        return

    if cfg.get("cbim_version") == version:
        print(f"[cbim] config.json already pinned to cbim_version=\"{version}\"")
        return

    if dry_run:
        print(f"[cbim] [dry-run] would inject cbim_version=\"{version}\" into config.json")
        return

    cfg["cbim_version"] = version
    cfg_path.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[cbim] injected cbim_version=\"{version}\" into config.json")


def _update_settings(project_root: Path, dry_run: bool) -> None:
    action = _sync.sync_settings(project_root, dry_run=dry_run)
    prefix = "[cbim] [dry-run] " if dry_run else "[cbim] "
    print(f"{prefix}{action}")


def _update_agents(project_root: Path, dry_run: bool) -> None:
    prefix = "[cbim] [dry-run] " if dry_run else "[cbim] "
    for action in _sync.sync_agents(project_root, dry_run=dry_run):
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
    version: str,
    dry_run: bool = False,
    force: bool = False,
) -> int:
    """Upgrade an old-layout CBIM project to the global-kernel model.

    Returns 0 on success, 1 on error / user-abort.
    """
    project_root = Path(project_root).resolve()
    cbim_dir = project_root / ".cbim"

    print(f"[cbim] Migrating project at {project_root}")
    print(f"[cbim] Target kernel version: {version}")

    if not cbim_dir.is_dir():
        print(f"[cbim] no .cbim/ directory found; nothing to migrate")
        return 0

    if not _is_old_layout(cbim_dir):
        print(f"[cbim] already on global-kernel layout")
        return 0

    if not (dry_run or force):
        print(f"[cbim] This will modify .cbim/, .claude/settings.json, and .claude/agents/.")
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

    _inject_version(cbim_dir, version, dry_run)
    _update_settings(project_root, dry_run)
    _update_agents(project_root, dry_run)
    _remove_old_dirs(cbim_dir, dry_run)

    if dry_run:
        print("[cbim] --- DRY RUN complete ---")
        return 0

    print("[cbim] Migration complete!")
    if backup_path is not None:
        print(f"[cbim] Backup saved to {backup_path.name}")
    print("[cbim] Restart Claude Code in this directory to use the new kernel.")
    return 0
