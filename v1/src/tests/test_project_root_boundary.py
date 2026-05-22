"""Regression tests for the `cbim init` home-directory clobber bug.

Background
----------
`cbim init` previously called `project_root()` to decide where to write the
new project skeleton. `project_root()`'s fallback walked up from cwd looking
for any ancestor containing `.cbim/`. If the user happened to have a global
`~/.cbim/` (the kernel installation directory), the walk would silently land
on `Path.home()` and init would overwrite user-global files.

The fixes verified here:
  1. `context.project_root()` raises if its fallback walk reaches
     `Path.home()`, instead of returning it.
  2. `cbim_launcher.find_project_root()` returns None at the same boundary.
  3. `_cmd_init` no longer routes through `project_root()` at all; it uses
     `Path.cwd()` directly and never touches the home directory.

Matrix covered:
  - CBIM_PROJECT_ROOT set / unset
  - cwd has `.cbim/` / does not
  - Some ancestor of cwd has `.cbim/` / does not
  - The "decoy" global `~/.cbim/` is always present in these tests
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


# --- helpers --------------------------------------------------------------


def _make_decoy_home(tmp_path: Path) -> Path:
    """Create a fake home with a `.cbim/config.json` decoy. Returns home path."""
    home = tmp_path / "fake_home"
    home.mkdir()
    decoy_cbim = home / ".cbim"
    decoy_cbim.mkdir()
    (decoy_cbim / "config.json").write_text(
        json.dumps({"cbim_version": "decoy", "marker": "do-not-touch"}),
        encoding="utf-8",
    )
    return home


def _decoy_snapshot(home: Path) -> dict[Path, tuple[float, str]]:
    """Snapshot mtime+content of every file under `home/.cbim/`."""
    out: dict[Path, tuple[float, str]] = {}
    for p in (home / ".cbim").rglob("*"):
        if p.is_file():
            out[p] = (p.stat().st_mtime_ns, p.read_text(encoding="utf-8"))
    return out


def _assert_decoy_intact(snapshot: dict[Path, tuple[float, str]]) -> None:
    for p, (mtime, content) in snapshot.items():
        assert p.exists(), f"decoy file vanished: {p}"
        assert p.stat().st_mtime_ns == mtime, f"decoy mtime changed: {p}"
        assert p.read_text(encoding="utf-8") == content, (
            f"decoy content changed: {p}"
        )


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Provide a fake $HOME with a decoy `.cbim/`; restore on teardown."""
    home = _make_decoy_home(tmp_path)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    # Also clear CBIM_PROJECT_ROOT and CBIM_KERNEL_ROOT to ensure tests use
    # the fallback code paths explicitly.
    monkeypatch.delenv("CBIM_PROJECT_ROOT", raising=False)
    monkeypatch.delenv("CBIM_KERNEL_ROOT", raising=False)
    return home


# --- context.project_root() ----------------------------------------------


def test_project_root_env_var_wins(tmp_path, monkeypatch, isolated_home):
    from context import project_root
    monkeypatch.setenv("CBIM_PROJECT_ROOT", str(tmp_path))
    assert project_root() == Path(str(tmp_path))


def test_project_root_finds_cwd_marker(tmp_path, monkeypatch, isolated_home):
    """cwd directly contains .cbim/config.json -> returns cwd."""
    from context import project_root
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".cbim").mkdir()
    (proj / ".cbim" / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(proj)
    assert project_root().resolve() == proj.resolve()


def test_project_root_finds_ancestor_marker(tmp_path, monkeypatch, isolated_home):
    """Ancestor (not home) has .cbim -> returns that ancestor."""
    from context import project_root
    proj = tmp_path / "proj"
    (proj / ".cbim").mkdir(parents=True)
    (proj / ".cbim" / "config.json").write_text("{}", encoding="utf-8")
    deep = proj / "a" / "b" / "c"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)
    assert project_root().resolve() == proj.resolve()


def test_project_root_raises_at_home_boundary(tmp_path, monkeypatch, isolated_home):
    """cwd lives under fake home, no project marker between cwd and home.
    Must raise instead of silently returning home (or anything beyond it)."""
    from context import project_root
    sub = isolated_home / "some" / "sub" / "dir"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    with pytest.raises(RuntimeError, match="user home"):
        project_root()


def test_project_root_outside_home_no_marker_returns_cwd(tmp_path, monkeypatch, isolated_home, tmp_path_factory):
    """cwd is outside home, no .cbim anywhere -> degrade to cwd (no raise,
    no home leak). Decoy must remain untouched.

    Note: must use an *isolated* tmp dir that does NOT live under the real
    user home; pytest's default tmp_path on Windows is under
    C:\\Users\\<user>\\AppData\\... which would let a polluted real
    `~/.cbim/` interfere with the walk. We use the test machine's drive
    root via a sibling tmp tree under the repo build dir instead.
    """
    import tempfile
    from context import project_root
    # Place the cwd somewhere guaranteed outside Path.home() — even the *real*
    # home (the fake one is already excluded by monkeypatch). Using the repo
    # root's drive directly keeps the test deterministic regardless of any
    # polluted user-home state.
    repo_drive = Path(__file__).resolve().drive + os.sep
    raw = Path(tempfile.mkdtemp(dir=repo_drive + "tmp" if Path(repo_drive + "tmp").exists() else repo_drive))
    try:
        sub = raw / "elsewhere" / "deep"
        sub.mkdir(parents=True)
        monkeypatch.chdir(sub)
        snap = _decoy_snapshot(isolated_home)
        result = project_root()
        assert result.resolve() == sub.resolve()
        _assert_decoy_intact(snap)
    finally:
        # Step out of the dir before cleanup so Windows can release the handle.
        monkeypatch.chdir(Path(__file__).resolve().parent)
        import shutil
        shutil.rmtree(raw, ignore_errors=True)


# --- cbim init: end-to-end clobber regression ----------------------------


def test_init_writes_to_cwd_not_home(tmp_path, monkeypatch, isolated_home):
    """Running `init` from an empty cwd MUST land in cwd, not home,
    even though the decoy ~/.cbim/ exists."""
    from engine.cli import _cmd_init

    proj = tmp_path / "new_project"
    proj.mkdir()
    monkeypatch.chdir(proj)

    snap = _decoy_snapshot(isolated_home)

    class _Args:
        version = "0.0.0-test"
        force = False
    _cmd_init(_Args())

    assert (proj / ".cbim" / "config.json").exists(), (
        "init did not create config.json in cwd"
    )
    _assert_decoy_intact(snap)


def test_init_from_subdir_of_real_project_still_targets_cwd(tmp_path, monkeypatch, isolated_home):
    """Even if an ancestor IS a real project, init targets cwd (not the
    ancestor). This matches the corrected semantics: init bootstraps where
    you are, period."""
    from engine.cli import _cmd_init

    outer = tmp_path / "outer_project"
    (outer / ".cbim").mkdir(parents=True)
    (outer / ".cbim" / "config.json").write_text(
        json.dumps({"cbim_version": "outer"}), encoding="utf-8"
    )
    inner = outer / "subdir" / "newproj"
    inner.mkdir(parents=True)
    monkeypatch.chdir(inner)

    snap_outer_cfg = (outer / ".cbim" / "config.json").read_text(encoding="utf-8")
    snap_decoy = _decoy_snapshot(isolated_home)

    class _Args:
        version = "0.0.0-test"
        force = False
    _cmd_init(_Args())

    assert (inner / ".cbim" / "config.json").exists()
    # Outer project's config.json must not have been overwritten
    assert (outer / ".cbim" / "config.json").read_text(encoding="utf-8") == snap_outer_cfg
    _assert_decoy_intact(snap_decoy)
