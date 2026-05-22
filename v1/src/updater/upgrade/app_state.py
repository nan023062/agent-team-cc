"""App-side install state, resolved from the updater's on-disk contract.

Reads ``<install_root>/versions.json`` directly — it is the updater's
stable on-disk contract (same file the launcher reads).

Design rule: ``install_root`` is *pure path resolution* (env + platform).
It is populated whenever ``_resolve_install_root()`` returns a path,
*independently* of whether the registry on disk is readable. Only the
registry-derived fields (``installed``, ``active_default``, ``venv*``) get
cleared when the registry cannot be read. This lets callers distinguish
"install root unknown" (no path resolvable at all) from "install root
exists but registry unreadable" (path known, no installed kernels).
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AppState:
    install_root: Optional[Path]
    installed: dict  # {version: {kernel_path, venv_path, source, installed_at}}
    active_default: Optional[str]
    venv_path: Optional[Path] = None
    venv_provisioned: bool = False
    error: Optional[str] = None  # populated when registry read fails

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


def _resolve_install_root() -> Optional[Path]:
    """Resolve the CBIM install root using the same rules as ``updater.paths``.

    Mirrors ``updater/paths.py:install_root()`` inline. The launcher
    (``v1/src/bin/cbim_launcher.py:_install_root``) is the third mirror; keep
    all three in sync.

    Resolution order:
      1. ``CBIM_INSTALL_ROOT`` env var (absolute or ``~``-expandable).
      2. Windows: ``%LOCALAPPDATA%\\Cbim-CC``
         (fallback: ``~/AppData/Local/Cbim-CC`` when LOCALAPPDATA is unset).
      3. POSIX (Linux, macOS, *BSD):
         ``$XDG_DATA_HOME/Cbim-CC`` (default: ``~/.local/share/Cbim-CC``).

    Returns ``None`` only if path construction itself fails (e.g. no home
    directory). The returned path is *not* required to exist on disk —
    existence/readability is a registry concern, not a path-resolution
    concern. Callers that need a concrete install must check separately.
    """
    try:
        env = os.environ.get("CBIM_INSTALL_ROOT")
        if env:
            return Path(env).expanduser()

        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA")
            if base:
                return Path(base) / "Cbim-CC"
            return Path.home() / "AppData" / "Local" / "Cbim-CC"

        # POSIX (Linux, macOS, *BSD).
        base = os.environ.get("XDG_DATA_HOME")
        if base:
            return Path(base) / "Cbim-CC"
        return Path.home() / ".local" / "share" / "Cbim-CC"
    except (RuntimeError, OSError):
        return None


def _read_versions_json(install_root: Path) -> Optional[dict]:
    """Read ``<install_root>/versions.json`` directly.

    This file is the updater's stable on-disk contract (the launcher
    reads it too). Returns ``None`` if the file is missing or unreadable;
    never raises.
    """
    vfile = install_root / "versions.json"
    if not vfile.is_file():
        return None
    try:
        with vfile.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _parse_registry(install_root: Path, data: dict) -> tuple:
    """Extract (installed, active_default, venv_path, venv_provisioned) from
    a versions.json payload. Tolerant of missing/malformed fields."""
    installed = data.get("installed")
    if not isinstance(installed, dict):
        installed = {}

    active = data.get("active_default")
    if not (isinstance(active, str) and active.strip()):
        active = None

    # Optional ``venv`` block; otherwise fall back to ``<install_root>/venv``.
    venv_path: Optional[Path] = None
    venv_provisioned = False
    venv_block = data.get("venv")
    if isinstance(venv_block, dict):
        vps = venv_block.get("path")
        if isinstance(vps, str) and vps:
            venv_path = Path(vps)
        venv_provisioned = bool(venv_block.get("provisioned"))
    if venv_path is None:
        candidate = install_root / "venv"
        if candidate.is_dir():
            venv_path = candidate
            venv_provisioned = True

    return installed, active, venv_path, venv_provisioned


def get_app_state() -> AppState:
    """Return the AppState.

    ``install_root`` is always populated when path resolution succeeds —
    regardless of whether the registry on disk is readable. Registry fields
    are cleared (with ``error`` set) only when the registry read fails.
    """
    install_root = _resolve_install_root()
    if install_root is None:
        return AppState(
            install_root=None,
            installed={},
            active_default=None,
            venv_path=None,
            venv_provisioned=False,
            error="install root cannot be determined",
        )

    data = _read_versions_json(install_root)
    if data is None:
        return AppState(
            install_root=install_root,
            installed={},
            active_default=None,
            venv_path=None,
            venv_provisioned=False,
            error="registry unreadable at {}".format(install_root / "versions.json"),
        )

    installed, active, venv_path, venv_provisioned = _parse_registry(install_root, data)
    return AppState(
        install_root=install_root,
        installed=installed,
        active_default=active,
        venv_path=venv_path,
        venv_provisioned=venv_provisioned,
    )


def get_install_root() -> Optional[Path]:
    return get_app_state().install_root


def list_installed() -> dict:
    return get_app_state().installed


def active_default() -> Optional[str]:
    return get_app_state().active_default
