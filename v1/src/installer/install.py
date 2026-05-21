"""Core kernel installation logic."""
from __future__ import annotations

import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

from installer import registry
from installer.migrate_install_root import migrate_legacy_install_root
from installer.venv_mgr import update_venv, venv_path


def _read_version(kernel_src: Path) -> str:
    version_file = kernel_src / "VERSION"
    if not version_file.is_file():
        raise FileNotFoundError(
            "VERSION file not found at {}".format(version_file)
        )
    return version_file.read_text(encoding="utf-8").strip()


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


def install_from_local(kernel_src: Path, version: Optional[str] = None) -> Path:
    """Copy ``kernel_src`` to ``<install_root>/kernel/<version>/``.

    Idempotent: if destination already exists, returns it unchanged.
    """
    migrate_legacy_install_root()
    kernel_src = Path(kernel_src).resolve()
    if not kernel_src.is_dir():
        raise FileNotFoundError(
            "kernel source not found: {}".format(kernel_src)
        )

    if version is None:
        version = _read_version(kernel_src)

    dest = registry.cbim_home() / "kernel" / version

    if dest.exists():
        print("[cbim] kernel {} already installed at {}".format(version, dest))
        registry.register(version, dest, venv_path(), source="local")
        if registry.get_default() is None:
            registry.set_default(version)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        str(kernel_src),
        str(dest),
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    registry.register(version, dest, venv_path(), source="local")
    if registry.get_default() is None:
        registry.set_default(version)

    print("[cbim] installed kernel {} -> {}".format(version, dest))
    return dest


def install_from_github(
    version: Optional[str] = None,
    set_default: bool = False,
    repo: Optional[str] = None,
) -> Path:
    """Download kernel tarball from GitHub Releases and install it.

    If *version* is None, fetches the latest published release.
    If *set_default* is True (or no default is set), marks the version
    as ``active_default`` in ``<install_root>/versions.json``.

    Returns the installed kernel path.
    """
    migrate_legacy_install_root()
    from installer.github import latest_version as _latest, download_tarball

    kwargs = {}
    if repo:
        kwargs["repo"] = repo

    if version is None:
        print("[cbim] fetching latest version from GitHub ...")
        version = _latest(**kwargs)
        print("[cbim] latest release: {}".format(version))

    dest = registry.cbim_home() / "kernel" / version
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
