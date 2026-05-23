"""MEMORY loop end-to-end tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from .log_assert import assert_memory_loop, parse_log
from .runner import run_claude


PROMPTS = Path(__file__).parent / "prompts"


@pytest.mark.workflow
def test_loop_memory_positive(test_project: Path) -> None:
    prompt = (PROMPTS / "memory_positive.md").read_text(encoding="utf-8")
    run = run_claude(test_project, prompt, timeout=300)
    events = parse_log(run.session_log)
    verdict = assert_memory_loop(events, test_project, positive=True)
    assert verdict.passed, "\n".join(
        verdict.diagnostics
        + [f"log={run.session_log_path}", f"exit={run.exit_code}", f"wall={run.wall_time_s:.1f}s"]
    )


@pytest.mark.workflow
def test_loop_memory_negative(test_project: Path) -> None:
    prompt = (PROMPTS / "memory_negative.md").read_text(encoding="utf-8")
    run = run_claude(test_project, prompt, timeout=180)
    events = parse_log(run.session_log)
    verdict = assert_memory_loop(events, test_project, positive=False)
    assert verdict.passed, "\n".join(
        verdict.diagnostics
        + [f"log={run.session_log_path}", f"exit={run.exit_code}", f"wall={run.wall_time_s:.1f}s"]
    )
