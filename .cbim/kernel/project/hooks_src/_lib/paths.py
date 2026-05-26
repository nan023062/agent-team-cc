"""
hooks_src/_lib/paths.py — path helpers for hook scripts.

stdlib-only. No business knowledge. No `cbim.*` imports.

Public surface:
    project_root_from_cwd(cwd) -> Path
    kernel_path(project_root)  -> Path  (<project>/.cbim/kernel)
"""

from __future__ import annotations

from pathlib import Path


def project_root_from_cwd(cwd: str) -> Path:
    """Walk up from `cwd` to find the directory containing `.claude/`.

    Falls back to `cwd` itself when nothing is found within 8 ancestors.
    """
    p = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    cur = p
    for _ in range(8):
        if (cur / ".claude").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return p


def kernel_path(project_root: Path) -> Path:
    """Return `<project_root>/.cbim/kernel`."""
    return Path(project_root) / ".cbim" / "kernel"
