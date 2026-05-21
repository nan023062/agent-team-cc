"""Remote tag inspection via ``git ls-remote --tags``.

All functions degrade silently on network failure — they return ``False`` /
``None`` / ``[]`` rather than raising. ``check`` callers treat that as
"remote unreachable"; ``apply`` callers treat it as a fatal preflight error.
"""
from __future__ import annotations

import fnmatch
import socket
import subprocess
from dataclasses import dataclass
from typing import Optional

from cbim_kernel.project.upgrade.config import UpgradeConfig


@dataclass
class RemoteState:
    url: str
    latest: Optional[str]
    reachable: bool


def network_available() -> bool:
    """Probe DNS reachability on 8.8.8.8:53 (UDP-free TCP connect)."""
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=3):
            return True
    except (OSError, socket.timeout):
        return False


def ls_remote_tags(remote_url: str) -> list:
    """Return list of tag names from ``git ls-remote --tags <url>``.

    Returns ``[]`` on any failure (git not installed, network down, bad URL).
    Strips ``refs/tags/`` prefix and ``^{}`` peeled-tag suffixes.
    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", remote_url],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    tags: list = []
    seen: set = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        ref = parts[1]
        if not ref.startswith("refs/tags/"):
            continue
        name = ref[len("refs/tags/"):]
        if name.endswith("^{}"):
            name = name[:-3]
        if name not in seen:
            seen.add(name)
            tags.append(name)
    return tags


def _version_key(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def latest_tag(remote_url: str, pattern: str) -> Optional[str]:
    """Return highest-versioned tag matching ``pattern`` (fnmatch glob)."""
    tags = ls_remote_tags(remote_url)
    if not tags:
        return None
    matched = [t for t in tags if fnmatch.fnmatch(t, pattern)]
    if not matched:
        return None
    matched.sort(key=_version_key)
    return matched[-1]


def get_remote_state(cfg: UpgradeConfig, skip_network: bool = False) -> RemoteState:
    """Collect RemoteState; respect ``--no-network`` short-circuit."""
    url = cfg.remote
    if skip_network:
        return RemoteState(url=url, latest=None, reachable=False)
    if not network_available():
        return RemoteState(url=url, latest=None, reachable=False)
    latest = latest_tag(url, cfg.branch_or_tag_pattern)
    return RemoteState(url=url, latest=latest, reachable=latest is not None)
