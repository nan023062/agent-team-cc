"""`cbim init` — bootstrap a new CBIM project."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
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


def _install_venv(project_root: Path, force: bool) -> None:
    """Build .cbim/.venv/ and install `mcp` into it. Idempotent.

    The managed venv is the canonical Python environment for every CBIM
    runtime invocation: shims under `.cbim/run` point at `.venv/bin/python`,
    the MCP server is launched out of it, and any future Python deps land
    here. Bootstrapped once with the system `python3`; thereafter the user's
    system Python is never touched.

    Healthy-skip path: if `.venv/bin/python -c 'import mcp'` exits 0 and
    `force` is False, do nothing. Otherwise (venv missing, venv broken, or
    mcp missing inside an otherwise-healthy venv) repair the missing piece.

    Venv build failure is fatal (clear hint about `python3-venv`). Mcp pip
    install failure is soft-fail (venv survives; user can re-run init or
    install mcp manually) — but we never silently swallow the error.
    """
    venv_dir = project_root / ".cbim" / ".venv"
    # POSIX layout; Windows is `Scripts/python.exe`.
    if os.name == "nt":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    if venv_python.exists() and not force:
        probe = subprocess.run(
            [str(venv_python), "-c", "import mcp"],
            capture_output=True, text=True,
        )
        if probe.returncode == 0:
            _print("skipped (already up to date)", venv_dir, project_root)
            return
        # Venv is healthy but mcp is missing — fall through to pip install.

    if not venv_python.exists():
        bootstrap_python = shutil.which("python3") or shutil.which("python")
        if bootstrap_python is None:
            raise SystemExit(
                "neither `python3` nor `python` was found on PATH; "
                "cannot bootstrap .cbim/.venv/"
            )
        result = subprocess.run(
            [bootstrap_python, "-m", "venv", str(venv_dir)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise SystemExit(
                f"failed to create venv at {venv_dir}: {result.stderr.strip()}\n"
                f"  Hint: ensure the bootstrap python has the `venv` module "
                f"(e.g. `apt install python3-venv` on Debian/Ubuntu)."
            )
        _print("created", venv_dir, project_root)

    result = subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--quiet", "mcp"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(
            f"[cbim] WARNING: failed to install `mcp` into {venv_dir}: "
            f"{result.stderr.strip()}\n"
            f"  Manual fix: {venv_python} -m pip install mcp",
            file=sys.stderr,
        )
        return
    _print("installed mcp", venv_dir, project_root)


def _install_run_shim(project_root: Path, force: bool) -> None:
    """Write the .cbim/run launcher shims (POSIX + Windows).

    Both files are rewritten on every install (force has no effect — the shim
    is a derivative of the on-disk layout). The shims resolve their own
    directory at runtime and exec the venv-managed `python` next door at
    `.venv/`, so no absolute interpreter path is baked in — `.cbim/` is
    self-contained and portable. The POSIX shim is mode 0755.

    Requires `_install_venv()` to have run first; the shim trusts that the
    venv exists at the resolved relative path.
    """
    cbim_dir = project_root / ".cbim"
    cbim_dir.mkdir(parents=True, exist_ok=True)

    posix_path = cbim_dir / "run"
    # Flat layout: `python <file>` would treat the entry file as __main__ with
    # no parent package, so `from .X import Y` inside engine/ would fail. We
    # set PYTHONPATH to the install root and invoke via `python -m engine`,
    # which routes through engine/__main__.py → engine.cli.main() with the
    # `engine` package properly bound so relative imports resolve.
    posix_content = (
        '#!/bin/sh\n'
        'DIR="$(cd "$(dirname "$0")" && pwd)"\n'
        'export PYTHONPATH="$DIR/kernel${PYTHONPATH:+:$PYTHONPATH}"\n'
        'exec "$DIR/.venv/bin/python" -m engine "$@"\n'
    )
    posix_path.write_text(posix_content, encoding="utf-8")
    os.chmod(posix_path, 0o755)
    _print("created", posix_path, project_root)

    win_path = cbim_dir / "run.cmd"
    win_content = (
        '@echo off\r\n'
        'setlocal\r\n'
        'set "DIR=%~dp0"\r\n'
        'set "PYTHONPATH=%DIR%kernel;%PYTHONPATH%"\r\n'
        '"%DIR%.venv\\Scripts\\python.exe" -m engine %*\r\n'
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


def _install_hook_scripts(project_root: Path, force: bool) -> None:
    """Install (or refresh) the 7 cbim_*.py hook scripts + _lib/ into .claude/hooks/.

    Always refreshes from source — `force` has no effect. Rationale: the hook
    scripts are derivatives of the kernel under .cbim/kernel/ and must stay in
    lockstep with it. Idempotent (re-running yields byte-identical output).
    """
    actions = _sync.sync_hook_scripts(project_root, dry_run=False)
    for action in actions:
        print(f"[cbim] {action}")


def _check_mcp_sdk(project_root: Path) -> None:
    """Verify `mcp` is importable from the managed venv. Diagnostic only.

    `_install_venv()` already builds the venv and installs `mcp` into it as
    part of the install flow. This probe runs at the end of init purely as
    a post-condition check: if mcp is still missing here, the install is
    incomplete and the MCP server will not start. Soft-fail (warn, don't
    abort) so the user keeps the rest of a successful init.
    """
    if os.name == "nt":
        venv_python = project_root / ".cbim" / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = project_root / ".cbim" / ".venv" / "bin" / "python"

    if not venv_python.exists():
        # _install_venv either hasn't run or failed; the venv-build path
        # already raised/warned. Don't double-report.
        return

    try:
        res = subprocess.run(
            [str(venv_python), "-c", "import mcp"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return

    if res.returncode == 0:
        print(f"[cbim] verified `mcp` SDK present in {venv_python}")
        return

    print(
        f"[cbim] WARNING: `mcp` not importable from {venv_python}; "
        f"MCP server will not start. Run: {venv_python} -m pip install mcp",
        file=sys.stderr,
    )


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


def _install_mcp_json(project_root: Path, force: bool) -> None:
    # sync_mcp_json merges idempotently; force has no effect on merge semantics.
    mcp_path = project_root / ".mcp.json"
    pre_existed = mcp_path.exists()
    action = _sync.sync_mcp_json(project_root, dry_run=False)
    if pre_existed and action.startswith("unchanged") and not force:
        _print("skipped (already up to date)", mcp_path, project_root)
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
    # sync_claudeignore is now append-missing-only (like .gitignore); the merge
    # is always safe so `force` has no effect.
    ci_path = project_root / ".claudeignore"
    pre_existed = ci_path.exists()
    action = _sync.sync_claudeignore(project_root, dry_run=False)
    if pre_existed and action.startswith("unchanged"):
        _print("skipped (already up to date)", ci_path, project_root)
        return
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
    # MUST come before the shim — the shim hard-codes the venv-relative
    # python path and assumes `.cbim/.venv/` already exists.
    _install_venv(project_root, force)
    _install_run_shim(project_root, force)
    _install_agents(project_root, force)
    _install_commands(project_root, force)
    _install_hook_scripts(project_root, force)
    _install_settings(project_root, force)
    _install_mcp_json(project_root, force)
    _install_claude_md(project_root, force)
    _install_claudeignore(project_root, force)
    _patch_gitignore(project_root)
    _check_mcp_sdk(project_root)

    print("[cbim] Done! Start Claude Code in this directory.")
