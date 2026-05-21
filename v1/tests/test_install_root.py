"""Tests for installer.paths.install_root() resolution.

Covers architect §A (1-5):
  1. CBIM_INSTALL_ROOT env var wins over everything.
  2. Windows: uses %LOCALAPPDATA%\\Cbim-CC\\.
  3. POSIX: uses $XDG_DATA_HOME/Cbim-CC/.
  4. Windows fallback: when LOCALAPPDATA is unset, falls back to
     ~/AppData/Local/Cbim-CC.
  5. POSIX fallback: when XDG_DATA_HOME is unset, defaults to
     ~/.local/share/Cbim-CC.

"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


# Ensure the installer package is importable when running pytest from repo root.
_HERE = Path(__file__).resolve().parent
_INSTALLER_SRC = _HERE.parent / "src"
_p = str(_INSTALLER_SRC)
if _p not in sys.path:
    sys.path.insert(0, _p)


def _reload_paths():
    """Re-import installer.paths to pick up env changes (the module itself is
    pure-function so reload isn't strictly needed; this is defensive)."""
    import importlib

    from installer import paths as _paths
    return importlib.reload(_paths)


# --- 1. env var wins ------------------------------------------------------


def test_env_var_overrides_everything(monkeypatch, tmp_path):
    monkeypatch.setenv("CBIM_INSTALL_ROOT", str(tmp_path / "custom_root"))
    # Set platform-specific bases too, to prove env wins over them.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "wrong_localappdata"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "wrong_xdg"))

    paths = _reload_paths()
    assert paths.install_root() == Path(str(tmp_path / "custom_root"))


def test_env_var_expanduser(monkeypatch):
    monkeypatch.setenv("CBIM_INSTALL_ROOT", "~/explicit-cbim")
    paths = _reload_paths()
    assert paths.install_root() == Path.home() / "explicit-cbim"


# --- 2. Windows branch ----------------------------------------------------


def test_windows_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.delenv("CBIM_INSTALL_ROOT", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))

    paths = _reload_paths()
    assert paths.install_root() == Path(str(tmp_path / "LocalAppData")) / "Cbim-CC"


# --- 3. POSIX branch ------------------------------------------------------


def test_posix_uses_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.delenv("CBIM_INSTALL_ROOT", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    paths = _reload_paths()
    assert paths.install_root() == Path(str(tmp_path / "xdg")) / "Cbim-CC"


# --- 4. Windows fallback (no LOCALAPPDATA) --------------------------------


def test_windows_fallback_when_localappdata_unset(monkeypatch):
    monkeypatch.delenv("CBIM_INSTALL_ROOT", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")

    paths = _reload_paths()
    assert paths.install_root() == Path.home() / "AppData" / "Local" / "Cbim-CC"


# --- 5. POSIX fallback (no XDG_DATA_HOME) ---------------------------------


def test_posix_fallback_when_xdg_unset(monkeypatch):
    monkeypatch.delenv("CBIM_INSTALL_ROOT", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")

    paths = _reload_paths()
    assert paths.install_root() == Path.home() / ".local" / "share" / "Cbim-CC"
