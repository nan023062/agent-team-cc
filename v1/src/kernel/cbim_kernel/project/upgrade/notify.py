"""Session-start notifier line + cache management.

Hard rule: ``notify`` never writes inside ``.cbim/`` directly. The cache write
happens in a fire-and-forget subprocess (``cbim upgrade check --json
--no-network``), invoked when the cache is stale. The subprocess itself
performs the write via its own normal CLI codepath.

The cache contains the most recent diagnosis snapshot used to render a single-
line banner like:

    [cbim] update available: 1.2.0 -> 1.2.5  (run `cbim upgrade check` for details)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from cbim_kernel.project.upgrade.project_state import (
    find_project_root,
    read_upgrade_config,
)


CACHE_FILENAME = ".upgrade_cache.json"


def cache_path(project_root: Path) -> Path:
    return project_root / ".cbim" / CACHE_FILENAME


def read_cache(project_root: Path) -> Optional[dict]:
    p = cache_path(project_root)
    if not p.is_file():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def write_cache(project_root: Path, data: dict) -> None:
    """Atomic write of the upgrade cache.

    Called by the CLI ``cmd_check`` codepath (the background subprocess), NOT
    by ``session_start_line``. Kept in this module so all cache I/O is colocated.
    """
    p = cache_path(project_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, p)


def _cache_age_seconds(cache: dict) -> Optional[float]:
    ts = cache.get("timestamp")
    if not isinstance(ts, (int, float)):
        return None
    return max(0.0, time.time() - float(ts))


def _spawn_background_refresh(project_root: Path) -> None:
    """Spawn ``cbim upgrade check --json --no-network`` in the background.

    Fire-and-forget — we never block on completion, never read stdout, never
    surface errors. Failure to spawn is silently swallowed.
    """
    try:
        # Detach so we don't hold a pipe or get reaped on session exit.
        kwargs: dict = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
            "cwd": str(project_root),
        }
        if sys.platform == "win32":
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            kwargs["creationflags"] = 0x00000008 | 0x00000200
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(
            [sys.executable, "-m", "cbim_kernel", "upgrade", "check",
             "--json", "--no-network", "--refresh-cache"],
            **kwargs,
        )
    except (OSError, ValueError):
        pass


def session_start_line(project_root: Optional[Path] = None) -> Optional[str]:
    """Return a one-line banner, or ``None`` if nothing to show.

    Called from ``hooks.load_memory``. Spawns a refresh subprocess if cache is
    stale; returns the previous cache's verdict (if any) so the banner appears
    at most one session late after a remote update.
    """
    if project_root is None:
        project_root = find_project_root(Path.cwd())
        if project_root is None:
            return None

    cfg = read_upgrade_config(project_root)
    if not cfg.auto_check:
        return None

    cache = read_cache(project_root)
    age = _cache_age_seconds(cache) if cache else None
    interval_s = cfg.check_interval_hours * 3600

    if cache is None or age is None or age > interval_s:
        _spawn_background_refresh(project_root)

    if cache is None:
        return None

    pin = cache.get("project_pin")
    target = cache.get("remote_latest") or cache.get("app_latest_local")
    update_available = bool(cache.get("update_available"))
    if not update_available or not target or not pin or pin == target:
        return None
    # Structured directive consumed by the coordinator at session start.
    # The coordinator parses the [cbim:upgrade-prompt] block, presents the
    # upgrade to the user in natural language, asks for confirmation, and on
    # confirm runs the `on_confirm` command directly via Bash (no agent
    # dispatch — this is a coordinator-level system task).
    return (
        "[cbim:upgrade-prompt]\n"
        f"current: {pin}\n"
        f"target: {target}\n"
        "message: A new CBIM version is available.\n"
        "on_confirm: cbim update && cbim project sync\n"
        "preserves: .cbim/config.json customizations, .cbim/memory/, "
        ".claude/commands/, custom agents, .dna/ knowledge\n"
        "overwrites: CLAUDE.md, .claude/agents (4 built-in), "
        ".claude/settings.json (kernel-managed keys only)\n"
        "[/cbim:upgrade-prompt]"
    )
