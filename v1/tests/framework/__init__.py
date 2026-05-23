"""Workflow test framework.

Public API surface:

    from v1.tests.framework import (
        TestTarget, TmpProject, ExternalProject,
        Result, run,
        Verdict, parse_log,
        assert_execution_loop, assert_architect_loop,
        assert_hr_loop, assert_memory_loop, assert_audit_loop,
        CaseStats, AggregateStats, aggregate,
        render_markdown, render_markdown_single, render_stdout,
    )
"""

from __future__ import annotations

from .log_assert import (
    Verdict,
    parse_log,
    assert_execution_loop,
    assert_architect_loop,
    assert_hr_loop,
    assert_memory_loop,
    assert_audit_loop,
)
from .reporter import (
    render_markdown,
    render_markdown_single,
    render_stdout,
)
from .result import Result
from .runner import run
from .stats import CaseStats, AggregateStats, aggregate
from .target import TestTarget, TmpProject, ExternalProject

__all__ = [
    "TestTarget",
    "TmpProject",
    "ExternalProject",
    "Result",
    "run",
    "Verdict",
    "parse_log",
    "assert_execution_loop",
    "assert_architect_loop",
    "assert_hr_loop",
    "assert_memory_loop",
    "assert_audit_loop",
    "CaseStats",
    "AggregateStats",
    "aggregate",
    "render_markdown",
    "render_markdown_single",
    "render_stdout",
]
