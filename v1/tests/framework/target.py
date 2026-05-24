"""Test target abstractions.

A `TestTarget` is the project the runner aims `claude -p` at. Two flavours:

  * `TmpProject`   — fresh CBIM install per test, isolated tempdir
  * `ExternalProject` — points at an existing on-disk project; no setup or
    teardown side effects (caller is responsible for the project state)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Protocol


REPO_ROOT = Path(__file__).resolve().parents[3]
KERNEL_SRC = REPO_ROOT / "v1" / "kernel"


class TestTarget(Protocol):
    project_root: Path

    def setup(self) -> None: ...
    def teardown(self) -> None: ...


# ---------------------------------------------------------------------------
# Tmp project — fresh install, isolated
# ---------------------------------------------------------------------------


def run_engine_init(project_dir: Path) -> None:
    """Run `python -m engine init` against project_dir as cwd."""
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{KERNEL_SRC}{os.pathsep}{env.get('PYTHONPATH', '')}"
    subprocess.run(
        [sys.executable, "-m", "engine", "init"],
        cwd=project_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def install_kernel(project_dir: Path) -> None:
    """Copy this repo's v1/kernel into <project>/.cbim/kernel/ so hooks can bootstrap."""
    dst = project_dir / ".cbim" / "kernel"
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(KERNEL_SRC, dst, dirs_exist_ok=True)


def build_template(template_dir: Path) -> Path:
    """One-shot CBIM install at template_dir; idempotent."""
    template_dir.mkdir(parents=True, exist_ok=True)
    if not (template_dir / ".cbim").is_dir():
        run_engine_init(template_dir)
    install_kernel(template_dir)
    return template_dir


class TmpProject:
    """Fresh per-instance copy of a CBIM template project.

    If `template_root` is None, builds a one-shot template in a sibling tempdir.
    Each `setup()` produces a fresh copy at `self.project_root`; `teardown()`
    removes it.
    """

    def __init__(self, template_root: Path | None = None):
        self._tmp_template_root: Path | None = None
        if template_root is None:
            self._tmp_template_root = Path(tempfile.mkdtemp(prefix="cbim_tmpl_"))
            self.template_root = build_template(self._tmp_template_root)
        else:
            self.template_root = template_root
        self._tmp_proj: Path | None = None
        self.project_root: Path = Path()

    def setup(self) -> None:
        self._tmp_proj = Path(tempfile.mkdtemp(prefix="cbim_proj_"))
        dst = self._tmp_proj / "proj"
        shutil.copytree(self.template_root, dst, symlinks=True)
        for sub in ("logs", "memory/short"):
            p = dst / ".cbim" / sub
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
            p.mkdir(parents=True, exist_ok=True)
        self.project_root = dst

    def teardown(self) -> None:
        if self._tmp_proj and self._tmp_proj.exists():
            shutil.rmtree(self._tmp_proj, ignore_errors=True)
            self._tmp_proj = None

    def cleanup_template(self) -> None:
        """Remove the auto-built template, if any."""
        if self._tmp_template_root and self._tmp_template_root.exists():
            shutil.rmtree(self._tmp_template_root, ignore_errors=True)
            self._tmp_template_root = None


# ---------------------------------------------------------------------------
# External project — operate on existing on-disk project; no side effects
# ---------------------------------------------------------------------------


class ExternalProject:
    """Points at an existing project. setup/teardown are no-ops."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def setup(self) -> None:
        return None

    def teardown(self) -> None:
        return None
