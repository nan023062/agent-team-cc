"""AUDIT loop end-to-end tests.

Audit is a cross-cutting concern (Phase 16 / 16b) — not one of the four
design loops, hence its own file. Five positive cases, one per registered
audit check; no negative flavor (audit should never be 'not called' when the
user explicitly asks for a governance check).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..framework import assert_audit_loop, parse_log, run
from ..framework.target import TmpProject


PROMPTS = Path(__file__).parent / "prompts"


def _run_audit_case(
    target: TmpProject,
    prompt_file: str,
    *,
    check_name: str,
    expected_agent: str,
    timeout: int = 300,
) -> None:
    prompt = (PROMPTS / prompt_file).read_text(encoding="utf-8")
    result = run(target, prompt, timeout=timeout)
    events = parse_log(result.session_log)
    verdict = assert_audit_loop(
        events,
        target.project_root,
        check_name=check_name,
        expected_agent=expected_agent,
    )
    assert verdict.passed, "\n".join(
        verdict.diagnostics
        + [
            f"log={result.session_log_path}",
            f"exit={result.exit_code}",
            f"wall={result.wall_time_s:.1f}s",
        ]
    )


@pytest.mark.workflow
def test_loop_audit_index_positive(workflow_target: TmpProject) -> None:
    _run_audit_case(
        workflow_target,
        "audit_index_positive.md",
        check_name="index_consistency",
        expected_agent="architect",
    )


@pytest.mark.workflow
def test_loop_audit_tree_positive(workflow_target: TmpProject) -> None:
    _run_audit_case(
        workflow_target,
        "audit_tree_positive.md",
        check_name="dna_tree",
        expected_agent="architect",
    )


@pytest.mark.workflow
def test_loop_audit_dna_fission_positive(workflow_target: TmpProject) -> None:
    _run_audit_case(
        workflow_target,
        "audit_dna_fission_positive.md",
        check_name="dna_fission",
        expected_agent="architect",
    )


@pytest.mark.workflow
def test_loop_audit_agent_fission_positive(workflow_target: TmpProject) -> None:
    _run_audit_case(
        workflow_target,
        "audit_agent_fission_positive.md",
        check_name="agent_fission",
        expected_agent="hr",
    )


@pytest.mark.workflow
def test_loop_audit_memory_positive(workflow_target: TmpProject) -> None:
    _run_audit_case(
        workflow_target,
        "audit_memory_positive.md",
        check_name="memory_threshold",
        expected_agent="architect",
    )
