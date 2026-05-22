"""Upgrade configuration: defaults + per-project overrides.

The per-project block lives at ``<project_root>/.cbim/config.json`` under the
``upgrade`` key. Missing/invalid values fall back to defaults.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_REMOTE = "https://github.com/nan023062/cbim.git"
DEFAULT_PATTERN = "v*"
DEFAULT_AUTO_CHECK = True
DEFAULT_CHECK_INTERVAL_HOURS = 24
DEFAULT_CHANNEL = "stable"


@dataclass
class UpgradeConfig:
    remote: str
    branch_or_tag_pattern: str
    auto_check: bool
    check_interval_hours: int
    channel: str

    def to_dict(self) -> dict:
        return {
            "remote": self.remote,
            "branch_or_tag_pattern": self.branch_or_tag_pattern,
            "auto_check": self.auto_check,
            "check_interval_hours": self.check_interval_hours,
            "channel": self.channel,
        }


def default_config() -> UpgradeConfig:
    return UpgradeConfig(
        remote=DEFAULT_REMOTE,
        branch_or_tag_pattern=DEFAULT_PATTERN,
        auto_check=DEFAULT_AUTO_CHECK,
        check_interval_hours=DEFAULT_CHECK_INTERVAL_HOURS,
        channel=DEFAULT_CHANNEL,
    )


def load_from_project(project_root: Path) -> UpgradeConfig:
    """Read ``.cbim/config.json`` ``upgrade`` block; fall back to defaults.

    Tolerates: missing file, invalid JSON, missing ``upgrade`` key, partial
    overrides, wrong types. Never raises on user data.
    """
    cfg = default_config()
    cfg_path = project_root / ".cbim" / "config.json"
    if not cfg_path.is_file():
        return cfg
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return cfg
    block = data.get("upgrade") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        return cfg

    remote = block.get("remote")
    if isinstance(remote, str) and remote.strip():
        cfg.remote = remote.strip()

    pattern = block.get("branch_or_tag_pattern")
    if isinstance(pattern, str) and pattern.strip():
        cfg.branch_or_tag_pattern = pattern.strip()

    auto_check = block.get("auto_check")
    if isinstance(auto_check, bool):
        cfg.auto_check = auto_check

    interval = block.get("check_interval_hours")
    if isinstance(interval, int) and interval > 0:
        cfg.check_interval_hours = interval

    channel = block.get("channel")
    if isinstance(channel, str) and channel.strip():
        cfg.channel = channel.strip()

    return cfg
