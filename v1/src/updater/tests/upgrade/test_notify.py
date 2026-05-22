"""Tests for the session-start notifier + cache I/O."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from updater.upgrade import notify
from updater.upgrade.config import default_config


def _make_project(tmp_path: Path, cfg_overrides: dict | None = None) -> Path:
    cbim = tmp_path / ".cbim"
    cbim.mkdir(parents=True)
    cfg = {"cbim_version": "1.2.0"}
    if cfg_overrides:
        cfg.update(cfg_overrides)
    (cbim / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Cache I/O round-trip.
def test_write_and_read_cache(tmp_path):
    project = _make_project(tmp_path)
    payload = {
        "timestamp": 12345,
        "project_pin": "1.2.0",
        "remote_latest": "1.2.5",
        "update_available": True,
        "scenario": 6,
    }
    notify.write_cache(project, payload)
    assert notify.read_cache(project) == payload


def test_read_cache_missing_returns_none(tmp_path):
    project = _make_project(tmp_path)
    assert notify.read_cache(project) is None


def test_read_cache_invalid_json_returns_none(tmp_path):
    project = _make_project(tmp_path)
    notify.cache_path(project).write_text("{not json", encoding="utf-8")
    assert notify.read_cache(project) is None


def test_cache_path_location(tmp_path):
    p = _make_project(tmp_path)
    assert notify.cache_path(p) == p / ".cbim" / ".upgrade_cache.json"


# ---------------------------------------------------------------------------
# session_start_line: no cache, auto_check on -> spawns refresh, returns None.
def test_session_start_line_no_cache_spawns(monkeypatch, tmp_path):
    project = _make_project(tmp_path)
    spawned = {}

    def fake_spawn(root):
        spawned["root"] = root

    monkeypatch.setattr(notify, "_spawn_background_refresh", fake_spawn)
    line = notify.session_start_line(project)
    assert line is None
    assert spawned["root"] == project


# Fresh cache (within interval) does NOT trigger a refresh.
def test_session_start_line_fresh_cache_no_spawn(monkeypatch, tmp_path):
    project = _make_project(tmp_path)
    notify.write_cache(project, {
        "timestamp": time.time(),
        "project_pin": "1.2.0",
        "remote_latest": "1.2.5",
        "update_available": True,
    })
    spawned = {"called": False}

    def fake_spawn(root):
        spawned["called"] = True

    monkeypatch.setattr(notify, "_spawn_background_refresh", fake_spawn)
    line = notify.session_start_line(project)
    assert spawned["called"] is False
    assert line is not None
    assert "1.2.0" in line and "1.2.5" in line
    assert "A new CBIM version is available" in line


# Stale cache (older than interval) triggers refresh AND still returns the
# old cache's banner (so user sees the previous verdict immediately).
def test_session_start_line_stale_cache_spawns(monkeypatch, tmp_path):
    project = _make_project(tmp_path)
    old_ts = time.time() - (25 * 3600)  # 25h ago, > default 24h
    notify.write_cache(project, {
        "timestamp": old_ts,
        "project_pin": "1.2.0",
        "remote_latest": "1.2.5",
        "update_available": True,
    })
    spawned = {"called": False}

    def fake_spawn(root):
        spawned["called"] = True

    monkeypatch.setattr(notify, "_spawn_background_refresh", fake_spawn)
    line = notify.session_start_line(project)
    assert spawned["called"] is True
    assert line is not None


# auto_check disabled -> always returns None, no spawn.
def test_session_start_line_auto_check_disabled(monkeypatch, tmp_path):
    project = _make_project(tmp_path, cfg_overrides={
        "upgrade": {"auto_check": False},
    })
    spawned = {"called": False}

    def fake_spawn(root):
        spawned["called"] = True

    monkeypatch.setattr(notify, "_spawn_background_refresh", fake_spawn)
    assert notify.session_start_line(project) is None
    assert spawned["called"] is False


# update_available=False -> no banner.
def test_session_start_line_no_update_available(monkeypatch, tmp_path):
    project = _make_project(tmp_path)
    notify.write_cache(project, {
        "timestamp": time.time(),
        "project_pin": "1.2.5",
        "remote_latest": "1.2.5",
        "update_available": False,
    })
    monkeypatch.setattr(notify, "_spawn_background_refresh", lambda r: None)
    assert notify.session_start_line(project) is None


# Pin == target -> suppress even if update_available somehow True.
def test_session_start_line_pin_equals_target(monkeypatch, tmp_path):
    project = _make_project(tmp_path)
    notify.write_cache(project, {
        "timestamp": time.time(),
        "project_pin": "1.2.5",
        "remote_latest": "1.2.5",
        "update_available": True,
    })
    monkeypatch.setattr(notify, "_spawn_background_refresh", lambda r: None)
    assert notify.session_start_line(project) is None


# No project context passed and none discoverable -> None.
def test_session_start_line_no_project(monkeypatch, tmp_path):
    monkeypatch.setattr(notify, "find_project_root", lambda start: None)
    assert notify.session_start_line() is None
