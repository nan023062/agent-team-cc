"""MEMORY loop end-to-end tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from .framework import assert_memory_loop, parse_log, run
from .framework.target import TmpProject


PROMPTS = Path(__file__).parent / "prompts"


@pytest.mark.workflow
def test_loop_memory_positive(workflow_target: TmpProject) -> None:
    prompt = (PROMPTS / "memory_positive.md").read_text(encoding="utf-8")
    result = run(workflow_target, prompt, timeout=300)
    events = parse_log(result.session_log)
    verdict = assert_memory_loop(events, workflow_target.project_root, positive=True)
    assert verdict.passed, "\n".join(
        verdict.diagnostics
        + [
            f"log={result.session_log_path}",
            f"exit={result.exit_code}",
            f"wall={result.wall_time_s:.1f}s",
        ]
    )


@pytest.mark.workflow
def test_loop_memory_negative(workflow_target: TmpProject) -> None:
    prompt = (PROMPTS / "memory_negative.md").read_text(encoding="utf-8")
    result = run(workflow_target, prompt, timeout=180)
    events = parse_log(result.session_log)
    verdict = assert_memory_loop(events, workflow_target.project_root, positive=False)
    assert verdict.passed, "\n".join(
        verdict.diagnostics
        + [
            f"log={result.session_log_path}",
            f"exit={result.exit_code}",
            f"wall={result.wall_time_s:.1f}s",
        ]
    )
