"""Render Results / Stats as markdown or stdout summaries.

Three public renderers:

  * `render_markdown(aggregate, cases, ...)`   — full multi-case bench report
  * `render_markdown_single(result, verdict)`  — single-case CLI report
  * `render_stdout(result, verdict)`           — short human-readable line
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from .stats import AggregateStats, CaseStats, aggregate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


CASE_NAME_RE = re.compile(r"^test_loop_(?P<loop>[a-z]+)_(?P<flavor>positive|negative)$")
LOOP_ORDER = ["execution", "architect", "hr", "memory"]
FLAVOR_ORDER = {"positive": 0, "negative": 1}


def _split_case(name: str) -> tuple[str, str]:
    m = CASE_NAME_RE.match(name)
    if not m:
        return (name, "")
    return (m.group("loop"), m.group("flavor"))


def _sort_key(c: CaseStats) -> tuple[int, int]:
    loop, flavor = _split_case(c.name)
    return (
        LOOP_ORDER.index(loop) if loop in LOOP_ORDER else 99,
        FLAVOR_ORDER.get(flavor, 99),
    )


def _tok(v: int | None) -> str:
    if v is None:
        return "?"
    if v >= 1000:
        return f"{v / 1000:.1f}k"
    return str(v)


def _wall(s: float) -> str:
    return f"{s:.1f}s"


def _verdict_to_case(name: str, verdict, result) -> CaseStats:
    """Build a CaseStats from a Verdict + Result. Lives here so callers
    don't have to import three modules just to glue the two together."""
    return CaseStats(
        name=name,
        passed=bool(verdict.passed),
        wall_time_s=result.wall_time_s,
        sub_checks_passed=verdict.sub_checks_passed,
        sub_checks_total=verdict.sub_checks_total,
        top_failure=verdict.top_failure,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        arch_metrics=dict(result.arch_metrics or {}),
    )


# ---------------------------------------------------------------------------
# Per-case table
# ---------------------------------------------------------------------------


def _case_table(cases: list[CaseStats], log_dir_rel: str | None) -> str:
    has_log_col = log_dir_rel is not None
    header = ["Case", "Status", "Sub", "Wall", "In tok", "Out tok"]
    if has_log_col:
        header.append("Log")
    sep = ["---"] * len(header)
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
    for c in cases:
        sub = f"{c.sub_checks_passed}/{c.sub_checks_total}"
        status = "pass" if c.passed else "fail"
        row = [
            f"`{c.name}`",
            status,
            sub,
            _wall(c.wall_time_s),
            _tok(c.input_tokens),
            _tok(c.output_tokens),
        ]
        if has_log_col:
            row.append(f"`{log_dir_rel}/{c.name}.log`")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _diagnostics_section(cases: list[CaseStats]) -> str:
    failed = [c for c in cases if not c.passed]
    if not failed:
        return "All checks passed."
    parts: list[str] = []
    for c in failed:
        parts.append(f"### `{c.name}`\n")
        if c.top_failure:
            parts.append(f"- top failure: {c.top_failure}")
        parts.append(f"- sub-checks: {c.sub_checks_passed}/{c.sub_checks_total}")
        parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public renderers
# ---------------------------------------------------------------------------


def render_markdown(
    aggregate: AggregateStats,
    cases: list[CaseStats],
    *,
    title: str,
    metadata: dict,
    log_dir_rel: str | None = None,
) -> str:
    """Multi-case markdown report (used by run-bench.sh / batch entry)."""
    sorted_cases = sorted(cases, key=_sort_key)

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Run")
    lines.append("")
    for k, v in metadata.items():
        lines.append(f"- **{k}**: {v}")
    lines.append(
        f"- **Cases**: {aggregate.total} total — {aggregate.passed} pass, "
        f"{aggregate.failed} fail (pass rate {aggregate.pass_rate * 100:.0f}%)"
    )
    lines.append(
        f"- **Wall**: {_wall(aggregate.total_wall_time_s)} total, "
        f"avg {_wall(aggregate.avg_wall_time_s)}/case"
    )
    lines.append(
        f"- **Tokens**: in {_tok(aggregate.total_input_tokens)}, "
        f"out {_tok(aggregate.total_output_tokens)}"
    )
    lines.append("")
    lines.append("## Per-case results")
    lines.append("")
    lines.append(_case_table(sorted_cases, log_dir_rel))
    lines.append("")

    if aggregate.by_group:
        lines.append("## Per-group summary")
        lines.append("")
        lines.append("| Group | Pass / Total | Wall | In tok | Out tok |")
        lines.append("|---|---|---|---|---|")
        for g, sub in aggregate.by_group.items():
            lines.append(
                f"| {g} | {sub.passed}/{sub.total} | {_wall(sub.total_wall_time_s)} | "
                f"{_tok(sub.total_input_tokens)} | {_tok(sub.total_output_tokens)} |"
            )
        lines.append("")

    lines.append("## Diagnostics")
    lines.append("")
    lines.append(_diagnostics_section(sorted_cases))
    lines.append("")
    return "\n".join(lines)


def render_markdown_single(result, verdict=None) -> str:
    """Single-case markdown report — used by CLI `run --output`."""
    parts: list[str] = []
    parts.append("# Workflow run")
    parts.append("")
    parts.append(f"- **Project**: `{result.target_root}`")
    parts.append(f"- **Started**: {result.started_at}")
    parts.append(f"- **Wall**: {_wall(result.wall_time_s)}")
    parts.append(f"- **Exit**: {result.exit_code}")
    parts.append(f"- **Tokens**: in {_tok(result.input_tokens)}, out {_tok(result.output_tokens)}")
    if result.session_log_path:
        parts.append(f"- **Session log**: `{result.session_log_path}`")
    parts.append("")
    parts.append("## Prompt")
    parts.append("")
    parts.append("```")
    parts.append(result.prompt.strip())
    parts.append("```")
    parts.append("")
    if verdict is not None:
        parts.append("## Verdict")
        parts.append("")
        parts.append(f"- **Passed**: {verdict.passed}")
        parts.append(
            f"- **Sub-checks**: {verdict.sub_checks_passed}/{verdict.sub_checks_total}"
        )
        if verdict.top_failure:
            parts.append(f"- **Top failure**: {verdict.top_failure}")
        if verdict.diagnostics:
            parts.append("")
            parts.append("### Diagnostics")
            parts.append("")
            for d in verdict.diagnostics:
                parts.append(f"- {d}")
        parts.append("")
    return "\n".join(parts)


def render_stdout(result, verdict=None) -> str:
    """Compact single-line-ish summary for CLI stdout."""
    head = (
        f"exit={result.exit_code} wall={_wall(result.wall_time_s)} "
        f"in={_tok(result.input_tokens)} out={_tok(result.output_tokens)} "
        f"log={result.session_log_path}"
    )
    if verdict is None:
        return head
    status = "PASS" if verdict.passed else "FAIL"
    sub = f"{verdict.sub_checks_passed}/{verdict.sub_checks_total}"
    tail = f"\n[{status}] sub={sub}"
    if not verdict.passed and verdict.top_failure:
        tail += f" top_failure={verdict.top_failure!r}"
    return head + tail


# ---------------------------------------------------------------------------
# Bench-report CLI (used by run-bench.sh)
# ---------------------------------------------------------------------------


def _load_meta(logs_dir: Path) -> list[dict]:
    metas: list[dict] = []
    for path in sorted(logs_dir.glob("*.meta.json")):
        try:
            metas.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return metas


def _meta_to_case(m: dict) -> CaseStats:
    top_failure = None
    if m.get("outcome") == "failed":
        top_failure = m.get("top_failure")
        if not top_failure:
            longrepr_lines = (m.get("longrepr") or "").strip().splitlines()
            top_failure = longrepr_lines[0] if longrepr_lines else None
    return CaseStats(
        name=m.get("test_name", "?"),
        passed=(m.get("outcome") == "passed"),
        wall_time_s=float(m.get("duration_s") or 0.0),
        sub_checks_passed=int(m.get("sub_checks_passed") or 0),
        sub_checks_total=int(m.get("sub_checks_total") or 0),
        top_failure=top_failure,
        input_tokens=m.get("input_tokens"),
        output_tokens=m.get("output_tokens"),
        arch_metrics=m.get("arch_metrics") or {},
    )


def _group_fn(c: CaseStats) -> str:
    loop, _ = _split_case(c.name)
    return loop


def build_bench_report(args: argparse.Namespace) -> str:
    logs_dir = Path(args.logs_dir)
    metas = _load_meta(logs_dir)
    cases = [_meta_to_case(m) for m in metas]
    agg = aggregate(cases, group_fn=_group_fn)

    metadata = {
        "Start": args.ts_start,
        "End": args.ts_end,
        "Git": f"{args.git_branch} @ {args.git_commit}",
        "Pytest exit": args.pytest_exit,
    }
    title = f"Workflow tests — Report {args.report_id}"
    return render_markdown(
        agg,
        cases,
        title=title,
        metadata=metadata,
        log_dir_rel=f"report-{args.report_id}/logs",
    )


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m v1.tests.framework.reporter")
    ap.add_argument("--raw-output", required=False, default="")
    ap.add_argument("--logs-dir", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--ts-start", required=True)
    ap.add_argument("--ts-end", required=True)
    ap.add_argument("--git-commit", required=True)
    ap.add_argument("--git-branch", required=True)
    ap.add_argument("--pytest-exit", required=True)
    ap.add_argument("--report-id", required=True)
    args = ap.parse_args()
    Path(args.output).write_text(build_bench_report(args), encoding="utf-8")
    sys.stdout.write(f"wrote {args.output}\n")


if __name__ == "__main__":
    main()
