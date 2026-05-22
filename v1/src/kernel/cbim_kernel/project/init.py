"""`cbim init` — bootstrap a new CBIM project."""
from __future__ import annotations

from pathlib import Path

from cbim_kernel.project import sync as _sync
from cbim_kernel.project.pin import write_pin

_TEMPLATES = _sync._TEMPLATES
_AGENT_NAMES = _sync.KERNEL_AGENT_NAMES


def _read_template(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def _print(action: str, path: Path, root: Path) -> None:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    rel_str = str(rel).replace("\\", "/")
    if path.is_dir() and not rel_str.endswith("/"):
        rel_str += "/"
    print(f"[cbim] {action} {rel_str}")


def _ensure_dir(path: Path, root: Path) -> None:
    if path.exists():
        _print("skipped (exists)", path, root)
        return
    path.mkdir(parents=True, exist_ok=True)
    _print("created", path, root)


def _install_config(project_root: Path, version: str, force: bool) -> None:
    cfg_path = project_root / ".cbim" / "config.json"
    if cfg_path.exists() and not force:
        _print("skipped (exists)", cfg_path, project_root)
        return
    content = _read_template("config.json.tmpl")
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(content, encoding="utf-8")
    _print("created", cfg_path, project_root)


def _install_pin(project_root: Path, version: str, force: bool) -> None:
    pin_path = project_root / ".cbim" / ".pin"
    if pin_path.exists() and not force:
        _print("skipped (exists)", pin_path, project_root)
        return
    write_pin(project_root, version)
    _print("created", pin_path, project_root)


def _install_agents(project_root: Path, force: bool) -> None:
    for name in _AGENT_NAMES:
        dst = project_root / ".claude" / "agents" / name / f"{name}.md"
        if dst.exists() and not force:
            _print("skipped (exists)", dst, project_root)
            continue
        # Delegate to sync's always-overwrite primitive.
        action = _sync.sync_agent(project_root, name, dry_run=False)
        print(f"[cbim] {action}")


def _install_settings(project_root: Path, force: bool) -> None:
    # sync_settings already merges idempotently; force has no effect on merge
    # semantics (the merge is always safe).
    settings_path = project_root / ".claude" / "settings.json"
    pre_existed = settings_path.exists()
    action = _sync.sync_settings(project_root, dry_run=False)
    # If the file already existed AND nothing changed AND not forcing, mirror
    # the historical "skipped (already up to date)" phrasing.
    if pre_existed and action.startswith("unchanged") and not force:
        _print("skipped (already up to date)", settings_path, project_root)
        return
    print(f"[cbim] {action}")


def _install_claude_md(project_root: Path, force: bool) -> None:
    dst = project_root / "CLAUDE.md"
    if dst.exists() and not force:
        _print("skipped (exists)", dst, project_root)
        return
    action = _sync.sync_claude_md(project_root, dry_run=False)
    print(f"[cbim] {action}")


def _install_claudeignore(project_root: Path, force: bool) -> None:
    dst = project_root / ".claudeignore"
    if dst.exists() and not force:
        _print("skipped (exists)", dst, project_root)
        return
    action = _sync.sync_claudeignore(project_root, dry_run=False)
    print(f"[cbim] {action}")


def _patch_gitignore(project_root: Path) -> None:
    gi_path = project_root / ".gitignore"
    pre_existed = gi_path.exists()
    action = _sync.sync_gitignore(project_root, dry_run=False)
    if pre_existed and action.startswith("unchanged"):
        _print("skipped (already up to date)", gi_path, project_root)
        return
    print(f"[cbim] {action}")


def init_project(project_root: Path, version: str, force: bool = False) -> None:
    """Bootstrap a new CBIM project at project_root.

    Idempotent: existing files are not overwritten unless force=True. The
    .claude/settings.json file is merged, and .gitignore is patched, regardless
    of force.
    """
    project_root = Path(project_root).resolve()
    print(f"[cbim] Initializing CBIM project at {project_root}")

    _install_config(project_root, version, force)
    _ensure_dir(project_root / ".cbim" / "logs", project_root)
    _ensure_dir(project_root / ".cbim" / "memory" / "short", project_root)
    _ensure_dir(project_root / ".cbim" / "memory" / "medium", project_root)
    _install_pin(project_root, version, force)
    _install_agents(project_root, force)
    _install_settings(project_root, force)
    _install_claude_md(project_root, force)
    _install_claudeignore(project_root, force)
    _patch_gitignore(project_root)

    print("[cbim] Done! Start Claude Code in this directory.")
