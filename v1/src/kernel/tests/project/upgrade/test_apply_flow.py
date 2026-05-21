"""Tests for snapshot / invoke / verify / rollback."""
from __future__ import annotations

from pathlib import Path

import pytest

from cbim_kernel.project.upgrade import apply_flow
from cbim_kernel.project.upgrade.app_state import AppState
from cbim_kernel.project.upgrade.config import default_config
from cbim_kernel.project.upgrade.diagnose import diagnose
from cbim_kernel.project.upgrade.project_state import ProjectState
from cbim_kernel.project.upgrade.remote import RemoteState


def _make_install_root(tmp_path: Path, version: str = "1.2.3") -> Path:
    root = tmp_path / "Cbim-CC"
    (root / "installer").mkdir(parents=True)
    (root / "installer" / "__init__.py").write_text("# stub", encoding="utf-8")
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "marker.txt").write_text("v1", encoding="utf-8")
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
# Snapshot + rollback round-trip
def test_snapshot_then_rollback_restores_files(tmp_path):
    root = _make_install_root(tmp_path)
    snap = apply_flow.snapshot_app(root)
    assert snap.is_file()

    # Mutate: wipe bin/, add a stray file under installer/.
    (root / "bin" / "marker.txt").unlink()
    (root / "installer" / "stray.txt").write_text("dirty", encoding="utf-8")

    apply_flow.rollback_from_snapshot(snap, root)
    assert (root / "bin" / "marker.txt").read_text(encoding="utf-8") == "v1"
    assert not (root / "installer" / "stray.txt").exists()
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
    project = ProjectState(root=tmp_path, pin="1.0.0", upgrade_config=default_config())
    app = AppState(install_root=root, installed=_entry("1.2.3"), active_default="1.2.3")
    remote = RemoteState(url="x", latest="1.2.5", reachable=True)
    d = diagnose(app, project, remote)
    with pytest.raises(SystemExit) as exc:
        apply_flow.preflight(d, "1.2.5")
    assert exc.value.code == 2


# Preflight: allows when target == pin.
def test_preflight_allows_when_target_equals_pin(tmp_path):
    root = _make_install_root(tmp_path)
    project = ProjectState(root=tmp_path, pin="1.2.3", upgrade_config=default_config())
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


# ---------------------------------------------------------------------------
# run_apply happy path: monkeypatch invoke + verify; ensure exit code 0.
def test_run_apply_happy_path(tmp_path, monkeypatch):
    root = _make_install_root(tmp_path)
    d = _diagnosis_for(root, pin=None, target="1.2.5")

    called = {}

    def fake_invoke(install_root, version):
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

    monkeypatch.setattr(apply_flow, "invoke_installer", fake_invoke)

    rc = apply_flow.run_apply(d, target_version="1.2.5", dry_run=False)
    assert rc == 0
    assert called["invoke"] == (root, "1.2.5")
    assert apply_flow.verify_post_install(root, "1.2.5") is True


# Rollback on installer failure: exit code 4, original state restored.
def test_run_apply_rollback_on_installer_failure(tmp_path, monkeypatch):
    root = _make_install_root(tmp_path)
    d = _diagnosis_for(root, pin=None, target="1.2.5")

    def fake_invoke(install_root, version):
        # Pretend the installer trashed bin/ before failing.
        (install_root / "bin" / "marker.txt").unlink()
        return 9

    monkeypatch.setattr(apply_flow, "invoke_installer", fake_invoke)

    rc = apply_flow.run_apply(d, target_version="1.2.5", dry_run=False)
    assert rc == 4
    assert (root / "bin" / "marker.txt").read_text(encoding="utf-8") == "v1"


# Rollback on verify failure: installer returns 0 but verification fails.
def test_run_apply_rollback_on_verify_failure(tmp_path, monkeypatch):
    root = _make_install_root(tmp_path)
    d = _diagnosis_for(root, pin=None, target="1.2.5")

    def fake_invoke(install_root, version):
        # Do nothing — verify_post_install will then fail.
        return 0

    monkeypatch.setattr(apply_flow, "invoke_installer", fake_invoke)

    rc = apply_flow.run_apply(d, target_version="1.2.5", dry_run=False)
    assert rc == 4
    assert (root / "bin" / "marker.txt").exists()


# Preflight refusal short-circuits before snapshot.
def test_run_apply_preflight_refusal(tmp_path):
    root = _make_install_root(tmp_path)
    project = ProjectState(root=tmp_path, pin="1.0.0", upgrade_config=default_config())
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
        raise AssertionError("invoke_installer must not be called in dry-run")

    monkeypatch.setattr(apply_flow, "invoke_installer", fail)
    rc = apply_flow.run_apply(d, target_version="1.2.5", dry_run=True)
    assert rc == 0
