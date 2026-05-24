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
    header = ["Case", "状态", "Sub", "耗时", "输入 token", "输出 token"]
    if has_log_col:
        header.append("日志")
    sep = ["---"] * len(header)
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
    for c in cases:
        sub = f"{c.sub_checks_passed}/{c.sub_checks_total}"
        status = "通过" if c.passed else "失败"
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
        return "全部检查通过。"
    parts: list[str] = []
    for c in failed:
        parts.append(f"### `{c.name}`\n")
        if c.top_failure:
            parts.append(f"- 主要失败：{c.top_failure}")
        parts.append(f"- 子检查：{c.sub_checks_passed}/{c.sub_checks_total}")
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
    lines.append("## 运行")
    lines.append("")
    for k, v in metadata.items():
        lines.append(f"- **{k}**：{v}")
    lines.append(
        f"- **Case**：共 {aggregate.total} —— 通过 {aggregate.passed}，"
        f"失败 {aggregate.failed}（通过率 {aggregate.pass_rate * 100:.0f}%）"
    )
    lines.append(
        f"- **耗时**：总 {_wall(aggregate.total_wall_time_s)}，"
        f"平均 {_wall(aggregate.avg_wall_time_s)}/case"
    )
    lines.append(
        f"- **Token**：输入 {_tok(aggregate.total_input_tokens)}，"
        f"输出 {_tok(aggregate.total_output_tokens)}"
    )
    lines.append("")
    lines.append("## 逐 case 结果")
    lines.append("")
    lines.append(_case_table(sorted_cases, log_dir_rel))
    lines.append("")

    if aggregate.by_group:
        lines.append("## 分组汇总")
        lines.append("")
        lines.append("| 分组 | 通过 / 总数 | 耗时 | 输入 token | 输出 token |")
        lines.append("|---|---|---|---|---|")
        for g, sub in aggregate.by_group.items():
            lines.append(
                f"| {g} | {sub.passed}/{sub.total} | {_wall(sub.total_wall_time_s)} | "
                f"{_tok(sub.total_input_tokens)} | {_tok(sub.total_output_tokens)} |"
            )
        lines.append("")

    lines.append("## 诊断")
    lines.append("")
    lines.append(_diagnostics_section(sorted_cases))
    lines.append("")
    return "\n".join(lines)


def render_markdown_single(result, verdict=None) -> str:
    """Single-case markdown report — used by CLI `run --output`."""
    parts: list[str] = []
    parts.append("# Workflow 运行")
    parts.append("")
    parts.append(f"- **项目**：`{result.target_root}`")
    parts.append(f"- **开始**：{result.started_at}")
    parts.append(f"- **耗时**：{_wall(result.wall_time_s)}")
    parts.append(f"- **退出码**：{result.exit_code}")
    parts.append(f"- **Token**：输入 {_tok(result.input_tokens)}，"
                 f"输出 {_tok(result.output_tokens)}")
    if result.session_log_path:
        parts.append(f"- **Session 日志**：`{result.session_log_path}`")
    parts.append("")
    parts.append("## Prompt")
    parts.append("")
    parts.append("```")
    parts.append(result.prompt.strip())
    parts.append("```")
    parts.append("")
    if verdict is not None:
        parts.append("## 判定")
        parts.append("")
        parts.append(f"- **通过**：{verdict.passed}")
        parts.append(
            f"- **子检查**：{verdict.sub_checks_passed}/{verdict.sub_checks_total}"
        )
        if verdict.top_failure:
            parts.append(f"- **主要失败**：{verdict.top_failure}")
        if verdict.diagnostics:
            parts.append("")
            parts.append("### 诊断")
            parts.append("")
            for d in verdict.diagnostics:
                parts.append(f"- {d}")
        parts.append("")
    return "\n".join(parts)


def render_stdout(result, verdict=None) -> str:
    """Compact single-line-ish summary for CLI stdout."""
    head = (
        f"退出码={result.exit_code} 耗时={_wall(result.wall_time_s)} "
        f"输入={_tok(result.input_tokens)} 输出={_tok(result.output_tokens)} "
        f"日志={result.session_log_path}"
    )
    if verdict is None:
        return head
    status = "通过" if verdict.passed else "失败"
    sub = f"{verdict.sub_checks_passed}/{verdict.sub_checks_total}"
    tail = f"\n[{status}] 子检查={sub}"
    if not verdict.passed and verdict.top_failure:
        tail += f" 主要失败={verdict.top_failure!r}"
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
        "开始": args.ts_start,
        "结束": args.ts_end,
        "Git": f"{args.git_branch} @ {args.git_commit}",
        "Pytest 退出码": args.pytest_exit,
    }
    title = f"Workflow 测试 —— 报告 {args.report_id}"
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
