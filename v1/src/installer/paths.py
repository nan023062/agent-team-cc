"""Single source of truth for CBIM global install root location.

# Upgrade module contract:
# All path queries for "where is CBIM installed" MUST go through:
#   - install_root() (here)
#   - registry.cbim_home() / registry.versions_file() / registry.get_kernel_path()
#   - venv_mgr.venv_path()
#   - bootstrap.bin_dir()
# DO NOT hardcode Path.home() / ".cbim" or any other path.
#
# The launcher (v1/src/bin/cbim_launcher.py) intentionally inlines a *copy*
# of install_root()'s logic (it must not import installer — it bootstraps
# the PATH before installer is reachable). Any change here must be mirrored
# there.

Resolution order:
    1. CBIM_INSTALL_ROOT env var (absolute path; overrides everything).
    2. Windows: %LOCALAPPDATA%\\Cbim-CC\\
       (fallback: ~/AppData/Local/Cbim-CC when LOCALAPPDATA is unset)
    3. POSIX: $XDG_DATA_HOME/Cbim-CC/
       (default: ~/.local/share/Cbim-CC when XDG_DATA_HOME is unset)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


_DIR_NAME = "Cbim-CC"


def install_root() -> Path:
    """Return the absolute path to the CBIM global install root.

    Resolution order:
        1. ``CBIM_INSTALL_ROOT`` env var (absolute or ``~``-expandable).
        2. Windows: ``%LOCALAPPDATA%\\Cbim-CC\\``
           (fallback: ``~/AppData/Local/Cbim-CC`` when LOCALAPPDATA is unset).
        3. POSIX: ``$XDG_DATA_HOME/Cbim-CC/``
           (default: ``~/.local/share/Cbim-CC`` when XDG_DATA_HOME is unset).
    """
    env = os.environ.get("CBIM_INSTALL_ROOT")
    if env:
        return Path(env).expanduser()

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / _DIR_NAME
        # Fallback: standard Windows local-appdata layout under the home dir.
        return Path.home() / "AppData" / "Local" / _DIR_NAME

    # POSIX (Linux, macOS, *BSD).
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / _DIR_NAME
    return Path.home() / ".local" / "share" / _DIR_NAME
