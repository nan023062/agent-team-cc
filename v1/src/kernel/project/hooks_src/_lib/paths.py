"""
hooks_src/_lib/paths.py — path helpers for hook scripts.

stdlib-only. No business knowledge. No `cbim.*` imports.

Public surface:
    project_root_from_cwd(cwd) -> Path
    project_hash(project_root)  -> str   (12-hex sha256 prefix)
    mcp_sock_path(project_root) -> Path  (~/.cache/cbim/<hash>/mcp.sock)
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


def project_root_from_cwd(cwd: str) -> Path:
    """Walk up from `cwd` to find the directory containing `.claude/`.

    Falls back to `cwd` itself when nothing is found within 8 ancestors.
    Does NOT consult `.cbim/` — hook scripts must not touch that tree.
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


def project_hash(project_root: Path) -> str:
    """sha256 prefix of the absolute project root path."""
    abs_str = str(Path(project_root).resolve())
    return hashlib.sha256(abs_str.encode("utf-8")).hexdigest()[:12]


def mcp_sock_path(project_root: Path) -> Path:
    """Return `~/.cache/cbim/<project-hash>/mcp.sock`."""
    cache_home = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_home) / "cbim" / project_hash(project_root) / "mcp.sock"
