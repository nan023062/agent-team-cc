"""Launcher bootstrap — writes ``<install_root>/bin/`` entries."""
from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path

from installer.registry import cbim_home

_INSTALLER_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def bin_dir() -> Path:
    """Return path to ``<install_root>/bin/`` (lazy)."""
    return cbim_home() / "bin"

POSIX_LAUNCHER = '#!/bin/sh\nexec python3 "$(dirname "$0")/cbim_launcher.py" "$@"\n'

WINDOWS_LAUNCHER = (
    "@echo off\r\n"
    'python "%~dp0cbim_launcher.py" %*\r\n'
    "exit /b %errorlevel%\r\n"
)


def _write_text(path: Path, content: str, newline: str = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline=newline) as f:
        f.write(content)


def _make_executable(path: Path) -> None:
    if sys.platform == "win32":
        return
    st = path.stat()
    path.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_launcher(launcher_src: Path) -> Path:
    """Install the cbim launcher into ``<install_root>/bin/``.

    Copies ``cbim_launcher.py`` and writes both the POSIX and Windows wrappers
    so the same installation works regardless of which shell is used later.
    """
    launcher_src = Path(launcher_src).resolve()
    if not launcher_src.is_file():
        raise FileNotFoundError(
            "launcher source not found: {}".format(launcher_src)
        )

    bd = bin_dir()
    bd.mkdir(parents=True, exist_ok=True)

    dst_launcher = bd / "cbim_launcher.py"
    shutil.copyfile(str(launcher_src), str(dst_launcher))
    _make_executable(dst_launcher)

    posix_cbim = bd / "cbim"
    _write_text(posix_cbim, POSIX_LAUNCHER, newline="\n")
    _make_executable(posix_cbim)

    win_cbim = bd / "cbim.cmd"
    _write_text(win_cbim, WINDOWS_LAUNCHER, newline="")

    return bd


def copy_installer(installer_src: Path) -> Path:
    """Copy the installer package to ``<install_root>/installer/``.

    Called once during initial installation so the launcher can invoke
    ``python -m installer upgrade/install/use/...`` without requiring the
    original git checkout to be on disk.
    """
    installer_src = Path(installer_src).resolve()
    dst = cbim_home() / "installer"

    if dst.exists():
        shutil.rmtree(str(dst))

    shutil.copytree(str(installer_src), str(dst), ignore=_INSTALLER_IGNORE)
    print("[cbim] installer package -> {}".format(dst))
    return dst


def print_path_instructions(bin_path: Path) -> None:
    """Print OS-appropriate instructions for adding the bin dir to PATH."""
    bin_path = Path(bin_path)
    on_path = _is_on_path(bin_path)

    if on_path:
        print("[cbim] {} is already on PATH.".format(bin_path))
        return

    print("")
    print("[cbim] Add the launcher to your PATH:")
    if sys.platform == "win32":
        print('  setx PATH "%LOCALAPPDATA%\\Cbim-CC\\bin;%PATH%"')
        print("  (or via System Settings -> Advanced -> Environment Variables)")
        print("  Then open a new terminal so the change takes effect.")
    else:
        print('  export PATH="$HOME/.local/share/Cbim-CC/bin:$PATH"')
        print("  Add the above line to ~/.bashrc or ~/.zshrc to persist.")


def _is_on_path(bin_path: Path) -> bool:
    try:
        bin_path = bin_path.resolve()
    except OSError:
        return False
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        try:
            if Path(entry).resolve() == bin_path:
                return True
        except OSError:
            continue
    return False
