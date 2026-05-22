"""Tests for snapshot / invoke / verify / rollback."""
from __future__ import annotations

from pathlib import Path

import pytest

from updater.upgrade import apply_flow
from updater.upgrade.app_state import AppState
from updater.upgrade.config import default_config
from updater.upgrade.diagnose import diagnose
from updater.upgrade.project_state import ProjectState
from updater.upgrade.remote import RemoteState


def _make_install_root(tmp_path: Path, version: str = "1.2.3") -> Path:
    root = tmp_path / "Cbim-CC"
    kdir = root / "kernel" / version / "cbim_kernel"
    kdir.mkdir(parents=True)
    (kdir / "__main__.py").write_text("# kernel", encoding="utf-8")
    (root / "versions.json").write_text(
        '{"active_default": "' + version + '", "installed": {"' + version + '": {"kernel_path": "x"}}}',
        encoding="utf-8",
    )
    return root


def _entry(ver: str) -> dict:
    return {ver: {"kernel_path": f"/k/{ver}", "venv_path": "/v", "source": "local", "installed_at": "x"}}


def _diagnosis_for(install_root: Path, pin: str | None, target: str) -> "diagnose":
    app = AppState(install_root=install_root, installed=_entry("1.2.3"), active_default="1.2.3")
    project = ProjectState(root=Path("/p") if pin else None, pin=pin, upgrade_config=default_config())
    remote = RemoteState(url="https://example/cbim.git", latest=target, reachable=True)
    return diagnose(app, project, remote)


# ---------------------------------------------------------------------------
# Snapshot + rollback round-trip — narrowed scope: only kernel/ + versions.json.
def test_snapshot_then_rollback_restores_files(tmp_path):
    root = _make_install_root(tmp_path)
    snap = apply_flow.snapshot_app(root)
    assert snap.is_file()

    # Mutate: trash the kernel main + versions.json.
    (root / "kernel" / "1.2.3" / "cbim_kernel" / "__main__.py").write_text("# dirty", encoding="utf-8")
    (root / "versions.json").write_text("{}", encoding="utf-8")

    apply_flow.rollback_from_snapshot(snap, root)
    assert (root / "kernel" / "1.2.3" / "cbim_kernel" / "__main__.py").read_text(encoding="utf-8") == "# kernel"
    assert '"active_default"' in (root / "versions.json").read_text(encoding="utf-8")
    snap.unlink()


# ---------------------------------------------------------------------------
# verify_post_install: positive
def test_verify_post_install_ok(tmp_path):
    root = _make_install_root(tmp_path, version="1.2.3")
    assert apply_flow.verify_post_install(root, "1.2.3") is True


# verify_post_install: missing kernel dir
def test_verify_post_install_missing_kernel(tmp_path):
    root = _make_install_root(tmp_path, version="1.2.3")
    assert apply_flow.verify_post_install(root, "9.9.9") is False


# ---------------------------------------------------------------------------
# Preflight: refuses when project pin requires migration first.
def test_preflight_refuses_when_pin_older_than_target(tmp_path):
    root = _make_install_root(tmp_path)
    # Project root that has neither a .pin nor a legacy config.json — the
    # Bug-A check must not fire on this path. Pin is supplied directly.
    proj_root = tmp_path / "proj"
    (proj_root / ".cbim").mkdir(parents=True)
    project = ProjectState(root=proj_root, pin="1.0.0", upgrade_config=default_config())
    app = AppState(install_root=root, installed=_entry("1.2.3"), active_default="1.2.3")
    remote = RemoteState(url="x", latest="1.2.5", reachable=True)
    d = diagnose(app, project, remote)
    with pytest.raises(SystemExit) as exc:
        apply_flow.preflight(d, "1.2.5")
    assert exc.value.code == 2


# Preflight: allows when target == pin.
def test_preflight_allows_when_target_equals_pin(tmp_path):
    root = _make_install_root(tmp_path)
    proj_root = tmp_path / "proj"
    (proj_root / ".cbim").mkdir(parents=True)
    project = ProjectState(root=proj_root, pin="1.2.3", upgrade_config=default_config())
    app = AppState(install_root=root, installed=_entry("1.2.3"), active_default="1.2.3")
    remote = RemoteState(url="x", latest="1.2.3", reachable=True)
    d = diagnose(app, project, remote)
    apply_flow.preflight(d, "1.2.3")  # no raise


# Preflight: allows when no project root.
def test_preflight_allows_when_no_project(tmp_path):
    root = _make_install_root(tmp_path)
    project = ProjectState(root=None, pin=None, upgrade_config=default_config())
    app = AppState(install_root=root, installed=_entry("1.2.3"), active_default="1.2.3")
    remote = RemoteState(url="x", latest="1.2.5", reachable=True)
    d = diagnose(app, project, remote)
    apply_flow.preflight(d, "1.2.5")  # no raise


# Bug-A fix: refuses legacy schema (cbim_version in config.json, no .pin file).
def test_preflight_refuses_legacy_schema(tmp_path):
    root = _make_install_root(tmp_path)
    proj_root = tmp_path / "legacy_proj"
    (proj_root / ".cbim").mkdir(parents=True)
    (proj_root / ".cbim" / "config.json").write_text(
        '{"cbim_version": "1.2.0"}', encoding="utf-8"
    )
    project = ProjectState(root=proj_root, pin=None, upgrade_config=default_config())
    app = AppState(install_root=root, installed=_entry("1.2.3"), active_default="1.2.3")
    remote = RemoteState(url="x", latest="1.2.5", reachable=True)
    d = diagnose(app, project, remote)
    with pytest.raises(SystemExit) as exc:
        apply_flow.preflight(d, "1.2.5")
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# run_apply happy path: monkeypatch invoke + verify; ensure exit code 0.
def test_run_apply_happy_path(tmp_path, monkeypatch):
    root = _make_install_root(tmp_path)
    d = _diagnosis_for(root, pin=None, target="1.2.5")

    called = {}

    def fake_invoke(install_root, version, source="github", source_from=None):
        called["invoke"] = (install_root, version)
        # Simulate the installer staging the new version.
        new_k = install_root / "kernel" / version / "cbim_kernel"
        new_k.mkdir(parents=True, exist_ok=True)
        (new_k / "__main__.py").write_text("# new kernel", encoding="utf-8")
        # Update versions.json to include the new version.
        import json as _j
        data = _j.loads((install_root / "versions.json").read_text(encoding="utf-8"))
        data["installed"][version] = {"kernel_path": str(install_root / "kernel" / version)}
        data["active_default"] = version
        (install_root / "versions.json").write_text(_j.dumps(data), encoding="utf-8")
        return 0

    monkeypatch.setattr(apply_flow, "invoke_updater", fake_invoke)

    rc = apply_flow.run_apply(d, target_version="1.2.5", dry_run=False)
    assert rc == 0
    assert called["invoke"] == (root, "1.2.5")
    assert apply_flow.verify_post_install(root, "1.2.5") is True


# Rollback on installer failure: exit code 4, original state restored.
def test_run_apply_rollback_on_installer_failure(tmp_path, monkeypatch):
    root = _make_install_root(tmp_path)
    d = _diagnosis_for(root, pin=None, target="1.2.5")

    def fake_invoke(install_root, version, source="github", source_from=None):
        # Pretend the installer trashed versions.json before failing.
        (install_root / "versions.json").write_text("{}", encoding="utf-8")
        return 9

    monkeypatch.setattr(apply_flow, "invoke_updater", fake_invoke)

    rc = apply_flow.run_apply(d, target_version="1.2.5", dry_run=False)
    assert rc == 4
    assert '"active_default"' in (root / "versions.json").read_text(encoding="utf-8")


# Rollback on verify failure: installer returns 0 but verification fails.
def test_run_apply_rollback_on_verify_failure(tmp_path, monkeypatch):
    root = _make_install_root(tmp_path)
    d = _diagnosis_for(root, pin=None, target="1.2.5")

    def fake_invoke(install_root, version, source="github", source_from=None):
        # Do nothing — verify_post_install will then fail.
        return 0

    monkeypatch.setattr(apply_flow, "invoke_updater", fake_invoke)

    rc = apply_flow.run_apply(d, target_version="1.2.5", dry_run=False)
    assert rc == 4
    # Original kernel content preserved.
    assert (root / "kernel" / "1.2.3" / "cbim_kernel" / "__main__.py").is_file()


# Preflight refusal short-circuits before snapshot.
def test_run_apply_preflight_refusal(tmp_path):
    root = _make_install_root(tmp_path)
    proj_root = tmp_path / "proj"
    (proj_root / ".cbim").mkdir(parents=True)
    project = ProjectState(root=proj_root, pin="1.0.0", upgrade_config=default_config())
    app = AppState(install_root=root, installed=_entry("1.2.3"), active_default="1.2.3")
    remote = RemoteState(url="x", latest="1.2.5", reachable=True)
    d = diagnose(app, project, remote)
    rc = apply_flow.run_apply(d, target_version="1.2.5", dry_run=False)
    assert rc == 2


# Remote unreachable on apply -> exit 3.
def test_run_apply_remote_unreachable(tmp_path):
    root = _make_install_root(tmp_path)
    app = AppState(install_root=root, installed=_entry("1.2.3"), active_default="1.2.3")
    project = ProjectState(root=None, pin=None, upgrade_config=default_config())
    remote = RemoteState(url="x", latest=None, reachable=False)
    d = diagnose(app, project, remote)
    rc = apply_flow.run_apply(d, target_version="1.2.5", dry_run=False)
    assert rc == 3


# Dry run never invokes installer.
def test_run_apply_dry_run_no_invoke(tmp_path, monkeypatch):
    root = _make_install_root(tmp_path)
    d = _diagnosis_for(root, pin=None, target="1.2.5")

    def fail(*a, **kw):
        raise AssertionError("invoke_updater must not be called in dry-run")

    monkeypatch.setattr(apply_flow, "invoke_updater", fail)
    rc = apply_flow.run_apply(d, target_version="1.2.5", dry_run=True)
    assert rc == 0
