"""Shared Python venv at ``<install_root>/venv/``."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from installer.registry import cbim_home


def venv_path() -> Path:
    """Return path to the shared venv (lazy: resolves install_root on call)."""
    return cbim_home() / "venv"


def python_executable() -> Path:
    """Return path to Python in the venv (``Scripts/python.exe`` on Windows)."""
    vp = venv_path()
    if sys.platform == "win32":
        return vp / "Scripts" / "python.exe"
    return vp / "bin" / "python"


def _has_mcp() -> bool:
    py = python_executable()
    if not py.is_file():
        return False
    try:
        result = subprocess.run(
            [str(py), "-c", "import mcp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return result.returncode == 0


def is_provisioned() -> bool:
    """Check if venv exists and has the mcp package installed."""
    return python_executable().is_file() and _has_mcp()


def _create_venv() -> None:
    vp = venv_path()
    vp.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "venv", str(vp)],
        check=True,
    )


def ensure_venv(requirements_txt: Path) -> Path:
    """Create venv + install requirements; idempotent fast-path when already provisioned."""
    if is_provisioned():
        return venv_path()

    if not python_executable().is_file():
        _create_venv()

    if requirements_txt.is_file():
        subprocess.run(
            [
                str(python_executable()),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(requirements_txt),
            ],
            check=True,
        )

    return venv_path()


def update_venv(requirements_txt: Path) -> Path:
    """Install/upgrade requirements into the existing venv (or create it first).

    Unlike ensure_venv, this always runs pip even when the venv is provisioned,
    so new dependencies in an upgraded kernel are picked up.
    """
    if not python_executable().is_file():
        _create_venv()

    if Path(requirements_txt).is_file():
        subprocess.run(
            [
                str(python_executable()),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(requirements_txt),
            ],
            check=True,
        )

    return venv_path()
