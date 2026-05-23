"""Aggregation of per-case results into a summary stats object."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class CaseStats:
    name: str
    passed: bool
    wall_time_s: float
    sub_checks_passed: int
    sub_checks_total: int
    top_failure: str | None
    input_tokens: int | None
    output_tokens: int | None
    arch_metrics: dict = field(default_factory=dict)


@dataclass
class AggregateStats:
    total: int
    passed: int
    failed: int
    pass_rate: float
    total_wall_time_s: float
    avg_wall_time_s: float
    total_input_tokens: int | None
    total_output_tokens: int | None
    by_group: dict[str, "AggregateStats"] = field(default_factory=dict)


def _sum_or_none(values: list[int | None]) -> int | None:
    """Sum ints, ignoring Nones; return None if every value is None."""
    nums = [v for v in values if isinstance(v, int)]
    if not nums:
        return None
    return sum(nums)


def _aggregate_flat(cases: list[CaseStats]) -> AggregateStats:
    total = len(cases)
    passed = sum(1 for c in cases if c.passed)
    failed = total - passed
    pass_rate = (passed / total) if total else 0.0
    total_wall = sum(c.wall_time_s for c in cases)
    avg_wall = (total_wall / total) if total else 0.0
    return AggregateStats(
        total=total,
        passed=passed,
        failed=failed,
        pass_rate=pass_rate,
        total_wall_time_s=total_wall,
        avg_wall_time_s=avg_wall,
        total_input_tokens=_sum_or_none([c.input_tokens for c in cases]),
        total_output_tokens=_sum_or_none([c.output_tokens for c in cases]),
    )


def aggregate(
    cases: list[CaseStats],
    group_fn: Callable[[CaseStats], str] | None = None,
) -> AggregateStats:
    """Aggregate flat stats; if group_fn is given, also nest per-group rollups."""
    agg = _aggregate_flat(cases)
    if group_fn is None:
        return agg
    groups: dict[str, list[CaseStats]] = {}
    for c in cases:
        groups.setdefault(group_fn(c), []).append(c)
    agg.by_group = {k: _aggregate_flat(v) for k, v in groups.items()}
    return agg
