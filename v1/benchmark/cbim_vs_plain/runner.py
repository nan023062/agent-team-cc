"""A/B benchmark: run each task in plain mode and in CBIM mode.

Plain mode: ephemeral copy of fixture, no `.cbim/`, no `.claude/`.
CBIM mode: ephemeral copy of fixture, then `engine init` to install CBIM.

Both modes run the same prompt via the framework's `runner.run` against an
`ExternalProject` pointing at the ephemeral copy.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from v1.tests.workflow.framework.result import Result
from v1.tests.workflow.framework.runner import run
from v1.tests.workflow.framework.target import ExternalProject, run_engine_init


@dataclass
class ModeResult:
    mode: str  # "plain" | "cbim"
    project_root: Path
    success: bool
    result: Result
    arch_metrics: dict = field(default_factory=dict)


@dataclass
class AbResult:
    task_name: str
    plain: ModeResult
    cbim: ModeResult


def _copy_fixture(fixture_root: Path, suffix: str) -> Path:
    """Materialize a fresh copy of the fixture in a tempdir. Returns the project root."""
    tmp = Path(tempfile.mkdtemp(prefix=f"cbimvsplain_{suffix}_"))
    proj = tmp / "proj"
    shutil.copytree(fixture_root, proj)
    return proj


def _make_plain_project(fixture_root: Path) -> Path:
    proj = _copy_fixture(fixture_root, "plain")
    # Defensive: ensure no CBIM artifacts ever leak in.
    for d in (".cbim", ".claude", ".dna"):
        p = proj / d
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    return proj


def _make_cbim_project(fixture_root: Path) -> Path:
    proj = _copy_fixture(fixture_root, "cbim")
    run_engine_init(proj)
    return proj


def _safe_arch_metrics(task_mod, result: Result, project_root: Path, baseline_root: Path) -> dict:
    try:
        return task_mod.arch_metrics_extract(result, project_root, baseline_root)
    except Exception as e:  # noqa: BLE001
        return {"_error": f"arch_metrics_extract failed: {e!r}"}


def _evaluate_success(task_mod, project_root: Path, result: Result) -> bool:
    """Run the task's success_check and (if defined) stdout_check."""
    ok = bool(task_mod.success_check(project_root))
    if not ok:
        return False
    stdout_check = getattr(task_mod, "stdout_check", None)
    if stdout_check is not None:
        try:
            return bool(stdout_check(result.stdout))
        except Exception:  # noqa: BLE001
            return False
    return True


def run_ab(task_mod, fixture_root: Path, *, timeout: int = 300, keep: bool = False) -> AbResult:
    """Run a single task in plain and CBIM mode against fresh fixture copies."""
    # ---- Plain ----
    plain_proj = _make_plain_project(fixture_root)
    plain_result = run(ExternalProject(plain_proj), task_mod.PROMPT, timeout=timeout)
    plain_ok = _evaluate_success(task_mod, plain_proj, plain_result)
    plain_metrics = _safe_arch_metrics(task_mod, plain_result, plain_proj, fixture_root)
    plain_mode = ModeResult(
        mode="plain",
        project_root=plain_proj,
        success=plain_ok,
        result=plain_result,
        arch_metrics=plain_metrics,
    )

    # ---- CBIM ----
    cbim_proj = _make_cbim_project(fixture_root)
    cbim_result = run(ExternalProject(cbim_proj), task_mod.PROMPT, timeout=timeout)
    cbim_ok = _evaluate_success(task_mod, cbim_proj, cbim_result)
    cbim_metrics = _safe_arch_metrics(task_mod, cbim_result, cbim_proj, fixture_root)
    cbim_mode = ModeResult(
        mode="cbim",
        project_root=cbim_proj,
        success=cbim_ok,
        result=cbim_result,
        arch_metrics=cbim_metrics,
    )

    return AbResult(task_name=task_mod.NAME, plain=plain_mode, cbim=cbim_mode)
