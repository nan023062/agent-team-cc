"""checks/dna_fission.py — DNA module body & workflow oversize detection.

Findings:
  DNA_BODY_OVERSIZE       info/warn/error  module.md body exceeds size band
  DNA_WORKFLOW_OVERLOAD   info/warn/error  module has too many workflows
"""

from __future__ import annotations

from pathlib import Path

from services import list_modules as _service_list_modules

from ..config import resolve_bands
from ..result import AuditFinding


def check(project_root: Path, config: dict) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    cfg = config.get("dna_fission", {})
    max_body = cfg.get("max_body_lines", 350)
    max_wf = cfg.get("max_workflow_count", 8)

    for m in _service_list_modules(cwd=str(project_root)):
        path = m.get("path") or m.get("id") or "?"
        body_lines = (m.get("architecture") or "").count("\n") + 1 \
            if (m.get("architecture") or "") else 0
        sev = resolve_bands(body_lines, max_body)
        if sev:
            findings.append(AuditFinding(
                check="dna_fission",
                severity=sev,
                target=path,
                message=(
                    f"module {path!r} body has {body_lines} lines "
                    f"(threshold {max_body})"
                ),
                suggestion=(
                    "Consider splitting via `cbim dna split` once the module covers "
                    "more than one cohesive concept."
                ),
                code="DNA_BODY_OVERSIZE",
                metadata={"lines": body_lines, "threshold": max_body},
            ))

        wf_count = len(m.get("workflows") or [])
        sev = resolve_bands(wf_count, max_wf)
        if sev:
            findings.append(AuditFinding(
                check="dna_fission",
                severity=sev,
                target=path,
                message=(
                    f"module {path!r} owns {wf_count} workflows "
                    f"(threshold {max_wf})"
                ),
                suggestion=(
                    "Workflow sprawl usually signals the module has acquired a "
                    "second responsibility; consider `cbim dna split`."
                ),
                code="DNA_WORKFLOW_OVERLOAD",
                metadata={"count": wf_count, "threshold": max_wf},
            ))
    return findings
