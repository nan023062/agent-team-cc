"""Tests for the pure 7-scenario diagnostic matrix."""
from __future__ import annotations

from pathlib import Path

import pytest

from cbim_kernel.project.upgrade.app_state import AppState
from cbim_kernel.project.upgrade.config import default_config
from cbim_kernel.project.upgrade.diagnose import diagnose, scenario_id
from cbim_kernel.project.upgrade.project_state import ProjectState
from cbim_kernel.project.upgrade.remote import RemoteState


def _app(installed: dict, active: str | None = None) -> AppState:
    return AppState(
        install_root=Path("/fake/install_root"),
        installed=installed,
        active_default=active,
    )


def _proj(root: Path | None, pin: str | None) -> ProjectState:
    return ProjectState(root=root, pin=pin, upgrade_config=default_config())


def _remote(latest: str | None, reachable: bool) -> RemoteState:
    return RemoteState(url="https://example/cbim.git", latest=latest, reachable=reachable)


def _entry(ver: str) -> dict:
    return {ver: {"kernel_path": f"/k/{ver}", "venv_path": "/v", "source": "local", "installed_at": "x"}}


# ---------------------------------------------------------------------------
# Scenario 1: cold-start — nothing installed, no project.
def test_scenario_1_cold_start():
    d = diagnose(_app({}), _proj(None, None), _remote(None, False))
    assert d.scenario == 1
    assert d.scenario_name == "cold-start"
    assert d.ordered is True
    assert any("install.py" in c.cmd for c in d.commands)
    assert any("cbim init" in c.cmd for c in d.commands)


# Scenario 2: app current, project not initialized, no remote update.
def test_scenario_2_app_ready_project_new():
    app = _app(_entry("1.2.3"), active="1.2.3")
    d = diagnose(app, _proj(None, None), _remote("1.2.3", True))
    assert d.scenario == 2
    assert d.scenario_name == "app-ready-project-new"
    assert d.commands[0].cmd == "cbim init"


# Scenario 3: app outdated, project not initialized.
def test_scenario_3_app_stale_project_new():
    app = _app(_entry("1.2.0"), active="1.2.0")
    d = diagnose(app, _proj(None, None), _remote("1.2.5", True))
    assert d.scenario == 3
    assert d.scenario_name == "app-stale-project-new"
    assert d.ordered is True
    assert "1.2.5" in d.commands[0].cmd
    assert d.commands[1].cmd == "cbim init"


# Scenario 4: app current, project pinned to an older installed version.
def test_scenario_4_project_stale_vs_app():
    installed = {**_entry("1.2.0"), **_entry("1.2.3")}
    app = _app(installed, active="1.2.3")
    d = diagnose(app, _proj(Path("/p"), "1.2.0"), _remote("1.2.3", True))
    assert d.scenario == 4
    assert d.scenario_name == "project-stale-vs-app"
    assert d.ordered is False
    assert any("migrate" in c.cmd for c in d.commands)


# Scenario 5: both stale — app behind remote, project behind app.
def test_scenario_5_both_stale():
    installed = {**_entry("1.2.0"), **_entry("1.2.3")}
    app = _app(installed, active="1.2.3")
    d = diagnose(app, _proj(Path("/p"), "1.2.0"), _remote("1.2.5", True))
    assert d.scenario == 5
    assert d.scenario_name == "both-stale"
    assert d.ordered is True
    assert "upgrade apply --to 1.2.5" in d.commands[0].cmd
    assert "migrate --to 1.2.5" in d.commands[1].cmd


# Scenario 6: app outdated vs remote, but pin == app current.
def test_scenario_6_app_stale_project_aligned():
    app = _app(_entry("1.2.3"), active="1.2.3")
    d = diagnose(app, _proj(Path("/p"), "1.2.3"), _remote("1.2.5", True))
    assert d.scenario == 6
    assert d.scenario_name == "app-stale-project-aligned"
    assert "upgrade apply --to 1.2.5" in d.commands[0].cmd


# Scenario 7: everything aligned.
def test_scenario_7_all_aligned():
    app = _app(_entry("1.2.3"), active="1.2.3")
    d = diagnose(app, _proj(Path("/p"), "1.2.3"), _remote("1.2.3", True))
    assert d.scenario == 7
    assert d.scenario_name == "all-aligned"
    assert d.commands == []


# ---------------------------------------------------------------------------
# Remote-unreachable degradation: scenario 5 should collapse to 4 when remote
# is unreachable (no remote_latest, so app cannot be "outdated").
def test_remote_unreachable_collapses_5_to_4():
    installed = {**_entry("1.2.0"), **_entry("1.2.3")}
    app = _app(installed, active="1.2.3")
    d = diagnose(app, _proj(Path("/p"), "1.2.0"), _remote(None, False))
    assert d.scenario == 4


# Pin exists but not installed → routed through scenario 4 (manual action).
def test_pin_not_installed_routes_to_scenario_4():
    app = _app(_entry("1.2.3"), active="1.2.3")
    d = diagnose(app, _proj(Path("/p"), "0.9.0"), _remote("1.2.3", True))
    assert d.scenario == 4


# ---------------------------------------------------------------------------
# scenario_id() pure truth-table coverage
def test_scenario_id_truth_table():
    # 1: no app, no pin
    assert scenario_id(False, False, False, False, False) == 1
    # 2: app current, no pin
    assert scenario_id(True, False, False, False, True) == 2
    # 3: app outdated, no pin
    assert scenario_id(True, True, False, False, True) == 3
    # 4: app current, pin older
    assert scenario_id(True, False, True, True, True) == 4
    # 5: app outdated, pin older
    assert scenario_id(True, True, True, True, True) == 5
    # 6: app outdated, pin aligned
    assert scenario_id(True, True, True, False, True) == 6
    # 7: all aligned
    assert scenario_id(True, False, True, False, True) == 7


# ---------------------------------------------------------------------------
# Hard purity check: diagnose() must not touch any filesystem, subprocess, or
# network. We assert by sentinel — pass a project root that does NOT exist
# and confirm diagnose() returns without error.
def test_diagnose_is_pure_no_io(tmp_path):
    bogus = tmp_path / "does-not-exist"
    d = diagnose(
        _app(_entry("1.2.3"), active="1.2.3"),
        _proj(bogus, "1.2.3"),
        _remote("1.2.3", True),
    )
    assert d.scenario == 7
