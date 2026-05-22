"""Core kernel installation logic."""
from __future__ import annotations

import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

from updater import registry
from updater.migrate_install_root import migrate_legacy_install_root
from updater.venv_mgr import update_venv, venv_path

# Sibling packages that live alongside kernel/ in the source tree and must
# be replicated to <install_root>/ as singletons (shared across all kernel
# versions). Order matters only for log readability.
_SIBLING_PACKAGES = ("updater", "installer")

# Launcher artifacts under v1/src/bin/ that must be refreshed at
# <install_root>/bin/ on every install. The launcher is the PATH entry the
# user invokes; without this refresh, routing changes in cbim_launcher.py
# (e.g. new UPDATER_COMMANDS) never reach the user's machine.
_LAUNCHER_FILES = ("cbim_launcher.py", "cbim", "cbim.cmd")

_PKG_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def _read_version(kernel_src: Path) -> str:
    version_file = kernel_src / "VERSION"
    if not version_file.is_file():
        raise FileNotFoundError(
            "VERSION file not found at {}".format(version_file)
        )
    return version_file.read_text(encoding="utf-8").strip()


def _replace_sibling_package(src: Path, dst: Path) -> None:
    """Copy *src* directory tree to *dst*, replacing any existing dst.

    Sibling packages (updater/, installer/) are version-less singletons
    living directly under <install_root>/. They are owned by the installer
    flow, not by any particular kernel version, so every install pass
    refreshes them to match the kernel being installed.
    """
    if dst.exists():
        shutil.rmtree(str(dst))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(src), str(dst), ignore=_PKG_IGNORE)
    print("[cbim] sibling package -> {}".format(dst))


def _sync_siblings_from_source_tree(source_parent: Path, install_root: Path) -> None:
    """Mirror sibling packages found under *source_parent* into *install_root*.

    Skips any sibling not present in the source tree, with a warning for
    updater/ since the launcher hard-requires it.
    """
    for name in _SIBLING_PACKAGES:
        src = source_parent / name
        if src.is_dir():
            _replace_sibling_package(src, install_root / name)
        elif name == "updater":
            print(
                "[cbim] warning: sibling updater/ not found at {}; "
                "launcher subcommands (upgrade/update/migrate) will fail "
                "until updater is installed.".format(src),
                file=sys.stderr,
            )


def _promote_launcher_from_kernel_dest(kernel_dest: Path, install_root: Path) -> None:
    """Relocate a bundled bin/ shipped inside the release tarball.

    Mirrors _promote_siblings_from_kernel_dest's contract: the release
    tarball drops bin/ alongside cbim_kernel/ under
    <install_root>/kernel/<version>/; lift its individual files up to
    <install_root>/bin/ where the launcher is expected to live.
    """
    bundled_bin = kernel_dest / "bin"
    if not bundled_bin.is_dir():
        return
    for name in _LAUNCHER_FILES:
        src = bundled_bin / name
        if not src.is_file():
            continue
        _refresh_one_launcher_file(src, install_root / "bin" / name)
    # Clean up the now-redundant bundled copy so version directories stay
    # focused on kernel content.
    try:
        shutil.rmtree(str(bundled_bin))
    except OSError:
        pass


def _promote_siblings_from_kernel_dest(kernel_dest: Path, install_root: Path) -> None:
    """Move sibling packages bundled inside *kernel_dest* up to *install_root*.

    The GitHub release tarball ships kernel files and sibling packages
    (updater/, optionally installer/) under one flat root. `_extract_tarball`
    drops everything into <install_root>/kernel/<version>/; this routine
    relocates the sibling subtrees to their canonical home so the launcher
    can find them.
    """
    for name in _SIBLING_PACKAGES:
        bundled = kernel_dest / name
        if not bundled.is_dir():
            continue
        target = install_root / name
        if target.exists():
            shutil.rmtree(str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(bundled), str(target))
        print("[cbim] sibling package -> {}".format(target))


def _refresh_one_launcher_file(src: Path, dst: Path) -> None:
    """Atomically replace *dst* with *src*'s contents.

    Windows quirk: the running launcher cannot be unlinked while in use, but
    `os.replace` on the same volume IS allowed to overwrite an open file —
    the old inode stays alive for the running process, the new bytes land at
    the path for any future invocation. We write to a sidecar `.new` first
    then `os.replace` it into position so a crash mid-copy never leaves a
    truncated launcher on disk.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".new")
    shutil.copyfile(str(src), str(tmp))
    try:
        # Preserve POSIX exec bit on `cbim` shell wrapper. No-op on Windows.
        shutil.copymode(str(src), str(tmp))
    except OSError:
        pass
    try:
        os.replace(str(tmp), str(dst))
    except OSError as exc:
        # Extremely rare on same-volume replace, but if Windows refuses
        # (e.g. AV holding a handle), leave the .new in place and tell the
        # user how to recover rather than half-applying the update.
        print(
            "[cbim] warning: could not refresh launcher {}: {}\n"
            "       New version staged at {}; re-run `cbim install` after "
            "closing any running cbim process, or manually rename "
            "{} -> {}.".format(dst, exc, tmp, tmp.name, dst.name),
            file=sys.stderr,
        )
        return
    print("[cbim] launcher -> {}".format(dst))


def _refresh_launcher(source_parent: Path, install_root: Path) -> None:
    """Mirror v1/src/bin/* launcher artifacts to <install_root>/bin/.

    Source layout: <source_parent>/bin/{cbim_launcher.py, cbim, cbim.cmd}
    where *source_parent* is the directory containing kernel/ (and the bin/
    sibling). For --local installs this is the v1/src/ checkout; for github
    installs the launcher source ships under the kernel tarball — handled by
    a separate helper.

    Silently skipped if bin/ isn't present in the source tree (release
    tarballs that pre-date bundled bin/ assets).
    """
    bin_src = source_parent / "bin"
    if not bin_src.is_dir():
        return
    bin_dst = install_root / "bin"
    for name in _LAUNCHER_FILES:
        src = bin_src / name
        if not src.is_file():
            continue
        _refresh_one_launcher_file(src, bin_dst / name)


def _extract_tarball(tarball: Path, dest: Path) -> None:
    """Extract *tarball* so that dest/ contains the kernel files directly.

    Handles two layouts:
    - Flat: tarball root contains cbim_kernel/, requirements.txt, VERSION
    - Wrapped: tarball root is a single directory wrapping the above

    In both cases the result is dest/ = kernel directory.
    """
    with tarfile.open(tarball, "r:gz") as tf:
        members = tf.getmembers()
        # Detect single-directory wrapper
        top_dirs = {m.name.split("/")[0] for m in members if m.name}
        if len(top_dirs) == 1:
            top = next(iter(top_dirs))
            # Strip the wrapper prefix when extracting
            dest.mkdir(parents=True, exist_ok=True)
            for member in members:
                rel = member.name[len(top):].lstrip("/")
                if not rel:
                    continue
                member.name = rel
                tf.extract(member, path=str(dest))
        else:
            dest.mkdir(parents=True, exist_ok=True)
            tf.extractall(str(dest))


def install_from_local(
    kernel_src: Path,
    version: Optional[str] = None,
    set_default: bool = True,
) -> Path:
    """Copy ``kernel_src`` to ``<install_root>/kernel/<version>/``.

    Idempotent: if destination already exists, returns it unchanged.
    If *set_default* is True (the default), activates the version as
    ``active_default``. Pass ``set_default=False`` to install without
    activating.
    """
    migrate_legacy_install_root()
    kernel_src = Path(kernel_src).resolve()
    if not kernel_src.is_dir():
        raise FileNotFoundError(
            "kernel source not found: {}".format(kernel_src)
        )

    if version is None:
        version = _read_version(kernel_src)

    install_root = registry.cbim_home()
    dest = install_root / "kernel" / version

    if dest.exists():
        print("[cbim] kernel {} already installed at {}".format(version, dest))
        registry.register(version, dest, venv_path(), source="local")
        if set_default or registry.get_default() is None:
            registry.set_default(version)
        # Still refresh siblings — caller may be re-running install precisely
        # to repair a missing/stale <install_root>/updater/.
        _sync_siblings_from_source_tree(kernel_src.parent, install_root)
        _refresh_launcher(kernel_src.parent, install_root)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(kernel_src), str(dest), ignore=_PKG_IGNORE)

    # Refresh sibling packages (updater/, installer/) from the source tree.
    # They live as singletons under <install_root>/, shared across kernel
    # versions, and must be present for the launcher to route upgrade /
    # update / migrate / install commands.
    _sync_siblings_from_source_tree(kernel_src.parent, install_root)

    # Refresh the PATH launcher (cbim, cbim.cmd, cbim_launcher.py) so
    # routing changes in the source tree actually reach the user's machine.
    _refresh_launcher(kernel_src.parent, install_root)

    registry.register(version, dest, venv_path(), source="local")
    if set_default or registry.get_default() is None:
        registry.set_default(version)

    print("[cbim] installed kernel {} -> {}".format(version, dest))
    return dest


def install_from_github(
    version: Optional[str] = None,
    set_default: bool = True,
    repo: Optional[str] = None,
) -> Path:
    """Download kernel tarball from GitHub Releases and install it.

    If *version* is None, fetches the latest published release.
    If *set_default* is True (the default), marks the version as
    ``active_default`` in ``<install_root>/versions.json``. Pass
    ``set_default=False`` to install without activating (e.g. for
    side-by-side testing).

    Returns the installed kernel path.
    """
    migrate_legacy_install_root()
    from updater.github import latest_version as _latest, download_tarball

    kwargs = {}
    if repo:
        kwargs["repo"] = repo

    if version is None:
        print("[cbim] fetching latest version from GitHub ...")
        version = _latest(**kwargs)
        print("[cbim] latest release: {}".format(version))

    install_root = registry.cbim_home()
    dest = install_root / "kernel" / version
    if dest.exists():
        print("[cbim] kernel {} already installed at {}".format(version, dest))
        registry.register(version, dest, venv_path(), source="github")
        if set_default or registry.get_default() is None:
            registry.set_default(version)
        return dest

    with tempfile.TemporaryDirectory(prefix="cbim-install-") as tmpdir:
        tarball = download_tarball(version, Path(tmpdir), **kwargs)
        print("[cbim] extracting -> {}".format(dest))
        _extract_tarball(tarball, dest)

    # Release tarballs bundle sibling packages (updater/, optionally
    # installer/) under the kernel root. Promote them to <install_root>/
    # so the launcher can route updater subcommands.
    _promote_siblings_from_kernel_dest(dest, install_root)

    # Same story for bin/ — if the tarball ships launcher artifacts under
    # kernel/<version>/bin/, lift them up to <install_root>/bin/.
    _promote_launcher_from_kernel_dest(dest, install_root)

    registry.register(version, dest, venv_path(), source="github")
    if set_default or registry.get_default() is None:
        registry.set_default(version)

    # Update shared venv with this version's requirements
    req = dest / "requirements.txt"
    if req.is_file():
        print("[cbim] updating shared venv ...")
        update_venv(req)

    print("[cbim] installed kernel {} -> {}".format(version, dest))
    return dest
