"""One-shot migration of the legacy ``~/.cbim/`` install to the new
``<install_root>/Cbim-CC/`` location.

Invoked by ``updater.install.install_from_local`` and
``install_from_github`` before they do any installation work. Idempotent:
returns immediately if the legacy directory is absent, and refuses to
clobber a non-empty new location.

Migration strategy: atomic rename via a ``.cbim.migrating`` staging name
(crash-safe: at worst the user is left with the staging dir, never with
two copies of the data). After the rename, rewrite ``versions.json`` so
the recorded ``kernel_path`` / ``venv_path`` entries point at the new
location.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from updater.paths import install_root


def _legacy_root() -> Path:
    return Path.home() / ".cbim"


def _is_empty_dir(path: Path) -> bool:
    if not path.exists():
        return True
    if not path.is_dir():
        return False
    try:
        return next(path.iterdir(), None) is None
    except OSError:
        return False


def _rewrite_versions_json(new_root: Path, legacy_root: Path) -> None:
    """Rewrite kernel_path / venv_path entries in versions.json so any
    absolute paths that pointed inside the legacy root now point inside
    the new root. Quietly no-ops if the file is absent or malformed."""
    vf = new_root / "versions.json"
    if not vf.is_file():
        return
    try:
        with vf.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    if not isinstance(data, dict):
        return

    legacy_str = str(legacy_root)
    new_str = str(new_root)
    installed = data.get("installed")
    if not isinstance(installed, dict):
        return

    changed = False
    for _ver, entry in installed.items():
        if not isinstance(entry, dict):
            continue
        for key in ("kernel_path", "venv_path"):
            val = entry.get(key)
            if not isinstance(val, str):
                continue
            if val == legacy_str or val.startswith(legacy_str + os.sep):
                entry[key] = new_str + val[len(legacy_str):]
                changed = True

    if not changed:
        return

    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp = vf.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(payload)
    os.replace(tmp, vf)


def _print_path_hint(new_root: Path) -> None:
    bin_path = new_root / "bin"
    print("[cbim] migration complete -> {}".format(new_root))
    print("[cbim] PATH still points at the old ~/.cbim/bin -- update it:")
    if os.name == "nt":
        print('       setx PATH "%LOCALAPPDATA%\\Cbim-CC\\bin;%PATH%"')
    else:
        print('       export PATH="{}:$PATH"'.format(bin_path))


def migrate_legacy_install_root() -> bool:
    """Move ``~/.cbim/`` -> install_root() if applicable. Returns True if a
    migration ran, False if nothing was done."""
    legacy = _legacy_root().resolve() if _legacy_root().exists() else _legacy_root()
    new = install_root()

    # Same location => the user's CBIM_INSTALL_ROOT happens to point at
    # ~/.cbim. Nothing to do.
    try:
        if legacy.resolve() == new.resolve() if new.exists() else False:
            return False
    except OSError:
        pass
    if str(legacy) == str(new):
        return False

    if not legacy.exists():
        return False

    if not legacy.is_dir():
        # Some strange leftover (a file at ~/.cbim). Skip with a warning.
        print(
            "[cbim] warning: ~/.cbim exists but is not a directory ({}); "
            "skipping migration.".format(legacy)
        )
        return False

    if new.exists() and not _is_empty_dir(new):
        print(
            "[cbim] warning: both legacy ({}) and new ({}) install roots exist "
            "and the new one is non-empty; not migrating. "
            "Resolve manually if needed.".format(legacy, new)
        )
        return False

    # Drop an empty placeholder if it happens to exist at the new location.
    if new.exists():
        try:
            new.rmdir()
        except OSError as exc:
            print(
                "[cbim] warning: could not remove empty new root {}: {}; "
                "skipping migration.".format(new, exc)
            )
            return False

    new.parent.mkdir(parents=True, exist_ok=True)

    # Atomic two-step: rename legacy -> staging -> new. If a crash happens
    # between the two renames, the user is left with `.cbim.migrating`
    # right next to the legacy spot — recoverable, never duplicated.
    staging = legacy.parent / ".cbim.migrating"
    if staging.exists():
        # Stale staging from a previous interrupted run. Refuse to clobber.
        print(
            "[cbim] warning: stale migration staging exists at {}. "
            "Resolve manually (rename to {} or delete) and retry.".format(
                staging, new
            )
        )
        return False

    print("[cbim] migrating {} -> {}".format(legacy, new))
    os.rename(legacy, staging)
    try:
        os.rename(staging, new)
    except OSError:
        # Cross-volume or other rename failure. Fall back to copy + cleanup.
        # NB: this is best-effort and not atomic — but we only get here when
        # os.rename has already moved legacy *out* of its original spot,
        # so the user's data is still in `staging` and recoverable.
        shutil.copytree(str(staging), str(new))
        shutil.rmtree(str(staging))

    _rewrite_versions_json(new, legacy)
    _print_path_hint(new)
    return True
