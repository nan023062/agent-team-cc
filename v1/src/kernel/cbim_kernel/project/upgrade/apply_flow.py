"""Snapshot / invoke / verify / rollback for ``cbim upgrade apply``.

All mutation of ``<install_root>/`` is delegated to the installer subprocess.
Snapshot + rollback are internal to this module — there is no public
``cbim upgrade rollback`` subcommand.

Exit-code contract (see contract.md):
  0  — applied successfully
  2  — preflight refused
  3  — network / download failure
  4  — apply failed mid-flight, rolled back
  1  — other unexpected error
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from cbim_kernel.project.upgrade.diagnose import Diagnosis


_SNAPSHOT_DIRS = ("installer", "bin")


class PreflightRefused(SystemExit):
    """Raised when the upgrade is refused before any mutation."""

    def __init__(self, message: str) -> None:
        sys.stderr.write("[cbim] preflight refused: {}\n".format(message))
        super().__init__(2)


def preflight(diagnosis: Diagnosis, target_version: str) -> None:
    """Refuse the upgrade if a project schema migration is required first.

    Rule: if the project has a pin AND the pin is older than the target AND
    the project root is known, the user must run ``cbim migrate`` first.
    The upgrade module never touches ``.cbim/`` directly.
    """
    project = diagnosis.project
    if project.root is None or not project.pin:
        # No project context, or no pin — safe to proceed on the app side.
        return
    if project.pin == target_version:
        return
    # If the target is newer than the pin, require an explicit migrate first.
    from cbim_kernel.project.upgrade.diagnose import _newer  # type: ignore
    if _newer(target_version, project.pin):
        raise PreflightRefused(
            "project at {} is pinned to {}; run `cbim migrate --to {}` first, "
            "then `cbim upgrade apply --to {}`".format(
                project.root, project.pin, target_version, target_version
            )
        )


def snapshot_app(install_root: Path) -> Path:
    """Tar ``<install_root>/{installer,bin}`` + active kernel into a temp file.

    Returns the absolute path to the snapshot tarball. Caller owns deletion.
    The current kernel directory is determined by inspecting
    ``<install_root>/kernel/`` and capturing every subdir (cheap on a single-
    version layout, correct on a multi-version layout).
    """
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    fd, tmp_path = tempfile.mkstemp(prefix="cbim-snapshot-{}-".format(ts), suffix=".tar")
    os.close(fd)
    snap = Path(tmp_path)
    try:
        with tarfile.open(snap, "w") as tar:
            for name in _SNAPSHOT_DIRS:
                d = install_root / name
                if d.is_dir():
                    tar.add(str(d), arcname=name)
            kernels = install_root / "kernel"
            if kernels.is_dir():
                tar.add(str(kernels), arcname="kernel")
            vfile = install_root / "versions.json"
            if vfile.is_file():
                tar.add(str(vfile), arcname="versions.json")
    except Exception:
        try:
            snap.unlink()
        except OSError:
            pass
        raise
    return snap


def invoke_installer(install_root: Path, version: str) -> int:
    """Run ``python -m installer install <version>``. Return exit code."""
    installer_dir = install_root / "installer"
    if not installer_dir.is_dir():
        sys.stderr.write(
            "[cbim] installer package not found at {}\n".format(installer_dir)
        )
        return 1
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(install_root) + (os.pathsep + existing if existing else "")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "installer", "install", version, "--set-default"],
            env=env,
        )
        return result.returncode
    except OSError as exc:
        sys.stderr.write("[cbim] failed to invoke installer: {}\n".format(exc))
        return 1


def verify_post_install(install_root: Path, version: str) -> bool:
    """Sanity check that the install actually landed the requested version."""
    kdir = install_root / "kernel" / version
    if not kdir.is_dir():
        return False
    # Spot-check that the kernel entry point exists.
    main = kdir / "cbim_kernel" / "__main__.py"
    if not main.is_file():
        return False
    # Confirm registry has the version.
    vfile = install_root / "versions.json"
    if vfile.is_file():
        try:
            import json as _json
            data = _json.loads(vfile.read_text(encoding="utf-8"))
            installed = data.get("installed", {})
            if isinstance(installed, dict) and version in installed:
                return True
        except (OSError, ValueError):
            return False
    return False


def rollback_from_snapshot(snapshot_path: Path, install_root: Path) -> None:
    """Restore ``<install_root>/{installer,bin,kernel,versions.json}`` from snapshot.

    Strategy:
      1. Wipe target dirs/files (atomic-best-effort: rename-then-rmtree).
      2. Extract snapshot tar in place.

    Raises on irrecoverable I/O errors — caller logs and exits 4.
    """
    install_root.mkdir(parents=True, exist_ok=True)

    for name in _SNAPSHOT_DIRS + ("kernel",):
        target = install_root / name
        if target.exists():
            shutil.rmtree(target)

    vfile = install_root / "versions.json"
    if vfile.is_file():
        vfile.unlink()

    with tarfile.open(snapshot_path, "r") as tar:
        # data_filter is preferred (Python 3.12+); fall back to permissive
        # extract for older interpreters. The snapshot is generated by this
        # same module from a trusted location, so the safety surface is small.
        try:
            tar.extractall(str(install_root), filter="data")
        except TypeError:
            tar.extractall(str(install_root))


def run_apply(
    diagnosis: Diagnosis,
    target_version: str,
    dry_run: bool = False,
) -> int:
    """Orchestrate the full apply flow. Returns the exit code per contract."""
    install_root = diagnosis.app.install_root
    if install_root is None:
        # Path resolution itself failed (no home dir, etc.). Distinct from
        # "install root exists but registry unreadable" — that case still
        # populates install_root so we can proceed with the apply.
        detail = diagnosis.app.error or "path resolution failed"
        sys.stderr.write(
            "[cbim] no install root resolved ({}); cannot apply\n".format(detail)
        )
        return 1

    try:
        preflight(diagnosis, target_version)
    except PreflightRefused as e:
        return int(e.code) if e.code is not None else 2

    if not diagnosis.remote.reachable:
        sys.stderr.write(
            "[cbim] remote unreachable; apply requires network confirmation of "
            "target version {}\n".format(target_version)
        )
        return 3

    if dry_run:
        print("[cbim] [dry-run] would snapshot {}".format(install_root))
        print("[cbim] [dry-run] would invoke: python -m installer install {} --set-default".format(target_version))
        print("[cbim] [dry-run] would verify version {} landed".format(target_version))
        return 0

    snapshot = snapshot_app(install_root)
    print("[cbim] snapshot -> {}".format(snapshot))

    rc = invoke_installer(install_root, target_version)
    if rc != 0:
        sys.stderr.write("[cbim] installer exited {}; rolling back\n".format(rc))
        try:
            rollback_from_snapshot(snapshot, install_root)
            print("[cbim] rolled back from snapshot")
        finally:
            _cleanup_snapshot(snapshot)
        return 4

    if not verify_post_install(install_root, target_version):
        sys.stderr.write("[cbim] post-install verification failed; rolling back\n")
        try:
            rollback_from_snapshot(snapshot, install_root)
            print("[cbim] rolled back from snapshot")
        finally:
            _cleanup_snapshot(snapshot)
        return 4

    _cleanup_snapshot(snapshot)
    print("[cbim] apply complete: active_default -> {}".format(target_version))
    return 0


def _cleanup_snapshot(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
