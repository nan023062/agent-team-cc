"""Project-side state read surface for upgrade diagnosis.

Pure reads — never writes to ``.cbim/``. All writes go through
``project.init`` / ``project.migrate``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cbim_kernel.project import pin as project_pin
from cbim_kernel.project.upgrade.config import UpgradeConfig, load_from_project


@dataclass
class ProjectState:
    root: Optional[Path]
    pin: Optional[str]
    upgrade_config: UpgradeConfig


def find_project_root(start: Path) -> Optional[Path]:
    """Walk up from ``start`` looking for ``.cbim/config.json``.

    Returns ``None`` if no project marker is reachable. Hard-stops at the user
    home directory to avoid treating a stale legacy ``~/.cbim/`` as a project.
    """
    cur = Path(start).resolve()
    try:
        home = Path.home().resolve()
    except (RuntimeError, OSError):
        home = None
    for _ in range(64):
        if home is not None and cur == home:
            return None
        if (cur / ".cbim" / "config.json").is_file():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def read_pin(project_root: Path) -> Optional[str]:
    """Read the pinned kernel version from ``.cbim/.pin``; return None on absence."""
    return project_pin.read_pin(project_root)


def read_upgrade_config(project_root: Path) -> UpgradeConfig:
    return load_from_project(project_root)


def get_project_state(start: Path) -> ProjectState:
    """Collect ProjectState rooted at the nearest ``.cbim/`` above ``start``."""
    root = find_project_root(start)
    if root is None:
        # No project: use defaults; pin is unknown.
        from cbim_kernel.project.upgrade.config import default_config
        return ProjectState(root=None, pin=None, upgrade_config=default_config())
    return ProjectState(
        root=root,
        pin=read_pin(root),
        upgrade_config=read_upgrade_config(root),
    )
