"""`cbim init` — bootstrap a new CBIM project."""
from __future__ import annotations

from pathlib import Path

from . import sync as _sync

_TEMPLATES = _sync._TEMPLATES
_AGENT_NAMES = _sync.KERNEL_AGENT_NAMES
_COMMAND_NAMES = _sync.KERNEL_COMMAND_NAMES


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


def _install_config(project_root: Path, force: bool) -> None:
    cfg_path = project_root / ".cbim" / "config.json"
    if cfg_path.exists() and not force:
        _print("skipped (exists)", cfg_path, project_root)
        return
    content = _read_template("config.json.tmpl")
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(content, encoding="utf-8")
    _print("created", cfg_path, project_root)


def _install_run_shim(project_root: Path, force: bool) -> None:
    """Write the .cbim/run launcher shims (POSIX + Windows).

    Both files are rewritten on every install (force has no effect — the shim
    is a derivative of the kernel install path, which can change between
    installs). The POSIX shim is mode 0755.
    """
    import os
    import shutil

    cbim_dir = project_root / ".cbim"
    cbim_dir.mkdir(parents=True, exist_ok=True)

    # The shim invokes whatever kernel sits next to it under
    # <project_root>/.cbim/kernel/. The path is computed at install time; if
    # the kernel is moved, re-run /cbim_install to refresh.
    install_root_posix = project_root / ".cbim" / "kernel"
    install_root_win = str(install_root_posix).replace("/", "\\")

    # Probe the Python interpreter at install time. Modern macOS / Debian /
    # Ubuntu ship `python3` only — a bare `python` exec will ENOENT. Bake the
    # absolute path into the shim so the shim is self-contained.
    python_exe = shutil.which("python3") or shutil.which("python")
    if python_exe is None:
        raise SystemExit(
            "neither `python3` nor `python` was found on PATH; "
            "cannot generate the .cbim/run shim"
        )

    posix_path = cbim_dir / "run"
    # Flat layout: `python <file>` would treat the entry file as __main__ with
    # no parent package, so `from .X import Y` inside engine/ would fail. We
    # set PYTHONPATH to the install root and invoke via `python -m engine`,
    # which routes through engine/__main__.py → engine.cli.main() with the
    # `engine` package properly bound so relative imports resolve.
    posix_content = (
        f'#!/bin/sh\n'
        f'export PYTHONPATH="{install_root_posix}${{PYTHONPATH:+:$PYTHONPATH}}"\n'
        f'exec "{python_exe}" -m engine "$@"\n'
    )
    posix_path.write_text(posix_content, encoding="utf-8")
    os.chmod(posix_path, 0o755)
    _print("created", posix_path, project_root)

    win_path = cbim_dir / "run.cmd"
    # On Windows the install-time probe usually finds `python` (py-launcher or
    # python.org installer). We still write the absolute path baked in.
    win_content = (
        f'@echo off\n'
        f'set "PYTHONPATH={install_root_win};%PYTHONPATH%"\n'
        f'"{python_exe}" -m engine %*\n'
    )
    win_path.write_text(win_content, encoding="utf-8")
    _print("created", win_path, project_root)


def _install_agents(project_root: Path, force: bool) -> None:
    for name in _AGENT_NAMES:
        dst = project_root / ".claude" / "agents" / name / f"{name}.md"
        if dst.exists() and not force:
            _print("skipped (exists)", dst, project_root)
            continue
        # Delegate to sync's always-overwrite primitive.
        action = _sync.sync_agent(project_root, name, dry_run=False)
        print(f"[cbim] {action}")


def _install_commands(project_root: Path, force: bool) -> None:
    for name in _COMMAND_NAMES:
        dst = project_root / ".claude" / "commands" / f"{name}.md"
        if dst.exists() and not force:
            _print("skipped (exists)", dst, project_root)
            continue
        # Delegate to sync's always-overwrite primitive.
        action = _sync.sync_command(project_root, name, dry_run=False)
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


def init_project(project_root: Path, force: bool = False) -> None:
    """Bootstrap a new CBIM project at project_root.

    Idempotent: existing files are not overwritten unless force=True. The
    .claude/settings.json file is merged, and .gitignore is patched, regardless
    of force. The .cbim/run shim is always (re)written.
    """
    project_root = Path(project_root).resolve()
    print(f"[cbim] Initializing CBIM project at {project_root}")

    _install_config(project_root, force)
    _ensure_dir(project_root / ".cbim" / "logs", project_root)
    _ensure_dir(project_root / ".cbim" / "memory" / "short", project_root)
    _ensure_dir(project_root / ".cbim" / "memory" / "medium", project_root)
    _install_run_shim(project_root, force)
    _install_agents(project_root, force)
    _install_commands(project_root, force)
    _install_settings(project_root, force)
    _install_claude_md(project_root, force)
    _install_claudeignore(project_root, force)
    _patch_gitignore(project_root)

    print("[cbim] Done! Start Claude Code in this directory.")
