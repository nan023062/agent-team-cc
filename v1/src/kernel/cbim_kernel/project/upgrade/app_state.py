"""App-side install state, resolved via the installer's JSON read surface.

Contract: this module MUST NOT ``import installer.paths`` or
``import installer.registry``. Instead it spawns ``python -m installer
version --json`` and parses the result. See
``upgrade/.dna/contract.md`` Key Decision (Option A / subprocess).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cbim_kernel.context import kernel_root


@dataclass
class AppState:
    install_root: Optional[Path]
    installed: dict  # {version: {kernel_path, venv_path, source, installed_at}}
    active_default: Optional[str]
    venv_path: Optional[Path] = None
    venv_provisioned: bool = False
    error: Optional[str] = None  # populated when subprocess fails

    @property
    def installed_versions(self) -> list:
        return sorted(self.installed.keys())

    @property
    def latest_local(self) -> Optional[str]:
        if not self.installed:
            return None
        return max(self.installed.keys(), key=_version_key)


def _version_key(v: str) -> tuple:
    """Sort versions numerically; fallback to lexical for non-numeric segments."""
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def _empty_state(error: Optional[str] = None) -> AppState:
    return AppState(
        install_root=None,
        installed={},
        active_default=None,
        venv_path=None,
        venv_provisioned=False,
        error=error,
    )


def _resolve_installer_dir() -> Optional[Path]:
    """Locate the installer package directory.

    Resolution order:
      1. ``CBIM_INSTALL_ROOT`` env var + ``/installer``.
      2. ``<kernel_root>/../installer`` (development checkout layout).
      3. Standard install locations (Windows LOCALAPPDATA / POSIX XDG).
    """
    env_root = os.environ.get("CBIM_INSTALL_ROOT")
    if env_root:
        cand = Path(env_root).expanduser() / "installer"
        if cand.is_dir():
            return cand

    # Dev-checkout layout: v1/src/kernel/cbim_kernel and v1/src/installer
    try:
        kroot = kernel_root()
        # kernel_root() points at the directory containing cbim_kernel/. In a
        # dev checkout that's v1/src/kernel/. Sibling is v1/src/installer/.
        cand = kroot.parent / "installer"
        if cand.is_dir():
            return cand
    except Exception:  # noqa: BLE001
        pass

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            cand = Path(base) / "Cbim-CC" / "installer"
            if cand.is_dir():
                return cand
        cand = Path.home() / "AppData" / "Local" / "Cbim-CC" / "installer"
        if cand.is_dir():
            return cand
    else:
        base = os.environ.get("XDG_DATA_HOME")
        if base:
            cand = Path(base) / "Cbim-CC" / "installer"
            if cand.is_dir():
                return cand
        cand = Path.home() / ".local" / "share" / "Cbim-CC" / "installer"
        if cand.is_dir():
            return cand
    return None


def _query_installer_json() -> Optional[dict]:
    """Run ``python -m installer version --json`` and parse the result.

    Returns ``None`` on any failure (subprocess error, non-zero exit, bad JSON).
    Never raises.
    """
    installer_dir = _resolve_installer_dir()
    if installer_dir is None:
        return None
    # The installer package must be importable as `installer`. Its parent dir
    # (e.g. <install_root>/ or v1/src/) goes on PYTHONPATH.
    pkg_parent = installer_dir.parent
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(pkg_parent) + (os.pathsep + existing if existing else "")
    )
    try:
        result = subprocess.run(
            [sys.executable, "-m", "installer", "version", "--json"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None


def _parse(payload: dict) -> AppState:
    install_root_s = payload.get("install_root")
    install_root = Path(install_root_s) if isinstance(install_root_s, str) and install_root_s else None
    installed = payload.get("installed")
    if not isinstance(installed, dict):
        installed = {}
    active = payload.get("active_default")
    if not (isinstance(active, str) and active.strip()):
        active = None
    venv = payload.get("venv") if isinstance(payload.get("venv"), dict) else {}
    venv_path_s = venv.get("path") if isinstance(venv, dict) else None
    venv_path = Path(venv_path_s) if isinstance(venv_path_s, str) and venv_path_s else None
    venv_provisioned = bool(venv.get("provisioned")) if isinstance(venv, dict) else False
    return AppState(
        install_root=install_root,
        installed=installed,
        active_default=active,
        venv_path=venv_path,
        venv_provisioned=venv_provisioned,
    )


def get_app_state() -> AppState:
    """Return the fully-populated AppState, or an empty state on failure."""
    payload = _query_installer_json()
    if payload is None:
        return _empty_state(error="installer query failed")
    return _parse(payload)


def get_install_root() -> Optional[Path]:
    return get_app_state().install_root


def list_installed() -> dict:
    return get_app_state().installed


def active_default() -> Optional[str]:
    return get_app_state().active_default
