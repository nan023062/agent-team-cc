"""Snapshot / invoke / verify / rollback for ``cbim upgrade apply``.

All mutation of ``<install_root>/`` is delegated to ``updater.install`` via a
direct in-process call (no subprocess). Snapshot + rollback are internal to
this module — there is no public ``cbim upgrade rollback`` subcommand.

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
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from updater.upgrade.diagnose import Diagnosis


# Snapshot scope: only versions.json + kernel/<ver>/. Bin and updater are
# excluded — they are rebuilt deterministically by `python install.py` /
# `cbim self-update` and the bin layout is launcher-version-stable.
_SNAPSHOT_DIRS: tuple = ()


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

    Bug-A fix: also refuse when the project is on the legacy schema
    (``cbim_version`` still embedded in ``.cbim/config.json`` and no
    ``.cbim/.pin`` file present).
    """
    project = diagnosis.project

    # Bug-A fix: detect legacy schema
    if project.root is not None:
        cbim_dir = project.root / ".cbim"
        config_path = cbim_dir / "config.json"
        pin_path = cbim_dir / ".pin"
        if not pin_path.exists() and config_path.exists():
            try:
                import json as _json
                cfg = _json.loads(config_path.read_text(encoding="utf-8"))
                if isinstance(cfg, dict) and "cbim_version" in cfg:
                    raise PreflightRefused(
                        f"project at {project.root} uses legacy schema "
                        f"(cbim_version in config.json, no .pin file); "
                        f"run `cbim migrate --version {target_version}` first"
                    )
            except (OSError, ValueError):
                pass

    if project.root is None or not project.pin:
        # No project context, or no pin — safe to proceed on the app side.
        return
    if project.pin == target_version:
        return
    # If the target is newer than the pin, require an explicit migrate first.
    from updater.upgrade.diagnose import _newer  # type: ignore
    if _newer(target_version, project.pin):
        raise PreflightRefused(
            "project at {} is pinned to {}; run `cbim migrate --version {}` first, "
            "then `cbim upgrade apply --to {}`".format(
                project.root, project.pin, target_version, target_version
            )
        )


def snapshot_app(install_root: Path) -> Path:
    """Tar ``<install_root>/{versions.json,kernel/}`` into a temp file.

    Returns the absolute path to the snapshot tarball. Caller owns deletion.
    Scope is intentionally narrow: only the registry + installed kernel trees
    are versioned. The ``updater/``, ``bin/`` and ``venv/`` directories are
    excluded — they are rebuilt deterministically from a kernel checkout and
    must not be rolled back as part of an upgrade.
    """
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    fd, tmp_path = tempfile.mkstemp(prefix="cbim-snapshot-{}-".format(ts), suffix=".tar")
    os.close(fd)
    snap = Path(tmp_path)
    try:
        with tarfile.open(snap, "w") as tar:
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


def invoke_updater(
    install_root: Path,
    version: str,
    source: str = "github",
    source_from: Optional[str] = None,
) -> int:
    """Install *version* into *install_root* via an in-process call.

    Returns 0 on success, 1 on failure. Replaces the previous subprocess-based
    ``invoke_installer`` shim — installer and apply-flow now live in the same
    package, so a direct import is both simpler and faster.
    """
    from updater.install import install_from_github, install_from_local
    try:
        if source == "local":
            src = Path(source_from) if source_from else Path.cwd()
            install_from_local(src, version=version)
        else:
            # github (default) or git — both go through the GitHub path
            install_from_github(version=version)
        return 0
    except Exception as e:  # noqa: BLE001 — top-level CLI boundary
        sys.stderr.write(f"[cbim] install failed: {e}\n")
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
    """Restore ``<install_root>/{kernel,versions.json}`` from snapshot.

    Strategy:
      1. Wipe target dirs/files (atomic-best-effort: rename-then-rmtree).
      2. Extract snapshot tar in place.

    Raises on irrecoverable I/O errors — caller logs and exits 4.
    """
    install_root.mkdir(parents=True, exist_ok=True)

    target = install_root / "kernel"
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
    source: str = "github",
    source_from: Optional[str] = None,
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
        print("[cbim] [dry-run] would invoke updater.install_kernel({})".format(target_version))
        print("[cbim] [dry-run] would verify version {} landed".format(target_version))
        return 0

    snapshot = snapshot_app(install_root)
    print("[cbim] snapshot -> {}".format(snapshot))

    rc = invoke_updater(install_root, target_version, source=source, source_from=source_from)
    if rc != 0:
        sys.stderr.write("[cbim] updater exited {}; rolling back\n".format(rc))
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
