"""Tests for installer.migrate_install_root.migrate_legacy_install_root.

Covers architect §C:
  1. No legacy -> no-op, returns False.
  2. Legacy exists, new does not -> rename to new location; legacy disappears.
  3. Both exist and new is non-empty -> warn + no-op; both untouched.
  4. Both exist but new is empty -> migrate (drop empty new, move legacy in).
  5. versions.json kernel_path / venv_path get rewritten to point at new root.
  6. Stale ``.cbim.migrating`` staging dir -> no-op.

Isolation strategy: monkeypatch both
  - installer.migrate_install_root._legacy_root  (so "legacy" lives under tmp_path)
  - installer.paths.install_root via CBIM_INSTALL_ROOT env  (so "new" lives under tmp_path)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_INSTALLER_SRC = _HERE.parent / "src"
_p = str(_INSTALLER_SRC)
if _p not in sys.path:
    sys.path.insert(0, _p)


@pytest.fixture
def fake_roots(tmp_path, monkeypatch):
    """Provide isolated (legacy, new) install-root paths under tmp_path.

    Returns a tuple ``(legacy_path, new_path)``. Neither exists yet.
    """
    legacy = tmp_path / "legacy_cbim"
    new = tmp_path / "new_root" / "Cbim-CC"

    from installer import migrate_install_root as mod

    monkeypatch.setattr(mod, "_legacy_root", lambda: legacy)
    monkeypatch.setenv("CBIM_INSTALL_ROOT", str(new))
    return legacy, new


def _seed_legacy(legacy: Path) -> None:
    """Populate legacy with a realistic-ish layout + versions.json."""
    (legacy / "kernel" / "1.2.3").mkdir(parents=True)
    (legacy / "kernel" / "1.2.3" / "VERSION").write_text("1.2.3", encoding="utf-8")
    (legacy / "venv" / "bin").mkdir(parents=True)
    (legacy / "venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")
    versions = {
        "active_default": "1.2.3",
        "installed": {
            "1.2.3": {
                "installed_at": "2026-05-21T00:00:00Z",
                "kernel_path": str(legacy / "kernel" / "1.2.3"),
                "venv_path": str(legacy / "venv"),
                "source": "local",
            }
        },
    }
    (legacy / "versions.json").write_text(
        json.dumps(versions, indent=2), encoding="utf-8"
    )


def test_noop_when_legacy_absent(fake_roots):
    from installer.migrate_install_root import migrate_legacy_install_root

    legacy, new = fake_roots
    assert not legacy.exists()
    assert migrate_legacy_install_root() is False
    assert not new.exists()


def test_migrates_when_only_legacy_exists(fake_roots):
    from installer.migrate_install_root import migrate_legacy_install_root

    legacy, new = fake_roots
    _seed_legacy(legacy)

    assert migrate_legacy_install_root() is True
    assert not legacy.exists(), "legacy directory should have been moved"
    assert new.is_dir()
    assert (new / "kernel" / "1.2.3" / "VERSION").read_text(encoding="utf-8") == "1.2.3"
    assert (new / "venv" / "bin" / "python").is_file()


def test_versions_json_paths_rewritten(fake_roots):
    from installer.migrate_install_root import migrate_legacy_install_root

    legacy, new = fake_roots
    _seed_legacy(legacy)

    migrate_legacy_install_root()

    data = json.loads((new / "versions.json").read_text(encoding="utf-8"))
    entry = data["installed"]["1.2.3"]
    assert entry["kernel_path"] == str(new / "kernel" / "1.2.3")
    assert entry["venv_path"] == str(new / "venv")
    # Make sure no leftover legacy path string survived.
    assert str(legacy) not in json.dumps(data)


def test_skips_when_new_root_nonempty(fake_roots, capsys):
    from installer.migrate_install_root import migrate_legacy_install_root

    legacy, new = fake_roots
    _seed_legacy(legacy)
    new.mkdir(parents=True)
    (new / "marker.txt").write_text("hands off", encoding="utf-8")

    assert migrate_legacy_install_root() is False
    # Both untouched
    assert legacy.is_dir()
    assert (legacy / "kernel" / "1.2.3" / "VERSION").is_file()
    assert (new / "marker.txt").read_text(encoding="utf-8") == "hands off"

    out = capsys.readouterr().out
    assert "non-empty" in out


def test_migrates_when_new_root_is_empty_dir(fake_roots):
    from installer.migrate_install_root import migrate_legacy_install_root

    legacy, new = fake_roots
    _seed_legacy(legacy)
    new.mkdir(parents=True)  # empty placeholder

    assert migrate_legacy_install_root() is True
    assert not legacy.exists()
    assert (new / "kernel" / "1.2.3" / "VERSION").is_file()


def test_skips_when_stale_staging_present(fake_roots, capsys):
    from installer.migrate_install_root import migrate_legacy_install_root

    legacy, new = fake_roots
    _seed_legacy(legacy)
    staging = legacy.parent / ".cbim.migrating"
    staging.mkdir()
    (staging / "leftover").write_text("oops", encoding="utf-8")

    assert migrate_legacy_install_root() is False
    # Legacy untouched, staging untouched.
    assert legacy.is_dir()
    assert (staging / "leftover").is_file()
    out = capsys.readouterr().out
    assert "staging" in out
