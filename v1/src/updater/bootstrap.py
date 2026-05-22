"""Launcher bootstrap — writes ``<install_root>/bin/`` entries."""
from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path

from updater.registry import cbim_home

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


def copy_updater(updater_src: Path) -> Path:
    """Copy the updater package to ``<install_root>/updater/``.

    Called once during initial installation so the launcher can invoke
    ``python -m updater upgrade/install/use/...`` without requiring the
    original git checkout to be on disk.
    """
    updater_src = Path(updater_src).resolve()
    dst = cbim_home() / "updater"

    if dst.exists():
        shutil.rmtree(str(dst))

    shutil.copytree(str(updater_src), str(dst), ignore=_INSTALLER_IGNORE)
    print("[cbim] updater package -> {}".format(dst))
    return dst


def ensure_on_path(bin_path: Path) -> None:
    """Add bin_path to user PATH if not already present. Idempotent. Never raises."""
    bin_path = Path(bin_path)

    if _is_on_path(bin_path):
        print("[cbim] {} is already on PATH.".format(bin_path))
        return

    try:
        if sys.platform == "win32":
            _ensure_on_path_windows(bin_path)
        else:
            _ensure_on_path_posix(bin_path)
    except Exception as exc:  # noqa: BLE001
        print("[cbim] WARNING: could not update PATH automatically: {}".format(exc))
        _print_path_fallback(bin_path)
        return

    os.environ["PATH"] = "{}{}{}".format(
        str(bin_path), os.pathsep, os.environ.get("PATH", "")
    )
    print("[cbim] Added {} to user PATH.".format(bin_path))
    print("[cbim] Open a new terminal for 'cbim' to be available.")


def _print_path_fallback(bin_path: Path) -> None:
    bin_path = Path(bin_path)
    if sys.platform == "win32":
        launcher = bin_path / "cbim.cmd"
        print("  Run manually:  {}".format(launcher))
        print("  Or add to PATH: {}".format(bin_path))
    else:
        launcher = bin_path / "cbim"
        print("  Run manually:  {}".format(launcher))
        print("  Or add to PATH: {}".format(bin_path))


def _ensure_on_path_windows(bin_path: Path) -> None:
    import ctypes
    import winreg  # type: ignore[import-not-found]

    bin_str = str(bin_path)

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE
    ) as key:
        try:
            current, value_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current = ""
            value_type = winreg.REG_EXPAND_SZ

        entries = [e for e in current.split(";") if e]
        bin_lower = bin_str.lower()
        for entry in entries:
            if entry.rstrip("\\").lower() == bin_lower.rstrip("\\"):
                return

        new_value = bin_str + (";" + current if current else "")
        winreg.SetValueEx(key, "Path", 0, value_type, new_value)

    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    result = ctypes.c_long()
    try:
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            5000,
            ctypes.byref(result),
        )
    except Exception:  # noqa: BLE001
        pass


def _ensure_on_path_posix(bin_path: Path) -> None:
    bin_str = str(bin_path)
    sentinel_start = "# >>> cbim launcher PATH >>>"
    sentinel_end = "# <<< cbim launcher PATH <<<"
    block = '{}\nexport PATH="{}:$PATH"\n{}\n'.format(
        sentinel_start, bin_str, sentinel_end
    )

    shell = os.environ.get("SHELL", "")
    home = Path.home()

    targets: list[Path] = []
    if "fish" in shell:
        targets.append(home / ".config" / "fish" / "conf.d" / "cbim.fish")
    else:
        bashrc = home / ".bashrc"
        zshrc = home / ".zshrc"
        if bashrc.exists():
            targets.append(bashrc)
        if zshrc.exists():
            targets.append(zshrc)
        if not targets:
            if "zsh" in shell:
                targets.append(zshrc)
            else:
                targets.append(bashrc)

    for target in targets:
        if "fish" in shell and target.name == "cbim.fish":
            fish_block = (
                "{}\nset -gx PATH {} $PATH\n{}\n".format(
                    sentinel_start, bin_str, sentinel_end
                )
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_sentinel_block(target, sentinel_start, sentinel_end, fish_block)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_sentinel_block(target, sentinel_start, sentinel_end, block)


def _write_sentinel_block(
    target: Path, sentinel_start: str, sentinel_end: str, block: str
) -> None:
    existing = ""
    if target.exists():
        existing = target.read_text(encoding="utf-8")

    if sentinel_start in existing and sentinel_end in existing:
        start_idx = existing.index(sentinel_start)
        end_idx = existing.index(sentinel_end) + len(sentinel_end)
        while end_idx < len(existing) and existing[end_idx] == "\n":
            end_idx += 1
        new_content = existing[:start_idx] + block + existing[end_idx:]
    else:
        if existing and not existing.endswith("\n"):
            existing += "\n"
        new_content = existing + block

    with target.open("w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)


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
