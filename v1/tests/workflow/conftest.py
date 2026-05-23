"""End-to-end workflow test fixtures.

These tests run the real `claude` CLI in headless mode (`-p`) against a
freshly-installed CBIM project, then inspect `.cbim/logs/session_*.log` to
verify which loops the coordinator drove. Each test costs a real Anthropic
API call.

Pytest is configured to:
  - register the `workflow` marker
  - auto-skip workflow tests when ANTHROPIC_API_KEY is unset
  - auto-skip workflow tests when the `claude` CLI is not on PATH
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
KERNEL_SRC = REPO_ROOT / "v1" / "kernel"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "workflow: end-to-end loop test (requires ANTHROPIC_API_KEY and `claude` CLI on PATH; costs real API spend)",
    )


def pytest_collection_modifyitems(config, items):
    skip_no_key = pytest.mark.skip(reason="ANTHROPIC_API_KEY not set")
    skip_no_cli = pytest.mark.skip(reason="`claude` CLI not on PATH")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_cli = shutil.which("claude") is not None
    for item in items:
        if "workflow" not in item.keywords:
            continue
        if not has_key:
            item.add_marker(skip_no_key)
        elif not has_cli:
            item.add_marker(skip_no_cli)


def _run_engine_init(project_dir: Path) -> None:
    """Run `python3 -m engine init` against project_dir as cwd."""
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


def _install_kernel(project_dir: Path) -> None:
    """Copy this repo's v1/kernel into <project>/.cbim/kernel/ so hooks can bootstrap."""
    dst = project_dir / ".cbim" / "kernel"
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(KERNEL_SRC, dst, dirs_exist_ok=True)


@pytest.fixture(scope="session")
def cbim_template_project(tmp_path_factory) -> Path:
    """One-shot CBIM install in a session-scoped tempdir.

    Per-test isolation is provided by `test_project`, which copies this
    template fresh for each test.
    """
    template = tmp_path_factory.mktemp("cbim_template")
    _run_engine_init(template)
    _install_kernel(template)
    return template


@pytest.fixture
def test_project(cbim_template_project: Path, tmp_path: Path) -> Path:
    """Per-test fresh copy of the template with logs/short memory cleared."""
    dst = tmp_path / "proj"
    shutil.copytree(cbim_template_project, dst, symlinks=True)
    # Wipe any state that may have leaked from prior fixture usage
    for sub in ("logs", "memory/short"):
        p = dst / ".cbim" / sub
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
        p.mkdir(parents=True, exist_ok=True)
    return dst
