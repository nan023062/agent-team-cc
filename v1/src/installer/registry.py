"""Versions registry for ``~/.cbim/versions.json``.

Schema::

    {
      "active_default": "1.2.0",
      "installed": {
        "1.2.0": {
          "installed_at": "2026-05-21T10:30:00Z",
          "kernel_path": "/home/user/.cbim/kernel/1.2.0",
          "venv_path": "/home/user/.cbim/venv",
          "source": "local"
        }
      }
    }

All writes are atomic (temp file + ``os.replace``).
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CBIM_HOME = Path.home() / ".cbim"
VERSIONS_FILE = CBIM_HOME / "versions.json"


def _empty() -> dict:
    return {"active_default": None, "installed": {}}


def load() -> dict:
    """Return versions registry. Returns empty structure if file doesn't exist."""
    if not VERSIONS_FILE.is_file():
        return _empty()
    try:
        with VERSIONS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(data, dict):
        return _empty()
    data.setdefault("active_default", None)
    installed = data.get("installed")
    if not isinstance(installed, dict):
        data["installed"] = {}
    return data


def save(data: dict) -> None:
    """Atomic write to versions.json."""
    CBIM_HOME.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    # Temp file in the same directory so os.replace is atomic on all platforms.
    fd, tmp_path = tempfile.mkstemp(
        prefix=".versions.", suffix=".json.tmp", dir=str(CBIM_HOME)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, VERSIONS_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def register(
    version: str,
    kernel_path: Path,
    venv_path: Path,
    source: str = "local",
) -> None:
    """Add or update a version entry. Does not change ``active_default``."""
    data = load()
    data["installed"][version] = {
        "installed_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "kernel_path": str(kernel_path),
        "venv_path": str(venv_path),
        "source": source,
    }
    save(data)


def list_installed() -> list:
    """Return sorted list of installed version strings."""
    data = load()
    return sorted(data.get("installed", {}).keys())


def get_default() -> Optional[str]:
    """Return ``active_default`` or ``None``."""
    data = load()
    val = data.get("active_default")
    if isinstance(val, str) and val.strip():
        return val
    return None


def set_default(version: str) -> None:
    """Set ``active_default`` in versions.json."""
    data = load()
    if version not in data.get("installed", {}):
        raise ValueError(
            "cannot set default to '{}': not installed".format(version)
        )
    data["active_default"] = version
    save(data)


def get_kernel_path(version: str) -> Optional[Path]:
    """Return Path to installed kernel dir for version, or None if not installed."""
    data = load()
    entry = data.get("installed", {}).get(version)
    if not entry:
        return None
    p = entry.get("kernel_path")
    if not p:
        return None
    return Path(p)
