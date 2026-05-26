"""audit/report.py — rendering helpers for AuditResult.

Three surfaces:
  to_stdout   compact human-readable table (default CLI mode)
  to_markdown summary suitable for pasting into review notes
  to_json     thin wrapper around AuditResult.to_json

None of these write files; the caller decides where the bytes go.
"""

from __future__ import annotations

from .result import AuditResult, severity_rank

_SEVERITY_GLYPH = {"info": "[info]", "warn": "[WARN]", "error": "[ERR ]"}


def to_stdout(result: AuditResult) -> str:
    if not result.findings:
        return f"audit: no findings ({len(result.summary.get('checks_ran', []))} checks ran)\n"
    lines: list[str] = []
    findings = sorted(
        result.findings,
        key=lambda f: (-severity_rank(f.severity), f.check, f.target or "", f.code or ""),
    )
    for f in findings:
        glyph = _SEVERITY_GLYPH.get(f.severity, f.severity)
        target = f.target if f.target is not None else "-"
        code = f.code or "?"
        lines.append(f"{glyph} {f.check}/{code} :: {target} :: {f.message}")
        if f.suggestion:
            lines.append(f"        -> {f.suggestion}")
    summary = result.summary
    lines.append("")
    lines.append(
        f"audit: {summary.get('total', 0)} findings "
        f"(error={summary.get('error', 0)}, warn={summary.get('warn', 0)}, "
        f"info={summary.get('info', 0)}) across {len(summary.get('checks_ran', []))} checks"
    )
    return "\n".join(lines) + "\n"


def to_markdown(result: AuditResult) -> str:
    out: list[str] = []
    out.append(f"# Audit Report\n")
    out.append(f"- ran_at: {result.ran_at}")
    out.append(f"- project_root: {result.project_root}")
    s = result.summary
    out.append(
        f"- summary: total={s.get('total', 0)} "
        f"error={s.get('error', 0)} warn={s.get('warn', 0)} info={s.get('info', 0)}\n"
    )
    if not result.findings:
        out.append("_No findings._\n")
        return "\n".join(out)
    out.append("| severity | check | code | target | message |")
    out.append("|----------|-------|------|--------|---------|")
    findings = sorted(
        result.findings,
        key=lambda f: (-severity_rank(f.severity), f.check, f.target or ""),
    )
    for f in findings:
        target = (f.target or "-").replace("|", "\\|")
        message = f.message.replace("|", "\\|").replace("\n", " ")
        out.append(
            f"| {f.severity} | {f.check} | {f.code or '?'} | {target} | {message} |"
        )
    return "\n".join(out) + "\n"


def to_json(result: AuditResult) -> str:
    return result.to_json()
