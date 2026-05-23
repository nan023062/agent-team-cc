"""Render A/B benchmark results as a side-by-side markdown report."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from .runner import AbResult


def _tok(v) -> str:
    if v is None:
        return "?"
    if isinstance(v, float):
        v = int(v)
    if v >= 1000:
        return f"{v / 1000:.1f}k"
    return str(v)


def _wall(s: float) -> str:
    return f"{s:.1f}s"


def _pct(a: float, b: float) -> str:
    if a == 0:
        return "n/a"
    return f"{((b - a) / a) * 100:+.0f}%"


def _delta(a, b) -> str:
    if a is None or b is None:
        return "?"
    if isinstance(a, float) or isinstance(b, float):
        return f"{b - a:+.1f}"
    return f"{b - a:+d}"


@dataclass
class ModeAggregate:
    n: int
    passed: int
    avg_wall: float
    avg_in: float | None
    avg_out: float | None
    avg_added: float
    avg_removed: float
    avg_dispatch: float
    avg_dna: float
    avg_turns: float


def _avg_or_none(xs):
    nums = [x for x in xs if isinstance(x, int) or isinstance(x, float)]
    return mean(nums) if nums else None


def _avg(xs):
    if not xs:
        return 0.0
    return sum(xs) / len(xs)


def _aggregate(mode_results) -> ModeAggregate:
    return ModeAggregate(
        n=len(mode_results),
        passed=sum(1 for m in mode_results if m.success),
        avg_wall=_avg([m.result.wall_time_s for m in mode_results]),
        avg_in=_avg_or_none([m.result.input_tokens for m in mode_results]),
        avg_out=_avg_or_none([m.result.output_tokens for m in mode_results]),
        avg_added=_avg([m.arch_metrics.get("code_lines_added", 0) for m in mode_results]),
        avg_removed=_avg([m.arch_metrics.get("code_lines_removed", 0) for m in mode_results]),
        avg_dispatch=_avg([m.arch_metrics.get("dispatch_count", 0) for m in mode_results]),
        avg_dna=_avg([m.arch_metrics.get("dna_read_count", 0) for m in mode_results]),
        avg_turns=_avg([m.arch_metrics.get("turn_count", 0) for m in mode_results]),
    )


def render_ab_markdown(
    ab_results: list[AbResult],
    *,
    title: str,
    metadata: dict,
) -> str:
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Run")
    lines.append("")
    for k, v in metadata.items():
        lines.append(f"- **{k}**: {v}")

    plain_modes = [ab.plain for ab in ab_results]
    cbim_modes = [ab.cbim for ab in ab_results]
    plain_agg = _aggregate(plain_modes)
    cbim_agg = _aggregate(cbim_modes)
    lines.append(
        f"- **Tasks**: {len(ab_results)} × 2 modes = {len(ab_results) * 2} runs"
    )
    lines.append(
        f"- **Outcome**: plain {plain_agg.passed}/{plain_agg.n} pass, "
        f"cbim {cbim_agg.passed}/{cbim_agg.n} pass"
    )
    lines.append("")

    # Per-task side-by-side
    lines.append("## Per-task side-by-side")
    lines.append("")
    header = [
        "Task", "Mode", "Success", "Wall", "In tok", "Out tok",
        "Lines +", "Lines -", "Dispatch", "DNA reads", "Turns",
    ]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for ab in ab_results:
        for m in (ab.plain, ab.cbim):
            row = [
                f"`{ab.task_name}`",
                m.mode,
                "pass" if m.success else "fail",
                _wall(m.result.wall_time_s),
                _tok(m.result.input_tokens),
                _tok(m.result.output_tokens),
                str(m.arch_metrics.get("code_lines_added", 0)),
                str(m.arch_metrics.get("code_lines_removed", 0)),
                str(m.arch_metrics.get("dispatch_count", 0)),
                str(m.arch_metrics.get("dna_read_count", 0)),
                str(m.arch_metrics.get("turn_count", 0)),
            ]
            lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Summary
    lines.append("## Summary (averages across all tasks)")
    lines.append("")
    lines.append("| Metric | Plain | CBIM | Delta |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| Success rate | {plain_agg.passed}/{plain_agg.n} "
        f"({plain_agg.passed / max(plain_agg.n, 1) * 100:.0f}%) | "
        f"{cbim_agg.passed}/{cbim_agg.n} "
        f"({cbim_agg.passed / max(cbim_agg.n, 1) * 100:.0f}%) | "
        f"{(cbim_agg.passed - plain_agg.passed):+d} task(s) |"
    )
    lines.append(
        f"| Avg wall time | {_wall(plain_agg.avg_wall)} | {_wall(cbim_agg.avg_wall)} | "
        f"{cbim_agg.avg_wall - plain_agg.avg_wall:+.1f}s ({_pct(plain_agg.avg_wall, cbim_agg.avg_wall)}) |"
    )
    lines.append(
        f"| Avg input tokens | {_tok(plain_agg.avg_in)} | {_tok(cbim_agg.avg_in)} | "
        f"{_delta(plain_agg.avg_in, cbim_agg.avg_in)} |"
    )
    lines.append(
        f"| Avg output tokens | {_tok(plain_agg.avg_out)} | {_tok(cbim_agg.avg_out)} | "
        f"{_delta(plain_agg.avg_out, cbim_agg.avg_out)} |"
    )
    lines.append(
        f"| Avg code lines added | {plain_agg.avg_added:.1f} | {cbim_agg.avg_added:.1f} | "
        f"{cbim_agg.avg_added - plain_agg.avg_added:+.1f} |"
    )
    lines.append(
        f"| Avg code lines removed | {plain_agg.avg_removed:.1f} | {cbim_agg.avg_removed:.1f} | "
        f"{cbim_agg.avg_removed - plain_agg.avg_removed:+.1f} |"
    )
    lines.append(
        f"| Avg dispatch count | {plain_agg.avg_dispatch:.1f} | {cbim_agg.avg_dispatch:.1f} | "
        f"{cbim_agg.avg_dispatch - plain_agg.avg_dispatch:+.1f} |"
    )
    lines.append(
        f"| Avg .dna reads | {plain_agg.avg_dna:.1f} | {cbim_agg.avg_dna:.1f} | "
        f"{cbim_agg.avg_dna - plain_agg.avg_dna:+.1f} |"
    )
    lines.append(
        f"| Avg turn count | {plain_agg.avg_turns:.1f} | {cbim_agg.avg_turns:.1f} | "
        f"{cbim_agg.avg_turns - plain_agg.avg_turns:+.1f} |"
    )
    lines.append("")

    # Diagnostics
    lines.append("## Diagnostics")
    lines.append("")
    failed = [
        (ab.task_name, mode)
        for ab in ab_results
        for mode in (ab.plain, ab.cbim)
        if not mode.success
    ]
    if not failed:
        lines.append("All runs passed their success_check.")
    else:
        for name, mode in failed:
            lines.append(f"### `{name}` — {mode.mode}: FAIL")
            lines.append("")
            lines.append(f"- exit code: {mode.result.exit_code}")
            lines.append(f"- wall: {_wall(mode.result.wall_time_s)}")
            stderr = (mode.result.stderr or "").strip().splitlines()
            if stderr:
                lines.append(f"- stderr head: {stderr[0][:160]}")
            lines.append("")
    return "\n".join(lines)
