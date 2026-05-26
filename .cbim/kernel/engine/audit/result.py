"""audit/result.py — AuditFinding / AuditResult dataclasses + JSON helpers.

Pure data; no I/O. Both `report.py` and the JSON CLI mode consume this.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Severity = Literal["info", "warn", "error"]

_SEVERITY_RANK = {"info": 0, "warn": 1, "error": 2}


@dataclass
class AuditFinding:
    check: str
    severity: Severity
    target: str | None
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    suggestion: str | None = None
    code: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditResult:
    findings: list[AuditFinding]
    summary: dict
    ran_at: str
    project_root: str
    config_snapshot: dict

    def to_dict(self) -> dict:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "ran_at": self.ran_at,
            "project_root": self.project_root,
            "config_snapshot": self.config_snapshot,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def max_severity(self) -> Severity | None:
        if not self.findings:
            return None
        return max(self.findings, key=lambda f: _SEVERITY_RANK[f.severity]).severity


def severity_rank(s: Severity) -> int:
    return _SEVERITY_RANK[s]
