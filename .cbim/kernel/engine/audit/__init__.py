"""audit — read-only governance drift checks across .dna, .claude/agents, .cbim/memory.

Public API:
  run_audit(project_root, *, checks=None) -> AuditResult
  list_checks() -> list[str]
  AuditResult, AuditFinding
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .config import load_audit_config
from .registry import CHECKS, list_check_names
from .result import AuditFinding, AuditResult


def list_checks() -> list[str]:
    return list_check_names()


def run_audit(
    project_root: Path | str,
    *,
    checks: list[str] | None = None,
) -> AuditResult:
    root = Path(project_root).resolve()
    cfg = load_audit_config()

    selected = checks or list_check_names()
    unknown = [c for c in selected if c not in CHECKS]
    if unknown:
        raise ValueError(
            f"unknown check(s): {unknown}; available: {list_check_names()}"
        )

    findings: list[AuditFinding] = []
    for name in selected:
        findings.extend(CHECKS[name](root, cfg))

    summary = {
        "total": len(findings),
        "error": sum(1 for f in findings if f.severity == "error"),
        "warn": sum(1 for f in findings if f.severity == "warn"),
        "info": sum(1 for f in findings if f.severity == "info"),
        "checks_ran": list(selected),
        "by_check": {
            n: sum(1 for f in findings if f.check == n) for n in selected
        },
    }

    return AuditResult(
        findings=findings,
        summary=summary,
        ran_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        project_root=str(root),
        config_snapshot=cfg,
    )


__all__ = [
    "run_audit",
    "list_checks",
    "AuditResult",
    "AuditFinding",
]
