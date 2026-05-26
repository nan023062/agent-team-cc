"""checks/agent_fission.py — project-level agent body & skill oversize detection.

Built-in framework agents are excluded (services.list_agents handles that).

Findings:
  AGENT_BODY_OVERSIZE     info/warn/error  agent .md file too long
  AGENT_SKILL_OVERLOAD    info/warn/error  too many skills under one agent
"""

from __future__ import annotations

from pathlib import Path

from services import list_agents as _service_list_agents

from ..config import resolve_bands
from ..result import AuditFinding
from ._agent_skill_parser import count_skills


def check(project_root: Path, config: dict) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    cfg = config.get("agent_fission", {})
    max_body = cfg.get("max_body_lines", 250)
    max_skills = cfg.get("max_skill_count", 6)

    for a in _service_list_agents(cwd=str(project_root), include_builtin=False):
        agent_id = a.get("id") or "?"
        md_path = project_root / ".claude" / "agents" / agent_id / f"{agent_id}.md"
        body_lines = 0
        if md_path.exists():
            try:
                body_lines = sum(1 for _ in md_path.read_text(encoding="utf-8").splitlines())
            except OSError:
                body_lines = 0

        sev = resolve_bands(body_lines, max_body)
        if sev:
            findings.append(AuditFinding(
                check="agent_fission",
                severity=sev,
                target=agent_id,
                message=(
                    f"agent {agent_id!r} body has {body_lines} lines "
                    f"(threshold {max_body})"
                ),
                suggestion=(
                    "Split capabilities into a dedicated agent via "
                    "`cbim agent scaffold` or extract heavy content into skills."
                ),
                code="AGENT_BODY_OVERSIZE",
                metadata={"lines": body_lines, "threshold": max_body},
            ))

        skill_count = count_skills(a.get("body", "") or "", agent_id)
        if skill_count == 0:
            skill_count = len(a.get("skills") or [])
        sev = resolve_bands(skill_count, max_skills)
        if sev:
            findings.append(AuditFinding(
                check="agent_fission",
                severity=sev,
                target=agent_id,
                message=(
                    f"agent {agent_id!r} has {skill_count} skills "
                    f"(threshold {max_skills})"
                ),
                suggestion=(
                    "Either fission the agent (HR: `cbim agent scaffold`) or "
                    "consolidate overlapping skills."
                ),
                code="AGENT_SKILL_OVERLOAD",
                metadata={"count": skill_count, "threshold": max_skills},
            ))
    return findings
