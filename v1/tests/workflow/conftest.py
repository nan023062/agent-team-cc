"""Pytest config for v1/tests/workflow/.

Wires the framework into pytest:

  * `workflow` marker — opt-in; auto-skipped without ANTHROPIC_API_KEY or
    `claude` on PATH.
  * `cbim_template_project` (session) — one-shot CBIM install template.
  * `workflow_target` (per test)      — a TmpProject bound to a fresh copy of
    the template; the framework runner takes it from there.
  * Per-test log-copy + sidecar meta JSON (when BENCH_LOGS_DIR is set) for
    run-bench.sh to build the markdown report afterwards.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from .framework.target import TmpProject, build_template


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "workflow: end-to-end loop test (requires ANTHROPIC_API_KEY and `claude` CLI on PATH; costs real API spend)",
    )


def pytest_collection_modifyitems(config, items):
    skip_no_key = pytest.mark.skip(reason="ANTHROPIC_API_KEY not set")
    skip_no_cli = pytest.mark.skip(reason="`claude` CLI not on PATH")
    skip_opt_in = pytest.mark.skip(reason="workflow tests are opt-in; pass `-m workflow` to run")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_cli = shutil.which("claude") is not None
    # `-m workflow` (or any expression containing `workflow`) opts in; otherwise
    # the case is auto-skipped even when API key + CLI are present.
    markexpr = (config.getoption("markexpr") or config.getini("markers") or "")
    opted_in = "workflow" in (markexpr if isinstance(markexpr, str) else "")
    for item in items:
        if "workflow" not in item.keywords:
            continue
        if not opted_in:
            item.add_marker(skip_opt_in)
        elif not has_key:
            item.add_marker(skip_no_key)
        elif not has_cli:
            item.add_marker(skip_no_cli)


@pytest.fixture(scope="session")
def cbim_template_project(tmp_path_factory) -> Path:
    """One-shot CBIM install; per-test isolation comes from `workflow_target`."""
    template = tmp_path_factory.mktemp("cbim_template")
    return build_template(template)


@pytest.fixture
def workflow_target(cbim_template_project: Path, request):
    """Per-test TmpProject bound to the shared template.

    Yields the TmpProject (not the path) so tests can pass it straight to
    `framework.run(target, prompt)`. We override `template_root` on a fresh
    instance so we don't re-install per test; setup() does the per-test copy.

    Finalizer: if BENCH_LOGS_DIR env var is set, copy the latest
    .cbim/logs/session_*.log out of the tmp project into
    <BENCH_LOGS_DIR>/<test_name>.log before the dir is removed.
    """
    target = TmpProject(template_root=cbim_template_project)
    target.setup()
    try:
        yield target
        bench_logs_dir = os.environ.get("BENCH_LOGS_DIR")
        if bench_logs_dir:
            logs_dir = target.project_root / ".cbim" / "logs"
            if logs_dir.is_dir():
                sessions = sorted(
                    logs_dir.glob("session_*.log"), key=lambda p: p.stat().st_mtime
                )
                if sessions:
                    out_dir = Path(bench_logs_dir)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sessions[-1], out_dir / f"{request.node.name}.log")
    finally:
        target.teardown()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Sidecar a JSON file per test (call phase) with outcome / duration / longrepr.

    Only writes when BENCH_LOGS_DIR is set. Used by framework.reporter to
    build the per-case results table without re-parsing pytest stdout.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return
    bench_logs_dir = os.environ.get("BENCH_LOGS_DIR")
    if not bench_logs_dir:
        return
    out_dir = Path(bench_logs_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "nodeid": report.nodeid,
        "test_name": item.name,
        "outcome": report.outcome,
        "duration_s": round(getattr(report, "duration", 0.0), 2),
        "longrepr": str(report.longrepr) if report.failed else "",
    }
    (out_dir / f"{item.name}.meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
